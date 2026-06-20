import math
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QPixmap,
    QResizeEvent,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QScrollArea,
    QScroller,
    QScrollerProperties,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.frontend.theme import COLOR_BACKGROUND_SURFACE
from le_beta_vis.frontend.widgets.event_grid._EventItemDelegate import (
    CLUSTER_ROLE,
    THUMBNAIL_ROLE,
    _EventItemDelegate,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionGrouping import (
    SectionInfo,
    flat_index_to_section,
    group_clusters,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionHeaderWidget import (
    EventGridSectionHeaderWidget,
)
from le_beta_vis.frontend.widgets.event_grid._SlidingWindowPager import (
    _SlidingWindowPager,
)
from le_beta_vis.frontend.widgets.event_grid._StickyHeaderOverlay import (
    _StickyHeaderOverlay,
)
from le_beta_vis.frontend.widgets.event_grid._VisibleRangeTracker import (
    _VisibleRangeTracker,
)


@dataclass
class _SectionRow:
    """Internal bookkeeping for one section in the grid."""

    info: SectionInfo
    header_widget: EventGridSectionHeaderWidget
    list_view: QListView
    model: QStandardItemModel


class EventGridWidget(QWidget):
    """Displays cluster events as a responsive, sectioned grid of thumbnails.

    Clusters are grouped by observation date and FITS filename.
    Each section has a header that pins to the top of the scrollable
    area while the user scrolls through its contents.

    Signals:
        eventSelected(int): Emitted with the flat event index on click.
        visibleRangeChanged(int, int): First and last visible flat indices.
        prefetchRequested(int): Emitted on ``setEvents`` with prefetch count.
    """

    eventSelected = Signal(int)
    visibleRangeChanged = Signal(int, int)
    prefetchRequested = Signal(int)

    def __init__(
        self,
        item_width: int = 140,
        item_height: int = 160,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._item_width = item_width
        self._item_height = item_height
        self._header_height: int = 28
        self._max_cols: int = 3
        self._prefetch_count: int = 30
        self._sections: List[_SectionRow] = []
        self._delegate = _EventItemDelegate(item_width, item_height, self)
        self._initUI()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scrollArea = self._buildScrollArea()
        root.addWidget(self._scrollArea)

        self._stickyOverlay = _StickyHeaderOverlay(
            parent=self,
            sections=self._sections,
            content_widget=self._contentWidget,
            scroll_area=self._scrollArea,
            header_height_getter=lambda: self._header_height,
            on_navigate=self._scrollToSection,
        )
        self._visibleRangeTracker = _VisibleRangeTracker(
            parent=self,
            sections=self._sections,
            content_widget=self._contentWidget,
            scroll_area=self._scrollArea,
            item_width_getter=lambda: self._item_width,
            item_height_getter=lambda: self._item_height,
            max_cols_getter=lambda: self._max_cols,
            header_height_getter=lambda: self._header_height,
            on_range_changed=self.visibleRangeChanged.emit,
        )
        self._pager = _SlidingWindowPager(
            sections=self._sections,
            header_height_getter=lambda: self._header_height,
            compute_list_view_height=self._computeListViewHeight,
            build_item=self._buildItem,
            add_section=self._addSection,
            insert_section_at_front=self._insertSectionAtFront,
        )
        self._configureKineticScrolling(self._scrollArea.viewport())
        self._scrollArea.viewport().installEventFilter(self)
        self._scrollArea.verticalScrollBar().valueChanged.connect(
            self._onScrollChanged,
        )

    def _buildScrollArea(self) -> QScrollArea:
        """Creates the outer scroll area and its content widget."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setStyleSheet(f"background-color: {COLOR_BACKGROUND_SURFACE};")

        self._contentWidget = QWidget()
        self._contentLayout = QVBoxLayout(self._contentWidget)
        self._contentLayout.setContentsMargins(0, 0, 0, 0)
        self._contentLayout.setSpacing(0)
        area.setWidget(self._contentWidget)
        area.verticalScrollBar().setStyleSheet(
            "QScrollBar:vertical { width: 0px; max-width: 0px; }"
        )
        return area

    def _buildSectionHeader(self, info: SectionInfo) -> EventGridSectionHeaderWidget:
        """Creates a section header widget for *info* with navigation.

        Navigation looks up the header's *current* position in
        ``self._sections`` at click time (via ``_indexOfHeader``)
        rather than capturing a fixed index — sections can be
        inserted/removed by ``appendEvents``/``prependEvents``/
        ``evictFront``/``evictBack`` after this header is built, which
        would make a captured index stale.
        """
        header = EventGridSectionHeaderWidget()
        date = info.date_part if info.date_part else self.tr("Unknown Date")
        file = info.file_part if info.file_part else self.tr("Unknown File")
        header.setDateText(date)
        header.setFileText(file)
        header.navigatePrevious.connect(
            lambda h=header: self._scrollToSection(self._indexOfHeader(h) - 1),
        )
        header.navigateNext.connect(
            lambda h=header: self._scrollToSection(self._indexOfHeader(h) + 1),
        )
        header.navigateToSelf.connect(
            lambda h=header: self._scrollToSection(self._indexOfHeader(h)),
        )
        return header

    def _indexOfHeader(self, header: EventGridSectionHeaderWidget) -> int:
        """Returns *header*'s current position in ``self._sections``, or -1."""
        for i, row in enumerate(self._sections):
            if row.header_widget is header:
                return i
        return -1

    def _buildSectionListView(self) -> QListView:
        """Creates a per-section QListView with shared delegate.

        Click handling looks up the view's *current* section index at
        click time (via ``_indexOfListView``) for the same reason
        navigation does — see ``_buildSectionHeader``.
        """
        view = QListView()
        view.setItemDelegate(self._delegate)
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setGridSize(QSize(self._item_width, self._item_height))
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
        """Returns *view*'s current position in ``self._sections``, or -1."""
        for i, row in enumerate(self._sections):
            if row.list_view is view:
                return i
        return -1

    def _configureKineticScrolling(self, viewport: QWidget) -> None:
        """Sets up touch-style kinetic scrolling on *viewport*."""
        QScroller.grabGesture(
            viewport,
            QScroller.LeftMouseButtonGesture,
        )
        scroller = QScroller.scroller(viewport)
        props = scroller.scrollerProperties()
        props.setScrollMetric(QScrollerProperties.AxisLockThreshold, 0.6)
        props.setScrollMetric(
            QScrollerProperties.HorizontalOvershootPolicy,
            QScrollerProperties.OvershootAlwaysOff,
        )
        props.setScrollMetric(
            QScrollerProperties.VerticalOvershootPolicy,
            QScrollerProperties.OvershootAlwaysOff,
        )
        scroller.setScrollerProperties(props)

    # ------------------------------------------------------------------ #
    # Public configuration API                                             #
    # ------------------------------------------------------------------ #

    def setGridSize(self, width: int, height: int) -> None:
        """Updates the grid cell dimensions from configuration.

        Args:
            width: Cell width in pixels.
            height: Cell height in pixels.
        """
        self._item_width = width
        self._item_height = height
        self._delegate.setItemSize(width, height)
        grid_size = QSize(width, height)
        for row in self._sections:
            row.list_view.setGridSize(grid_size)
        self._recomputeAllHeights()

    def setHeaderHeight(self, height: int) -> None:
        """Advisory hint for the section header height.

        The actual height is auto-detected from the widget's layout
        in ``_afterLayout``.  This method updates the fallback value
        used before the first layout pass completes.

        Args:
            height: Fallback header height in pixels.
        """
        self._header_height = height

    def setPhysicsManager(self, manager: PhysicsConversionManager) -> None:
        """Sets the physics conversion manager for keV display.

        Args:
            manager: The conversion manager to use.
        """
        self._delegate._physics = manager

    def setDisplayEnergyInKev(self, enabled: bool) -> None:
        """Sets whether energy labels use keV or ADU.

        Args:
            enabled: True for keV display, False for raw ADU.
        """
        self._delegate._displayKeV = enabled

    def setClassificationThreshold(self, threshold: float) -> None:
        """Sets the confidence threshold for classification badges.

        Args:
            threshold: Min confidence for positive classification.
        """
        self._delegate._threshold = threshold

    def setColumnConstraints(self, default_cols: int, max_cols: int) -> None:
        """Sets minimum/maximum width based on column counts.

        Args:
            default_cols: Number of columns visible by default.
            max_cols: Maximum number of visible columns.
        """
        self._max_cols = max_cols
        grid_w = self._item_width
        spacing = 4
        self.setMinimumWidth(default_cols * (grid_w + spacing))
        self.setMaximumWidth(max_cols * (grid_w + spacing))

    def setPrefetchCount(self, count: int) -> None:
        """Sets the number of thumbnails to pre-fetch on initial load.

        Args:
            count: Number of thumbnails to eagerly request.
        """
        self._prefetch_count = max(3, count)

    def setSmoothScaling(self, enabled: bool) -> None:
        """Enable or disable smooth (anti-aliased) thumbnail scaling.

        Args:
            enabled: True for bilinear interpolation, False for
                nearest-neighbor (sharp pixels).
        """
        self._delegate.setSmoothScaling(enabled)

    # ------------------------------------------------------------------ #
    # Event data management                                                #
    # ------------------------------------------------------------------ #

    def setEvents(self, events: List[Cluster]) -> None:
        """Populates the grid with lazy placeholder items grouped by section.

        Thumbnails are not generated here — they are loaded
        asynchronously once the items scroll into the viewport.

        Args:
            events: List of Cluster objects to display.
        """
        self._clearSections()
        sections = group_clusters(events)
        for info in sections:
            self._addSection(info, events)
        self._setAllNavigationStates()
        QTimer.singleShot(0, self._afterLayout)
        self._visibleRangeTracker.scheduleCheck()
        self.prefetchRequested.emit(self._prefetch_count)

    def _clearSections(self) -> None:
        """Removes all section widgets from the content layout."""
        self._stickyOverlay.hide()
        for row in self._sections:
            row.header_widget.setParent(None)
            row.list_view.setParent(None)
            row.header_widget.deleteLater()
            row.list_view.deleteLater()
        self._sections.clear()

    def _buildItem(self, cluster: Cluster) -> QStandardItem:
        """Builds one non-editable grid item carrying its source cluster."""
        item = QStandardItem()
        item.setData(cluster, CLUSTER_ROLE)
        item.setEditable(False)
        return item

    def _addSection(
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
        header = self._buildSectionHeader(info)
        model = QStandardItemModel()
        view = self._buildSectionListView()
        view.setModel(model)

        start = info.start_index - base_offset
        for cluster in events[start: start + info.count]:
            model.appendRow(self._buildItem(cluster))

        view.setFixedHeight(self._computeListViewHeight(info.count))
        self._contentLayout.addWidget(header)
        self._contentLayout.addWidget(view)
        self._sections.append(_SectionRow(info, header_widget=header,
                                          list_view=view, model=model))

    def _insertSectionAtFront(
        self,
        info: SectionInfo,
        events: List[Cluster],
        base_offset: int,
    ) -> None:
        """Creates one section and inserts it at the very top of the layout.

        Mirror of ``_addSection`` for ``prependEvents`` — used when a
        backward page fetch introduces clusters earlier than anything
        currently resident.
        """
        header = self._buildSectionHeader(info)
        model = QStandardItemModel()
        view = self._buildSectionListView()
        view.setModel(model)

        start = info.start_index - base_offset
        for cluster in events[start: start + info.count]:
            model.appendRow(self._buildItem(cluster))

        view.setFixedHeight(self._computeListViewHeight(info.count))
        self._contentLayout.insertWidget(0, header)
        self._contentLayout.insertWidget(1, view)
        self._sections.insert(0, _SectionRow(info, header_widget=header,
                                             list_view=view, model=model))

    @property
    def windowStart(self) -> int:
        """Global index of the first currently-resident cluster."""
        return self._sections[0].info.start_index if self._sections else 0

    def _setAllNavigationStates(self) -> None:
        """Set prev/next button states on all section headers."""
        total = len(self._sections)
        for i, row in enumerate(self._sections):
            row.header_widget.setNavigationState(
                has_previous=i > 0,
                has_next=i < total - 1,
            )

    def _scrollToSection(self, section_index: int) -> None:
        """Scroll so the target section's header is at the top."""
        if section_index < 0 or section_index >= len(self._sections):
            return
        header = self._sections[section_index].header_widget
        header_y = header.mapTo(self._contentWidget, QPoint(0, 0)).y()
        self._scrollArea.verticalScrollBar().setValue(header_y)

    def _afterLayout(self) -> None:
        """Deferred call after Qt finishes laying out sections."""
        if self._sections:
            hint = self._sections[0].header_widget.sizeHint().height()
            if hint > 0:
                self._header_height = hint
            self._stickyOverlay.setFixedHeight(self._header_height)
        self._recomputeAllHeights()
        self._stickyOverlay.update()
        self._visibleRangeTracker.scheduleCheck()

    def updateThumbnail(self, index: int, pixmap: QPixmap) -> None:
        """Update a single cell's thumbnail and trigger repaint.

        Args:
            index: Flat row index of the item to update.
            pixmap: The rendered thumbnail pixmap.
        """
        if not self._sections:
            return
        try:
            sec_idx, local_idx = flat_index_to_section(
                [r.info for r in self._sections], index,
            )
        except IndexError:
            return
        item = self._sections[sec_idx].model.item(local_idx)
        if item is not None:
            item.setData(pixmap, THUMBNAIL_ROLE)

    def setSelectedIndex(self, index: int) -> None:
        """Programmatically selects a grid item.

        Args:
            index: Flat index to select, or -1 to clear selection.
        """
        if index < 0:
            for row in self._sections:
                row.list_view.clearSelection()
            return
        if not self._sections:
            return
        try:
            sec_idx, local_idx = flat_index_to_section(
                [r.info for r in self._sections], index,
            )
        except IndexError:
            return
        for i, row in enumerate(self._sections):
            if i != sec_idx:
                row.list_view.clearSelection()
        model_index = self._sections[sec_idx].model.index(local_idx, 0)
        self._sections[sec_idx].list_view.setCurrentIndex(model_index)

    def clear(self) -> None:
        """Removes all items from the grid."""
        self._clearSections()

    # ------------------------------------------------------------------ #
    # Layout & height computation                                          #
    # ------------------------------------------------------------------ #

    def _computeListViewHeight(self, count: int) -> int:
        """Calculate the pixel height needed to display *count* items.

        Qt's icon-mode layout with ``setGridSize`` places items at
        exact grid-size intervals — the ``spacing`` value only adds
        visual padding inside the cell, not to the stride.
        """
        if count == 0:
            return 0
        content_w = self._contentWidget.width()
        if content_w <= 0:
            content_w = self.width()
        grid_w = self._item_width
        grid_h = self._item_height
        cols = min(max(1, content_w // grid_w), self._max_cols)
        rows = math.ceil(count / cols)
        return rows * grid_h

    def _recomputeAllHeights(self) -> None:
        """Recalculate fixed heights for every section list view."""
        for row in self._sections:
            row.list_view.setFixedHeight(
                self._computeListViewHeight(row.info.count),
            )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._recomputeAllHeights()
        self._stickyOverlay.setFixedWidth(self.width())
        self._stickyOverlay.update()
        self._visibleRangeTracker.scheduleCheck()

    # ------------------------------------------------------------------ #
    # Sticky header overlay                                                #
    # ------------------------------------------------------------------ #

    def _onScrollChanged(self) -> None:
        """Handles scroll bar value changes."""
        self._stickyOverlay.update()
        self._visibleRangeTracker.scheduleCheck()

    # ------------------------------------------------------------------ #
    # Visible range detection                                              #
    # ------------------------------------------------------------------ #

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Detect scroll, resize, show and paint on the viewport."""
        etype = event.type()
        if etype in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Paint,
            QEvent.Type.Scroll,
        ):
            self._visibleRangeTracker.scheduleCheck()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------ #
    # Click handling                                                       #
    # ------------------------------------------------------------------ #

    def _onItemClicked(
        self, view: QListView, index: QModelIndex,
    ) -> None:
        """Translates a per-section click into a flat-index signal."""
        section_index = self._indexOfListView(view)
        if section_index < 0:
            return
        for i, row in enumerate(self._sections):
            if i != section_index:
                row.list_view.clearSelection()
        flat = self._sections[section_index].info.start_index + index.row()
        self.eventSelected.emit(flat)

    # ------------------------------------------------------------------ #
    # Sliding-window paging: append / prepend / evict                      #
    # ------------------------------------------------------------------ #

    def appendEvents(self, new_events: List[Cluster]) -> None:
        """Appends a newly-fetched page to the tail of the grid.

        Does not rebuild existing sections — preserves scroll position
        and already-rendered thumbnails. No scroll compensation is
        needed since content is added below the viewport.

        Args:
            new_events: The newly fetched chunk only (not the full
                list of currently-resident events).
        """
        if not new_events:
            return
        self._pager.append(new_events)
        self._setAllNavigationStates()
        self._stickyOverlay.update()
        QTimer.singleShot(0, self._afterLayout)
        self._visibleRangeTracker.scheduleCheck()

    def prependEvents(self, new_events: List[Cluster]) -> None:
        """Prepends a newly-fetched page to the head of the grid.

        Inserts above the current viewport and compensates the
        scrollbar immediately (heights here are pure functions of
        stored width/row-count, not a Qt ``sizeHint()``, so no
        layout-pass deferral is needed before adjusting it) so the
        user's visual position doesn't jump.

        Args:
            new_events: The newly fetched chunk only (not the full
                list of currently-resident events).
        """
        if not new_events:
            return
        added_height = self._pager.prepend(new_events)
        self._setAllNavigationStates()
        scrollbar = self._scrollArea.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + added_height)
        QTimer.singleShot(0, self._afterLayout)
        self._visibleRangeTracker.scheduleCheck()

    def evictFront(self, global_offset: int, global_count: int) -> None:
        """Removes leading rows in ``[global_offset, global_offset + global_count)``.

        Compensates the scrollbar so content does not visually jump
        upward — eviction only follows a forward page append, so the
        evicted range is always above (or starting at) the viewport.

        Args:
            global_offset: Global start of the evicted range.
            global_count: Row count of the evicted range.
        """
        if not self._sections or global_count <= 0:
            return
        removed_height = self._pager.evictFront(global_count)
        self._setAllNavigationStates()
        self._stickyOverlay.update()
        scrollbar = self._scrollArea.verticalScrollBar()
        scrollbar.setValue(max(0, scrollbar.value() - removed_height))

    def evictBack(self, global_offset: int, global_count: int) -> None:
        """Removes trailing rows in ``[global_offset, global_offset + global_count)``.

        No scrollbar compensation: eviction-back only follows a
        backward page fetch, which only triggers once the user has
        scrolled toward the front — the evicted range is always below
        the viewport.

        Args:
            global_offset: Global start of the evicted range.
            global_count: Row count of the evicted range.
        """
        if not self._sections or global_count <= 0:
            return
        self._pager.evictBack(global_count)
        self._setAllNavigationStates()
        self._stickyOverlay.update()
