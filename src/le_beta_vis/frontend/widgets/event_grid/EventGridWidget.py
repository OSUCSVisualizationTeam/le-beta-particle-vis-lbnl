from typing import List, Optional

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
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
    THUMBNAIL_ROLE,
    _EventItemDelegate,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionController import (
    _EventGridSectionController,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionGrouping import (
    flat_index_to_section,
    group_clusters,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionRow import (
    _SectionRow,
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


class EventGridWidget(QWidget):
    """Displays cluster events as a responsive, sectioned grid of thumbnails.

    Clusters are grouped by observation date and FITS filename.
    Each section has a header that pins to the top of the scrollable
    area while the user scrolls through its contents.

    Signals:
        eventSelected(int): Emitted with the flat event index on click.
        visibleRangeChanged(int, int): First and last visible flat indices.
        prefetchRequested(int): Emitted on ``setEvents`` with prefetch count.
        pageJumpRequested(int, int): Emitted when a header's skip
            button is clicked — (anchor_global_index, direction),
            where direction is -1 (previous page) or +1 (next page).
    """

    eventSelected = Signal(int)
    visibleRangeChanged = Signal(int, int)
    prefetchRequested = Signal(int)
    pageJumpRequested = Signal(int, int)

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
        self._has_more_backward: bool = False
        self._has_more_forward: bool = False
        self._is_loading: bool = False
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
            has_more_backward_getter=lambda: self._has_more_backward,
            has_more_forward_getter=lambda: self._has_more_forward,
            on_page_jump=self.pageJumpRequested.emit,
            is_loading_getter=lambda: self._is_loading,
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
        self._sectionController = _EventGridSectionController(
            sections=self._sections,
            content_layout=self._contentLayout,
            content_widget=self._contentWidget,
            delegate=self._delegate,
            item_width_getter=lambda: self._item_width,
            item_height_getter=lambda: self._item_height,
            max_cols_getter=lambda: self._max_cols,
            widget_width_getter=lambda: self.width(),
            on_page_jump=self.pageJumpRequested.emit,
            on_navigate_to_self=self._scrollToSection,
            on_item_selected=self.eventSelected.emit,
        )
        self._pager = _SlidingWindowPager(
            sections=self._sections,
            header_height_getter=lambda: self._header_height,
            compute_list_view_height=self._sectionController.computeListViewHeight,
            build_item=self._sectionController.buildItem,
            add_section=self._sectionController.addSection,
            insert_section_at_front=self._sectionController.insertSectionAtFront,
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
        self._sectionController.applyGridSize(width, height)

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

    def setEvents(self, events: List[Cluster], window_start: int = 0) -> None:
        """Populates the grid with lazy placeholder items grouped by section.

        Thumbnails are not generated here — they are loaded
        asynchronously once the items scroll into the viewport.

        Args:
            events: List of Cluster objects to display.
            window_start: Global index of ``events[0]``. Defaults to
                0 for the very first load; a page jump anchors the
                resident window elsewhere, and every ``SectionInfo``
                built here must carry a *global* ``start_index`` —
                callers like ``flat_index_to_section`` and the
                section-header skip buttons key off it directly.
        """
        self._stickyOverlay.hide()
        self._sectionController.clearAll()
        sections = group_clusters(events)
        for info in sections:
            info.start_index += window_start
            self._sectionController.addSection(info, events, base_offset=window_start)
        self._refreshNavigationStates()
        QTimer.singleShot(0, self._afterLayout)
        self._visibleRangeTracker.scheduleCheck()
        self.prefetchRequested.emit(self._prefetch_count)

    @property
    def windowStart(self) -> int:
        """Global index of the first currently-resident cluster."""
        return self._sections[0].info.start_index if self._sections else 0

    def setGlobalPagingState(self, has_more_backward: bool, has_more_forward: bool) -> None:
        """Updates whether a page exists beyond the resident window's edges.

        Args:
            has_more_backward: True if a page exists before the
                window's head.
            has_more_forward: True if a page exists beyond the
                window's tail.
        """
        self._has_more_backward = has_more_backward
        self._has_more_forward = has_more_forward
        self._refreshNavigationStates()

    def setLoading(self, loading: bool) -> None:
        """Disables every section's skip button while a fetch is in flight.

        A spam-clicked skip button can otherwise fire a second
        full-grid rebuild before the first one's fetch and layout
        pass have finished, churning through Qt widget construction/
        ``deleteLater()`` cycles fast enough to crash PySide6.

        Args:
            loading: True to disable all skip-navigation buttons.
        """
        self._is_loading = loading
        self._refreshNavigationStates()
        self._stickyOverlay.update()

    def _refreshNavigationStates(self) -> None:
        """Pushes the current paging/loading state to all section headers."""
        self._sectionController.refreshNavigationStates(
            self._has_more_backward, self._has_more_forward, self._is_loading,
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
        self._sectionController.recomputeAllHeights()
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

    # ------------------------------------------------------------------ #
    # Layout & height computation                                          #
    # ------------------------------------------------------------------ #

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sectionController.recomputeAllHeights()
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
        self._refreshNavigationStates()
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
        self._refreshNavigationStates()
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
        self._refreshNavigationStates()
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
        self._refreshNavigationStates()
        self._stickyOverlay.update()
