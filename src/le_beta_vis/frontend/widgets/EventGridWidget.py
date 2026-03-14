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
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QScroller,
    QScrollerProperties,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.frontend.theme import COLOR_BACKGROUND_SURFACE
from le_beta_vis.frontend.widgets._event_item_delegate import (
    CLUSTER_ROLE,
    THUMBNAIL_ROLE,
    _EventItemDelegate,
)


class EventGridWidget(QWidget):
    """Displays cluster events as a responsive grid of thumbnails.

    Each cell shows a cluster thumbnail with particle type badge
    (top-left) and confidence percentage (top-right).  The grid
    re-flows when the window is resized.

    Signals:
        eventSelected(int): Emitted when a grid item is clicked.
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
        self._prefetch_count: int = 30
        self._initUI()

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._visibilityTimer = QTimer(self)
        self._visibilityTimer.setSingleShot(True)
        self._visibilityTimer.setInterval(50)
        self._visibilityTimer.timeout.connect(self._emitVisibleRange)

        self._trailingTimer = QTimer(self)
        self._trailingTimer.setSingleShot(True)
        self._trailingTimer.setInterval(50)
        self._trailingTimer.timeout.connect(self._emitVisibleRange)

        self._listView = self._buildListView()
        layout.addWidget(self._listView)
        self._configureKineticScrolling(self._listView.viewport())

    def _buildListView(self) -> QListView:
        """Creates and configures the grid's QListView."""
        self._model = QStandardItemModel()
        self._delegate = _EventItemDelegate(
            self._item_width,
            self._item_height,
            self,
        )

        view = QListView()
        view.setModel(self._model)
        view.setItemDelegate(self._delegate)
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setGridSize(QSize(self._item_width, self._item_height))
        view.setUniformItemSizes(True)
        view.setSpacing(4)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet(f"background-color: {COLOR_BACKGROUND_SURFACE};")
        view.clicked.connect(self._onItemClicked)
        view.viewport().installEventFilter(self)
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

    def setGridSize(self, width: int, height: int) -> None:
        """Updates the grid cell dimensions from configuration.

        Args:
            width: Cell width in pixels.
            height: Cell height in pixels.
        """
        self._item_width = width
        self._item_height = height
        self._listView.setGridSize(QSize(width, height))
        self._delegate.setItemSize(width, height)

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

        Constrains the grid width so it displays *default_cols*
        columns by default and never exceeds *max_cols* columns,
        keeping the grid narrow and leaving space for the inspector.

        Args:
            default_cols: Number of columns visible by default.
            max_cols: Maximum number of visible columns.
        """
        grid_w = self._listView.gridSize().width()
        spacing = self._listView.spacing()
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

    def setEvents(self, events: List[Cluster]) -> None:
        """Populates the grid with lazy placeholder items.

        Thumbnails are not generated here — they are loaded
        asynchronously once the items scroll into the viewport.

        Args:
            events: List of Cluster objects to display.
        """
        self._model.clear()
        for cluster in events:
            item = QStandardItem()
            item.setData(cluster, CLUSTER_ROLE)
            item.setEditable(False)
            self._model.appendRow(item)
        self._scheduleVisibilityCheck()
        self.prefetchRequested.emit(self._prefetch_count)

    def updateThumbnail(self, index: int, pixmap: QPixmap) -> None:
        """Update a single cell's thumbnail and trigger repaint.

        Args:
            index: Row index of the item to update.
            pixmap: The rendered thumbnail pixmap.
        """
        if 0 <= index < self._model.rowCount():
            item = self._model.item(index)
            if item is not None:
                item.setData(pixmap, THUMBNAIL_ROLE)

    def setSelectedIndex(self, index: int) -> None:
        """Programmatically selects a grid item.

        Args:
            index: Index to select, or -1 to clear selection.
        """
        if index < 0:
            self._listView.clearSelection()
        elif index < self._model.rowCount():
            model_index = self._model.index(index, 0)
            self._listView.setCurrentIndex(model_index)

    def clear(self) -> None:
        """Removes all items from the grid."""
        self._model.clear()

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
        if self._model.rowCount() == 0:
            return
        viewport = self._listView.viewport()
        vp_w = viewport.width()
        vp_h = viewport.height()
        if vp_w == 0 or vp_h == 0:
            return

        first_row = self._findFirstVisibleRow(viewport)
        last_row = self._findLastVisibleRow(first_row, vp_w, vp_h)

        self.visibleRangeChanged.emit(first_row, last_row)

    def _findFirstVisibleRow(self, viewport: QWidget) -> int:
        """Finds the row index of the first visible item."""
        first_idx = self._listView.indexAt(viewport.rect().topLeft())
        return first_idx.row() if first_idx.isValid() else 0

    def _findLastVisibleRow(self, first_row: int, vp_w: int, vp_h: int) -> int:
        """Probes the viewport to find the row index of the last visible item."""
        grid_w = self._listView.gridSize().width() + self._listView.spacing()
        grid_h = self._listView.gridSize().height() + self._listView.spacing()
        cols = max(1, vp_w // grid_w)

        # Probe the bottom edge of the viewport at the center of each
        # column to find the actual last visible item.  This is more
        # reliable than a pure arithmetic estimate because it uses
        # QListView's own layout engine.
        y_bottom = vp_h - 1
        last_row = self._probeRowAtY(y_bottom, cols, grid_w, vp_w, first_row)

        # If probing missed (bottom pixel landed on spacing), try one
        # grid-row higher to catch the partially visible bottom row.
        if last_row == first_row and self._model.rowCount() > cols:
            y_fallback = max(0, y_bottom - grid_h)
            last_row = self._probeRowAtY(y_fallback, cols, grid_w, vp_w, last_row)
            # Add one visual row to account for the row we stepped back from
            last_row = min(last_row + cols, self._model.rowCount() - 1)

        return last_row

    def _probeRowAtY(self, y: int, cols: int, grid_w: int, vp_w: int, current_last: int) -> int:
        """Probes horizontally across a specific Y coordinate to find the max row index."""
        max_row = current_last
        for col in range(cols):
            x_probe = col * grid_w + grid_w // 2
            if x_probe >= vp_w:
                break
            idx = self._listView.indexAt(QPoint(x_probe, y))
            if idx.isValid() and idx.row() > max_row:
                max_row = idx.row()
        return max_row

    def _onItemClicked(self, index: QModelIndex) -> None:
        self.eventSelected.emit(index.row())
