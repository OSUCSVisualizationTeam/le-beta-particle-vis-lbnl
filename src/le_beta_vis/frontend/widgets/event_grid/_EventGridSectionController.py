import math
from typing import Callable, List, Tuple

from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QListView, QVBoxLayout, QWidget

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.theme import COLOR_BACKGROUND_SURFACE
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionGrouping import (
    SectionInfo,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionHeaderWidget import (
    EventGridSectionHeaderWidget,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionRow import (
    _SectionRow,
)
from le_beta_vis.frontend.widgets.event_grid._EventItemDelegate import (
    CLUSTER_ROLE,
    _EventItemDelegate,
)


class _EventGridSectionController:
    """Builds, tears down, and sizes per-section widgets.

    Holds a live reference to the owning widget's ``_sections`` list
    rather than a copy, so every operation reflects the current
    window — mirrors the same ownership pattern as
    ``_SlidingWindowPager``. Also translates each section's raw Qt
    signals (header nav buttons, list view clicks) into flat-index
    callbacks, since that translation always needs the section's
    *current* position in ``sections`` at signal-fire time, which
    only this class can look up.
    """

    def __init__(
        self,
        sections: List[_SectionRow],
        content_layout: QVBoxLayout,
        content_widget: QWidget,
        delegate: _EventItemDelegate,
        item_width_getter: Callable[[], int],
        item_height_getter: Callable[[], int],
        max_cols_getter: Callable[[], int],
        widget_width_getter: Callable[[], int],
        on_page_jump: Callable[[int, int], None],
        on_navigate_to_self: Callable[[int], None],
        on_item_selected: Callable[[int], None],
    ) -> None:
        self._sections = sections
        self._content_layout = content_layout
        self._content_widget = content_widget
        self._delegate = delegate
        self._item_width_getter = item_width_getter
        self._item_height_getter = item_height_getter
        self._max_cols_getter = max_cols_getter
        self._widget_width_getter = widget_width_getter
        self._on_page_jump = on_page_jump
        self._on_navigate_to_self = on_navigate_to_self
        self._on_item_selected = on_item_selected

    # ------------------------------------------------------------------ #
    # Section construction & teardown                                      #
    # ------------------------------------------------------------------ #

    def buildItem(self, cluster: Cluster) -> QStandardItem:
        """Builds one non-editable grid item carrying its source cluster."""
        item = QStandardItem()
        item.setData(cluster, CLUSTER_ROLE)
        item.setEditable(False)
        return item

    def addSection(
        self,
        info: SectionInfo,
        events: List[Cluster],
        base_offset: int = 0,
    ) -> None:
        """Creates and appends one section (header + list view) to the layout.

        Args:
            info: Section descriptor with a global ``start_index``.
            events: Cluster list to slice rows from.
            base_offset: Subtracted from ``info.start_index`` to get
                the local slice position into *events* — 0 when
                *events* is the full resident list (``setEvents``),
                or the window's prior end when *events* is a freshly
                appended chunk (``appendEvents``).
        """
        header, view, model = self._buildRow(info, events, base_offset)
        self._content_layout.addWidget(header)
        self._content_layout.addWidget(view)
        self._sections.append(_SectionRow(info, header_widget=header,
                                          list_view=view, model=model))

    def insertSectionAtFront(
        self,
        info: SectionInfo,
        events: List[Cluster],
        base_offset: int,
    ) -> None:
        """Creates one section and inserts it at the very top of the layout.

        Mirror of ``addSection`` for ``prependEvents`` — used when a
        backward page fetch introduces clusters earlier than anything
        currently resident.
        """
        header, view, model = self._buildRow(info, events, base_offset)
        self._content_layout.insertWidget(0, header)
        self._content_layout.insertWidget(1, view)
        self._sections.insert(0, _SectionRow(info, header_widget=header,
                                             list_view=view, model=model))

    def _buildRow(
        self,
        info: SectionInfo,
        events: List[Cluster],
        base_offset: int,
    ) -> Tuple[EventGridSectionHeaderWidget, QListView, QStandardItemModel]:
        header = self._buildHeader(info)
        model = QStandardItemModel()
        view = self._buildListView()
        view.setModel(model)

        start = info.start_index - base_offset
        for cluster in events[start: start + info.count]:
            model.appendRow(self.buildItem(cluster))

        view.setFixedHeight(self.computeListViewHeight(info.count))
        return header, view, model

    def clearAll(self) -> None:
        """Removes all section widgets from the content layout."""
        for row in self._sections:
            row.header_widget.setParent(None)
            row.list_view.setParent(None)
            row.header_widget.deleteLater()
            row.list_view.deleteLater()
        self._sections.clear()

    def _buildHeader(self, info: SectionInfo) -> EventGridSectionHeaderWidget:
        """Creates a section header widget for *info* with navigation.

        Navigation looks up the header's *current* position in
        ``sections`` at click time (via ``_indexOfHeader``) rather
        than capturing a fixed index — sections can be
        inserted/removed by ``appendEvents``/``prependEvents``/
        ``evictFront``/``evictBack`` after this header is built, which
        would make a captured index stale.
        """
        header = EventGridSectionHeaderWidget()
        date = info.date_part if info.date_part else header.tr("Unknown Date")
        file = info.file_part if info.file_part else header.tr("Unknown File")
        header.setDateText(date)
        header.setFileText(file)
        header.navigatePrevious.connect(
            lambda h=header: self._emitPageJump(h, -1),
        )
        header.navigateNext.connect(
            lambda h=header: self._emitPageJump(h, 1),
        )
        header.navigateToSelf.connect(
            lambda h=header: self._on_navigate_to_self(self._indexOfHeader(h)),
        )
        return header

    def _indexOfHeader(self, header: EventGridSectionHeaderWidget) -> int:
        """Returns *header*'s current position in ``sections``, or -1."""
        for i, row in enumerate(self._sections):
            if row.header_widget is header:
                return i
        return -1

    def _emitPageJump(self, header: EventGridSectionHeaderWidget, direction: int) -> None:
        """Invokes ``on_page_jump`` anchored on *header*'s section."""
        idx = self._indexOfHeader(header)
        if idx < 0:
            return
        self._on_page_jump(self._sections[idx].info.start_index, direction)

    def _buildListView(self) -> QListView:
        """Creates a per-section QListView with shared delegate.

        Click handling looks up the view's *current* section index at
        click time (via ``_indexOfListView``) for the same reason
        navigation does — see ``_buildHeader``.
        """
        view = QListView()
        view.setItemDelegate(self._delegate)
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setGridSize(QSize(self._item_width_getter(), self._item_height_getter()))
        view.setUniformItemSizes(True)
        view.setSpacing(4)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet(f"background-color: {COLOR_BACKGROUND_SURFACE};")
        view.clicked.connect(
            lambda idx, v=view: self._onItemClicked(v, idx)
        )
        return view

    def _indexOfListView(self, view: QListView) -> int:
        """Returns *view*'s current position in ``sections``, or -1."""
        for i, row in enumerate(self._sections):
            if row.list_view is view:
                return i
        return -1

    def _onItemClicked(self, view: QListView, index: QModelIndex) -> None:
        """Translates a per-section click into a flat-index callback."""
        section_index = self._indexOfListView(view)
        if section_index < 0:
            return
        for i, row in enumerate(self._sections):
            if i != section_index:
                row.list_view.clearSelection()
        flat = self._sections[section_index].info.start_index + index.row()
        self._on_item_selected(flat)

    # ------------------------------------------------------------------ #
    # Navigation state                                                      #
    # ------------------------------------------------------------------ #

    def refreshNavigationStates(
        self,
        has_more_backward: bool,
        has_more_forward: bool,
        is_loading: bool = False,
    ) -> None:
        """Set prev/next button states on all section headers.

        A section's own skip button is enabled either when an
        adjacent resident section exists, or — at the window's edges —
        when the ViewModel has reported a further page exists there.
        While *is_loading* is true, every skip button is force-disabled
        regardless of adjacency — prevents a spam-clicked button from
        firing a second full grid rebuild before the first one's fetch
        and layout pass have finished.
        """
        total = len(self._sections)
        for i, row in enumerate(self._sections):
            row.header_widget.setNavigationState(
                has_previous=not is_loading and (i > 0 or has_more_backward),
                has_next=not is_loading and (i < total - 1 or has_more_forward),
            )

    # ------------------------------------------------------------------ #
    # Sizing                                                               #
    # ------------------------------------------------------------------ #

    def computeListViewHeight(self, count: int) -> int:
        """Calculate the pixel height needed to display *count* items.

        Qt's icon-mode layout with ``setGridSize`` places items at
        exact grid-size intervals — the ``spacing`` value only adds
        visual padding inside the cell, not to the stride.
        """
        if count == 0:
            return 0
        content_w = self._content_widget.width()
        if content_w <= 0:
            content_w = self._widget_width_getter()
        grid_w = self._item_width_getter()
        grid_h = self._item_height_getter()
        cols = min(max(1, content_w // grid_w), self._max_cols_getter())
        rows = math.ceil(count / cols)
        return rows * grid_h

    def recomputeAllHeights(self) -> None:
        """Recalculate fixed heights for every section list view."""
        for row in self._sections:
            row.list_view.setFixedHeight(
                self.computeListViewHeight(row.info.count),
            )

    def applyGridSize(self, width: int, height: int) -> None:
        """Updates the grid size on every resident list view."""
        grid_size = QSize(width, height)
        for row in self._sections:
            row.list_view.setGridSize(grid_size)
        self.recomputeAllHeights()
