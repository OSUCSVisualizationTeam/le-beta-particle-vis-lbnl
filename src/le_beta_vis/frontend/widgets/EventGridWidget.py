import math
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import (
    QEvent,
    QMetaObject,
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
from le_beta_vis.frontend.widgets._EventItemDelegate import (
    CLUSTER_ROLE,
    THUMBNAIL_ROLE,
    _EventItemDelegate,
)
from le_beta_vis.frontend.widgets._EventGridSectionGrouping import (
    SectionInfo,
    flat_index_to_section,
    group_clusters,
)
from le_beta_vis.frontend.widgets._EventGridSectionHeaderWidget import (
    EventGridSectionHeaderWidget,
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
        self._overlayPrevConn: Optional[QMetaObject.Connection] = None
        self._overlayNextConn: Optional[QMetaObject.Connection] = None
        self._overlaySelfConn: Optional[QMetaObject.Connection] = None
        self._initUI()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _initUI(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._visibilityTimer = QTimer(self)
        self._visibilityTimer.setSingleShot(True)
        self._visibilityTimer.setInterval(50)
        self._visibilityTimer.timeout.connect(self._emitVisibleRange)

        self._trailingTimer = QTimer(self)
        self._trailingTimer.setSingleShot(True)
        self._trailingTimer.setInterval(50)
        self._trailingTimer.timeout.connect(self._emitVisibleRange)

        self._scrollArea = self._buildScrollArea()
        root.addWidget(self._scrollArea)

        self._stickyOverlay = self._buildStickyOverlay()
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

        self._contentWidget = QWidget()
        self._contentLayout = QVBoxLayout(self._contentWidget)
        self._contentLayout.setContentsMargins(0, 0, 0, 0)
        self._contentLayout.setSpacing(0)
        area.setWidget(self._contentWidget)
        return area

    def _buildStickyOverlay(self) -> EventGridSectionHeaderWidget:
        """Creates the floating header that pins above the scroll area."""
        overlay = EventGridSectionHeaderWidget(parent=self)
        overlay.hide()
        overlay.raise_()
        return overlay

    def _buildSectionHeader(
        self, info: SectionInfo, section_index: int,
    ) -> EventGridSectionHeaderWidget:
        """Creates a section header widget for *info* with navigation."""
        header = EventGridSectionHeaderWidget()
        date = info.date_part if info.date_part else self.tr("Unknown Date")
        file = info.file_part if info.file_part else self.tr("Unknown File")
        header.setDateText(date)
        header.setFileText(file)
        header.navigatePrevious.connect(
            lambda s=section_index: self._scrollToSection(s - 1),
        )
        header.navigateNext.connect(
            lambda s=section_index: self._scrollToSection(s + 1),
        )
        header.navigateToSelf.connect(
            lambda s=section_index: self._scrollToSection(s),
        )
        return header

    def _buildSectionListView(self, section_index: int) -> QListView:
        """Creates a per-section QListView with shared delegate."""
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
        view.clicked.connect(
            lambda idx, s=section_index: self._onSectionItemClicked(s, idx)
        )
        return view

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
        for idx, info in enumerate(sections):
            self._addSection(idx, info, events)
        self._setAllNavigationStates()
        QTimer.singleShot(0, self._afterLayout)
        self._scheduleVisibilityCheck()
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

    def _addSection(
        self,
        section_index: int,
        info: SectionInfo,
        events: List[Cluster],
    ) -> None:
        """Creates and adds one section (header + list view) to the layout."""
        header = self._buildSectionHeader(info, section_index)
        model = QStandardItemModel()
        view = self._buildSectionListView(section_index)
        view.setModel(model)

        start = info.start_index
        for cluster in events[start: start + info.count]:
            item = QStandardItem()
            item.setData(cluster, CLUSTER_ROLE)
            item.setEditable(False)
            model.appendRow(item)

        view.setFixedHeight(self._computeListViewHeight(info.count))
        self._contentLayout.addWidget(header)
        self._contentLayout.addWidget(view)
        self._sections.append(_SectionRow(info, header_widget=header,
                                          list_view=view, model=model))

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

    def _reconnectOverlaySignals(self, active_idx: int) -> None:
        """Disconnect and reconnect sticky overlay navigation signals."""
        if self._overlayPrevConn is not None:
            self._stickyOverlay.navigatePrevious.disconnect(
                self._overlayPrevConn,
            )
        if self._overlayNextConn is not None:
            self._stickyOverlay.navigateNext.disconnect(
                self._overlayNextConn,
            )
        if self._overlaySelfConn is not None:
            self._stickyOverlay.navigateToSelf.disconnect(
                self._overlaySelfConn,
            )
        self._overlayPrevConn = self._stickyOverlay.navigatePrevious.connect(
            lambda: self._scrollToSection(active_idx - 1),
        )
        self._overlayNextConn = self._stickyOverlay.navigateNext.connect(
            lambda: self._scrollToSection(active_idx + 1),
        )
        self._overlaySelfConn = self._stickyOverlay.navigateToSelf.connect(
            lambda: self._scrollToSection(active_idx),
        )

    def _afterLayout(self) -> None:
        """Deferred call after Qt finishes laying out sections."""
        if self._sections:
            hint = self._sections[0].header_widget.sizeHint().height()
            if hint > 0:
                self._header_height = hint
            self._stickyOverlay.setFixedHeight(self._header_height)
        self._recomputeAllHeights()
        self._updateStickyOverlay()
        self._scheduleVisibilityCheck()

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
        self._updateStickyOverlay()
        self._scheduleVisibilityCheck()

    # ------------------------------------------------------------------ #
    # Sticky header overlay                                                #
    # ------------------------------------------------------------------ #

    def _onScrollChanged(self) -> None:
        """Handles scroll bar value changes."""
        self._updateStickyOverlay()
        self._scheduleVisibilityCheck()

    def _updateStickyOverlay(self) -> None:
        """Position the sticky overlay based on the current scroll offset."""
        if not self._sections:
            self._stickyOverlay.hide()
            return

        vp_h = self._scrollArea.viewport().height()
        content_h = self._contentWidget.height()
        if content_h <= vp_h:
            self._stickyOverlay.hide()
            return

        scroll_y = self._scrollArea.verticalScrollBar().value()
        active_idx = self._findActiveSectionIndex(scroll_y)
        if active_idx < 0:
            self._stickyOverlay.hide()
            return

        self._positionOverlay(active_idx, scroll_y)

    def _findActiveSectionIndex(self, scroll_y: int) -> int:
        """Return the index of the section whose header has scrolled past the top."""
        active = -1
        for i, row in enumerate(self._sections):
            header_y = row.header_widget.mapTo(self._contentWidget, QPoint(0, 0)).y()
            if header_y <= scroll_y:
                active = i
            else:
                break
        return active

    def _positionOverlay(self, active_idx: int, scroll_y: int) -> None:
        """Set the overlay text, geometry, navigation state, and visibility."""
        row = self._sections[active_idx]
        date = row.info.date_part if row.info.date_part else self.tr("Unknown Date")
        file = row.info.file_part if row.info.file_part else self.tr("Unknown File")
        self._stickyOverlay.setDateText(date)
        self._stickyOverlay.setFileText(file)
        self._stickyOverlay.setFixedWidth(self.width())

        self._reconnectOverlaySignals(active_idx)
        self._stickyOverlay.setNavigationState(
            has_previous=active_idx > 0,
            has_next=active_idx < len(self._sections) - 1,
        )

        y_pos = 0
        if active_idx + 1 < len(self._sections):
            next_header = self._sections[active_idx + 1].header_widget
            next_y = next_header.mapTo(self._contentWidget, QPoint(0, 0)).y()
            push = next_y - scroll_y - self._header_height
            if push < 0:
                y_pos = push

        self._stickyOverlay.move(0, max(-self._header_height, y_pos))
        self._stickyOverlay.raise_()
        self._stickyOverlay.show()

    # ------------------------------------------------------------------ #
    # Visible range detection                                              #
    # ------------------------------------------------------------------ #

    def _scheduleVisibilityCheck(self) -> None:
        """Schedule visible-range emission with leading + trailing edge debounce."""
        if not self._visibilityTimer.isActive():
            self._visibilityTimer.start()
        self._trailingTimer.start()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Detect scroll, resize, show and paint on the viewport."""
        etype = event.type()
        if etype in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Paint,
            QEvent.Type.Scroll,
        ):
            self._scheduleVisibilityCheck()
        return super().eventFilter(obj, event)

    def _emitVisibleRange(self) -> None:
        """Calculate the visible item range and emit visibleRangeChanged."""
        if not self._sections:
            return
        vp_h = self._scrollArea.viewport().height()
        if vp_h <= 0:
            return

        scroll_y = self._scrollArea.verticalScrollBar().value()
        first = self._flatIndexAtY(scroll_y)
        last = self._flatIndexAtY(scroll_y + vp_h)
        self.visibleRangeChanged.emit(first, last)

    def _flatIndexAtY(self, y: int) -> int:
        """Map a content-widget Y coordinate to the closest flat event index."""
        if not self._sections:
            return 0

        grid_w = self._item_width
        grid_h = self._item_height
        content_w = self._contentWidget.width()
        cols = min(max(1, content_w // grid_w), self._max_cols) if content_w > 0 else 1
        total = self._sections[-1].info.start_index + self._sections[-1].info.count

        for i, row in enumerate(self._sections):
            header_y = row.header_widget.mapTo(
                self._contentWidget, QPoint(0, 0),
            ).y()
            section_top = header_y + self._header_height
            section_h = row.list_view.height()
            section_bottom = section_top + section_h

            if y < section_top:
                return row.info.start_index
            if y < section_bottom:
                local_y = y - section_top
                local_row = min(local_y // grid_h, math.ceil(row.info.count / cols) - 1)
                local_idx = min(int(local_row * cols), row.info.count - 1)
                return row.info.start_index + local_idx

        return max(0, total - 1)

    # ------------------------------------------------------------------ #
    # Click handling                                                       #
    # ------------------------------------------------------------------ #

    def _onSectionItemClicked(
        self, section_index: int, index: QModelIndex,
    ) -> None:
        """Translates a per-section click into a flat-index signal."""
        for i, row in enumerate(self._sections):
            if i != section_index:
                row.list_view.clearSelection()
        flat = self._sections[section_index].info.start_index + index.row()
        self.eventSelected.emit(flat)
