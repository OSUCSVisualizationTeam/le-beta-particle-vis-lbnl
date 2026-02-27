from PySide6.QtCore import QMetaObject, QSize, Qt, Slot
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..fitsconverters import Colormap
from ..viewmodels.RawDataViewModel import (
    ActiveTool,
    ClusteringState,
    RawDataViewModel,
)
from ..widgets.BoxSelectionGraphicsItem import BoxSelectionGraphicsItem
from ..widgets.CaptureGraphicsView import CaptureGraphicsView
from ..widgets.MagnifierGraphicsItem import MagnifierGraphicsItem
from ..widgets.ClusteredEventWidget import ClusteredEventWidget
from ..widgets.ClusteringProgressOverlay import ClusteringProgressOverlay
from ..widgets.VerticalRangeControl import VerticalRangeControl
from .MosaicView import MosaicView


class _Style:
    LEFT_TOOLBAR = (
        "background-color: #2d2d2d; border-right: 1px solid #3d3d3d;"
    )
    LEFT_TOOLBAR_BUTTON = "font-weight: bold; color: #ffffff;"
    LEFT_TOOLBAR_DIVIDER = "background-color: #555555;"
    ZOOM_IN = "font-size: 20px; font-weight: bold; color: #ffffff;"
    ZOOM_OUT = "font-size: 20px; font-weight: bold; color: #ffffff;"
    GRAPHICS_VIEW = "background-color: #000; border: none;"
    STATUS_BAR = (
        "background-color: #1e1e1e; color: #cccccc;"
        " font-size: 12px; padding-left: 8px;"
    )
    RIGHT_SIDEBAR = """
        QFrame { background-color: #f0f0f0; border-left: 1px solid #ccc; }
        QGroupBox { color: #000000; }
        QGroupBox::title { color: #000000; }
        QLabel { color: #000000; background: transparent; }
        QPushButton { color: #000000; }
        QComboBox { color: #000000; background-color: #ffffff; }
        QComboBox QAbstractItemView {
            color: #000000; background-color: #ffffff;
        }
        QDoubleSpinBox { color: #000000; background-color: #ffffff; }
        QListWidget {
            color: #000000;
            background-color: #f4f4f4;
            alternate-background-color: #e8e8e8;
        }
        QListWidget::item:selected { background-color: #b3d4fc; }
    """


class RawDataView(QWidget):
    def __init__(self, viewModel: RawDataViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        """Initializes the UI components and layout."""
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self._setupMosaicView()
        self._setupMainBody()

    def _setupMosaicView(self):
        self.mosaicView = MosaicView(self.viewModel.mosaicViewModel)
        self.mainLayout.addWidget(self.mosaicView)
        self.mosaicView.setVisible(False)

    def _setupMainBody(self):
        self.bodyWidget = QWidget()
        self.bodyLayout = QHBoxLayout(self.bodyWidget)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(0)
        self.mainLayout.addWidget(self.bodyWidget)

        self._setupLeftToolbar()
        self._setupCenterImageArea()
        self._setupRightSidebar()

    def _setupLeftToolbar(self):
        self.leftToolbar = QFrame()
        self.leftToolbar.setFixedWidth(100)
        self.leftToolbar.setStyleSheet(_Style.LEFT_TOOLBAR)
        layout = QVBoxLayout(self.leftToolbar)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        btn_size = QSize(40, 40)
        tool_btn_style = _Style.LEFT_TOOLBAR_BUTTON

        self._setupToolButtons(layout, btn_size, tool_btn_style)

        layout.addWidget(self._createDivider(), 0, Qt.AlignHCenter)

        self._setupZoomButtons(layout, btn_size)

        layout.addWidget(self._createDivider(), 0, Qt.AlignHCenter)
        layout.addSpacing(10)

        self.rangeControl = VerticalRangeControl(abs_min=0.0, abs_max=1.0)
        self.rangeControl.setVisible(False)
        self.rangeControl.rangeChanged.connect(self.onRangeChanged)
        layout.addWidget(self.rangeControl, 0, Qt.AlignHCenter)

        self.bodyLayout.addWidget(self.leftToolbar)

    def _setupToolButtons(
        self, layout: QVBoxLayout, btn_size: QSize, style: str
    ):
        """Creates the Pointer, Magnifier, and Box Select tool buttons."""
        self._toolButtonGroup = QButtonGroup(self)
        self._toolButtonGroup.setExclusive(True)

        # Pointer
        self.btnPointer = QToolButton()
        self.btnPointer.setIcon(self._createPointerIcon())
        self.btnPointer.setToolTip(
            self.tr("Pointer: Select and Pan")
        )
        self.btnPointer.setCheckable(True)
        self.btnPointer.setChecked(True)
        self.btnPointer.setFixedSize(btn_size)
        self.btnPointer.setStyleSheet(style)
        self.btnPointer.clicked.connect(
            lambda: self.viewModel.setActiveTool(ActiveTool.POINTER)
        )
        self._toolButtonGroup.addButton(self.btnPointer)
        layout.addWidget(self.btnPointer, 0, Qt.AlignHCenter)

        # Magnifier
        self.btnMagnifier = QToolButton()
        self.btnMagnifier.setIcon(self._createMagnifierIcon())
        self.btnMagnifier.setToolTip(
            self.tr("Magnifier: Inspect pixels in detail")
        )
        self.btnMagnifier.setCheckable(True)
        self.btnMagnifier.setFixedSize(btn_size)
        self.btnMagnifier.setStyleSheet(style)
        self.btnMagnifier.clicked.connect(
            lambda: self.viewModel.setActiveTool(ActiveTool.MAGNIFIER)
        )
        self._toolButtonGroup.addButton(self.btnMagnifier)
        layout.addWidget(self.btnMagnifier, 0, Qt.AlignHCenter)

        # Box Select
        self.btnBoxSelect = QToolButton()
        self.btnBoxSelect.setIcon(self._createBoxSelectIcon())
        self.btnBoxSelect.setToolTip(self.tr("Region Of Interest"))
        self.btnBoxSelect.setCheckable(True)
        self.btnBoxSelect.setFixedSize(btn_size)
        self.btnBoxSelect.setStyleSheet(style)
        self.btnBoxSelect.clicked.connect(
            lambda: self.viewModel.setActiveTool(ActiveTool.BOX_SELECT)
        )
        self._toolButtonGroup.addButton(self.btnBoxSelect)
        layout.addWidget(self.btnBoxSelect, 0, Qt.AlignHCenter)

    def _createPointerIcon(self) -> QIcon:
        """Creates a crosshair/target icon for the Pointer tool."""
        icon = QIcon.fromTheme("crosshairs")
        if not icon.isNull():
            return icon

        size = 40
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(2)
        painter.setPen(pen)
        cx, cy = size // 2, size // 2
        r = 10
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        arm = 6
        painter.drawLine(cx, cy - r - arm, cx, cy - r)
        painter.drawLine(cx, cy + r, cx, cy + r + arm)
        painter.drawLine(cx - r - arm, cy, cx - r, cy)
        painter.drawLine(cx + r, cy, cx + r + arm, cy)
        painter.end()
        return QIcon(pixmap)

    def _createMagnifierIcon(self) -> QIcon:
        """Creates a magnifier icon from theme or painted fallback."""
        icon = QIcon.fromTheme("edit-find")
        if not icon.isNull():
            return icon

        pixmap = QPixmap(40, 40)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPixelSize(24)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "\U0001F50D")
        painter.end()
        return QIcon(pixmap)

    def _createBoxSelectIcon(self) -> QIcon:
        """Creates a dashed rectangle icon for the Box Select tool."""
        size = 40
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        margin = 8
        painter.drawRect(margin, margin, size - 2 * margin, size - 2 * margin)
        # Corner handles
        handle = 4
        corners = [
            (margin, margin),
            (size - margin, margin),
            (margin, size - margin),
            (size - margin, size - margin),
        ]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        for cx, cy in corners:
            painter.drawRect(
                cx - handle // 2, cy - handle // 2, handle, handle
            )
        painter.end()
        return QIcon(pixmap)

    def _setupZoomButtons(self, layout: QVBoxLayout, btn_size: QSize):
        """Creates the Zoom In, Reset, and Zoom Out buttons."""
        # Zoom In
        self.btnZoomIn = QToolButton()
        self.btnZoomIn.setText("+")
        self.btnZoomIn.setToolTip(self.tr("Zoom In"))
        self.btnZoomIn.setFixedSize(btn_size)
        self.btnZoomIn.setStyleSheet(_Style.ZOOM_IN)
        self.btnZoomIn.clicked.connect(self.viewModel.zoomIn)
        layout.addWidget(self.btnZoomIn, 0, Qt.AlignHCenter)

        # Reset Zoom
        self.btnZoomReset = QToolButton()
        self.btnZoomReset.setText("1x")
        self.btnZoomReset.setToolTip(self.tr("Reset Zoom (1:1)"))
        self.btnZoomReset.setFixedSize(btn_size)
        self.btnZoomReset.setStyleSheet(_Style.LEFT_TOOLBAR_BUTTON)
        self.btnZoomReset.clicked.connect(self.viewModel.resetZoom)
        layout.addWidget(self.btnZoomReset, 0, Qt.AlignHCenter)

        # Zoom Out
        self.btnZoomOut = QToolButton()
        self.btnZoomOut.setText("-")
        self.btnZoomOut.setToolTip(self.tr("Zoom Out"))
        self.btnZoomOut.setFixedSize(btn_size)
        self.btnZoomOut.setStyleSheet(_Style.ZOOM_OUT)
        self.btnZoomOut.clicked.connect(self.viewModel.zoomOut)
        layout.addWidget(self.btnZoomOut, 0, Qt.AlignHCenter)

    def _createDivider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(_Style.LEFT_TOOLBAR_DIVIDER)
        line.setFixedWidth(80)
        return line

    def _setupCenterImageArea(self):
        centerContainer = QWidget()
        centerLayout = QVBoxLayout(centerContainer)
        centerLayout.setContentsMargins(0, 0, 0, 0)
        centerLayout.setSpacing(0)

        self.scene = QGraphicsScene()
        self.graphicsView = CaptureGraphicsView()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setStyleSheet(_Style.GRAPHICS_VIEW)
        self.graphicsView.setAlignment(Qt.AlignCenter)

        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)

        # Magnifier overlay (starts hidden)
        self._magnifierItem = MagnifierGraphicsItem(
            fixedDisplaySize=127,
            initialMagnificationFactor=3.0,
        )
        self._magnifierItem.setUnitLabel(self.tr("keV"))
        self._magnifierItem.setVisible(False)
        if self.viewModel.showToolHints:
            self._magnifierItem.setHintLines([
                self.tr("Arrow keys: fine movement"),
                self.tr("Scroll wheel: zoom in/out"),
            ])
        self.scene.addItem(self._magnifierItem)

        # Box selection overlay (starts hidden)
        self._boxSelectionItem = BoxSelectionGraphicsItem()
        self._boxSelectionItem.setColor(self.viewModel.boxSelectColor)
        self._boxSelectionItem.setBorderWidth(
            self.viewModel.boxSelectBorderWidth
        )
        self._boxSelectionItem.setVisible(False)
        self.scene.addItem(self._boxSelectionItem)

        centerLayout.addWidget(self.graphicsView)

        # Status bar for pointer pixel inspection
        self._statusLabel = QLabel()
        self._statusLabel.setFixedHeight(24)
        self._statusLabel.setStyleSheet(_Style.STATUS_BAR)
        centerLayout.addWidget(self._statusLabel)

        # Activate pointer mode by default
        self.graphicsView.setPointerActive(True)

        # Clustering progress overlay (starts hidden)
        self._clusteringOverlay = ClusteringProgressOverlay(
            centerContainer
        )

        self.bodyLayout.addWidget(centerContainer)

    def _setupRightSidebar(self):
        self.rightSidebar = QFrame()
        self.rightSidebar.setFixedWidth(300)
        self.rightSidebar.setStyleSheet(_Style.RIGHT_SIDEBAR)
        self.rightLayout = QVBoxLayout(self.rightSidebar)
        self.rightLayout.setContentsMargins(10, 10, 10, 10)
        self.rightLayout.setSpacing(15)
        self.rightLayout.setAlignment(Qt.AlignTop)

        self._addVisualizationSection()
        self._addFilteringSection()
        self._addExtractionSection()
        self._addInspectorSection()

        self.bodyLayout.addWidget(self.rightSidebar)

    def _addVisualizationSection(self):
        group = QGroupBox(self.tr("Visualization"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("Colormap")))
        self.cmapSelector = QComboBox()
        self.cmapSelector.addItems([c.value for c in Colormap])
        self.cmapSelector.currentTextChanged.connect(self.onColormapChanged)
        layout.addWidget(self.cmapSelector)
        self.rightLayout.addWidget(group)

    def _addFilteringSection(self):
        group = QGroupBox(self.tr("Filtering Pipeline"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("(Not implemented yet)")))
        self.rightLayout.addWidget(group)

    def _addExtractionSection(self):
        group = QGroupBox(self.tr("Cluster Extraction"))
        layout = QVBoxLayout(group)

        # Sigma Threshold spinner
        layout.addWidget(QLabel(self.tr("Sigma Threshold")))
        self._thresholdSpinBox = QDoubleSpinBox()
        self._thresholdSpinBox.setRange(0.1, 100.0)
        self._thresholdSpinBox.setSingleStep(0.5)
        self._thresholdSpinBox.setDecimals(1)
        self._thresholdSpinBox.setValue(
            self.viewModel.clusteringThreshold
        )
        layout.addWidget(self._thresholdSpinBox)

        # Run Extraction button
        self._btnRunExtraction = QPushButton(
            self.tr("Run Extraction")
        )
        self._btnRunExtraction.setEnabled(False)
        self._btnRunExtraction.clicked.connect(
            self.viewModel.triggerClustering
        )
        layout.addWidget(self._btnRunExtraction)

        self.rightLayout.addWidget(group)

    def _addInspectorSection(self):
        self._clusteredEventWidget = ClusteredEventWidget()
        self._clusteredEventWidget.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Expanding
        )
        self.rightLayout.addWidget(self._clusteredEventWidget)

    def bindViewModel(self):
        """Bind all ViewModel callbacks and View signals."""
        self._bindImageCallbacks()
        self._bindToolCallbacks()
        self._bindGraphicsViewSignals()
        self._bindRoiCallbacks()
        self._bindClusteringCallbacks()

    def _bindImageCallbacks(self):
        """Wire image rendering, scale, mosaic, and range control."""
        def on_image_changed():
            QMetaObject.invokeMethod(
                self, "updateImage", Qt.QueuedConnection
            )

        def on_scale_changed():
            QMetaObject.invokeMethod(
                self, "updateZoom", Qt.QueuedConnection
            )

        self.viewModel.add_image_changed_callback(on_image_changed)
        self.viewModel.mosaicViewModel.add_thumbnails_changed_callback(
            self.updateMosaicVisibility
        )
        self.viewModel.add_scale_changed_callback(on_scale_changed)
        self.updateMosaicVisibility()

        vmin, vmax = self.viewModel.visualizationRange
        self.rangeControl.setValues(vmin, vmax)
        self.rangeControl.setColormap(self.viewModel.colormap)

    def _bindToolCallbacks(self):
        """Wire active tool, magnifier, and pointer hover callbacks."""
        def on_active_tool_changed():
            QMetaObject.invokeMethod(
                self, "_updateActiveTool", Qt.QueuedConnection
            )

        def on_magnifier_state_changed():
            QMetaObject.invokeMethod(
                self, "_updateMagnifierState", Qt.QueuedConnection
            )

        def on_magnifier_position_changed():
            QMetaObject.invokeMethod(
                self, "_updateMagnifierPosition",
                Qt.QueuedConnection,
            )

        def on_pointer_hover_changed():
            QMetaObject.invokeMethod(
                self, "_updatePointerStatus",
                Qt.QueuedConnection,
            )

        self.viewModel.add_active_tool_changed_callback(
            on_active_tool_changed
        )
        self.viewModel.add_magnifier_state_changed_callback(
            on_magnifier_state_changed
        )
        self.viewModel.add_magnifier_position_changed_callback(
            on_magnifier_position_changed
        )
        self.viewModel.add_pointer_hover_changed_callback(
            on_pointer_hover_changed
        )

    def _bindGraphicsViewSignals(self):
        """Connect CaptureGraphicsView Qt signals to handlers."""
        self.graphicsView.pixelHovered.connect(self._onPixelHovered)
        self.graphicsView.pixelNudgeRequested.connect(
            self._onPixelNudged
        )
        self.graphicsView.magnificationDeltaRequested.connect(
            self.viewModel.adjustMagnification
        )
        self.graphicsView.mouseLeft.connect(
            self.viewModel.clearPointerHover
        )
        self.graphicsView.boxSelectionCompleted.connect(
            self._onBoxSelectionCompleted
        )
        self.graphicsView.boxSelectClicked.connect(
            self._onBoxSelectClicked
        )

    def _bindRoiCallbacks(self):
        """Wire ROI change and extraction button refresh callbacks."""
        def on_roi_changed():
            QMetaObject.invokeMethod(
                self, "_updateBoxSelection", Qt.QueuedConnection
            )

        self.viewModel.add_roi_changed_callback(on_roi_changed)

        self.viewModel.add_active_tool_changed_callback(
            lambda: QMetaObject.invokeMethod(
                self, "_refreshExtractionButton",
                Qt.QueuedConnection,
            )
        )
        self.viewModel.add_roi_changed_callback(
            lambda: QMetaObject.invokeMethod(
                self, "_refreshExtractionButton",
                Qt.QueuedConnection,
            )
        )

    def _bindClusteringCallbacks(self):
        """Wire clustering state, progress, error, and cancel callbacks.

        Uses Qt.AutoConnection so the overlay shows immediately when
        triggerClustering runs on the main thread, while still queuing
        safely from the extractor background thread.
        """
        def on_clustering_state_changed():
            QMetaObject.invokeMethod(
                self, "_updateClusteringState",
                Qt.AutoConnection,
            )

        self.viewModel.add_clustering_state_changed_callback(
            on_clustering_state_changed
        )

        def on_clustering_progress():
            QMetaObject.invokeMethod(
                self, "_updateClusteringProgress",
                Qt.AutoConnection,
            )

        self.viewModel.add_clustering_progress_callback(
            on_clustering_progress
        )

        self._clusteringOverlay.cancelRequested.connect(
            self.viewModel.cancelClustering
        )

        def on_clustering_error():
            QMetaObject.invokeMethod(
                self, "_showClusteringError",
                Qt.QueuedConnection,
            )

        self.viewModel.add_clustering_error_callback(
            on_clustering_error
        )

        def on_clustering_completed():
            QMetaObject.invokeMethod(
                self, "_updateClusteringResults",
                Qt.AutoConnection,
            )

        self.viewModel.add_clustering_completed_callback(
            on_clustering_completed
        )

        def on_selected_cluster_changed():
            QMetaObject.invokeMethod(
                self, "_updateSelectedCluster",
                Qt.QueuedConnection,
            )

        self.viewModel.add_selected_cluster_changed_callback(
            on_selected_cluster_changed
        )

        self._clusteredEventWidget.clusterSelected.connect(
            self.viewModel.selectCluster
        )
        self._clusteredEventWidget.classifyRequested.connect(
            self.viewModel.classifySelectedCluster
        )
        self._clusteredEventWidget.exportRequested.connect(
            self.viewModel.exportSelectedCluster
        )

    def updateMosaicVisibility(self):
        count = len(self.viewModel.mosaicViewModel.thumbnails)
        self.mosaicView.setVisible(count > 1)

    @Slot()
    def updateImage(self):
        """Thread-safe update of the displayed pixmap."""
        buffer = self.viewModel.currentBuffer
        self.rangeControl.setVisible(buffer is not None)

        if buffer is not None:
            # Convert NumPy Buffer (RGB) -> QImage -> QPixmap
            height, width, channels = buffer.shape
            bytes_per_line = channels * width
            q_img = QImage(
                buffer.data, width, height, bytes_per_line,
                QImage.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(q_img)

            self.pixmapItem.setPixmap(pixmap)
            self.scene.setSceneRect(0, 0, width, height)

            # Ensure zoom is correct for new image
            self.updateZoom()

            # Update Range Control Limits (Sync with ViewModel data range)
            dmin, dmax = self.viewModel.dataRange
            self.rangeControl.setAbsoluteRange(dmin, dmax)

            vmin, vmax = self.viewModel.visualizationRange
            self.rangeControl.setValues(vmin, vmax)
            self.rangeControl.setColormap(self.viewModel.colormap)

            # Update magnifier source data
            self._updateMagnifierSourceData(pixmap)
        else:
            self.pixmapItem.setPixmap(QPixmap())

    def _updateMagnifierSourceData(self, pixmap: QPixmap) -> None:
        """Feeds the magnifier item with the current pixmap and raw data."""
        rawData = self.viewModel.activeRawData
        if rawData is not None:
            kevFactor = self.viewModel.kevConversionFactor
            self._magnifierItem.setSourceData(
                pixmap, rawData, lambda val: val * kevFactor
            )

    @Slot()
    def updateZoom(self):
        """Updates the graphics view transform based on scale."""
        # UX Feedback: Busy Cursor & Disable Buttons
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.btnZoomIn.setEnabled(False)
        self.btnZoomOut.setEnabled(False)
        self.btnZoomReset.setEnabled(False)

        try:
            scale = self.viewModel.scale
            transform = QTransform()
            transform.scale(scale, scale)
            self.graphicsView.setTransform(transform)
        finally:
            # Restore UX
            self.btnZoomIn.setEnabled(True)
            self.btnZoomOut.setEnabled(True)
            self.btnZoomReset.setEnabled(True)
            QApplication.restoreOverrideCursor()

    @Slot()
    def _updateActiveTool(self):
        """Syncs toolbar button states, cursor modes, and overlays."""
        tool = self.viewModel.activeTool
        self.btnPointer.setChecked(tool == ActiveTool.POINTER)
        self.btnMagnifier.setChecked(tool == ActiveTool.MAGNIFIER)
        self.btnBoxSelect.setChecked(tool == ActiveTool.BOX_SELECT)

        pointerActive = self.viewModel.isPointerActive
        magnifierActive = self.viewModel.isMagnifierActive
        boxSelectActive = self.viewModel.isBoxSelectActive

        self.graphicsView.setPointerActive(pointerActive)
        self.graphicsView.setMagnifierActive(magnifierActive)
        self.graphicsView.setBoxSelectActive(boxSelectActive)
        self._magnifierItem.setVisible(magnifierActive)

        if not pointerActive:
            self.viewModel.clearPointerHover()

        if magnifierActive:
            self.graphicsView.setFocus()

    @Slot()
    def _updateMagnifierState(self):
        """Updates the magnifier graphics item's magnification factor."""
        self._magnifierItem.setMagnificationFactor(
            self.viewModel.magnificationFactor
        )

    @Slot(int, int)
    def _onPixelHovered(self, row: int, col: int):
        """Routes mouse hover to the active tool in the ViewModel."""
        if self.viewModel.isMagnifierActive:
            self.viewModel.setMagnifierPosition(row, col)
        elif self.viewModel.isPointerActive:
            self.viewModel.setPointerHoverPosition(row, col)

    @Slot(int, int)
    def _onPixelNudged(self, drow: int, dcol: int):
        """Routes arrow key nudge to the ViewModel."""
        self.viewModel.moveMagnifier(drow, dcol)

    @Slot()
    def _updateMagnifierPosition(self):
        """Syncs magnifier item position from ViewModel state."""
        row, col = self.viewModel.magnifierPosition
        self._magnifierItem.setPixelPos(row, col)
        self._positionMagnifierItem(row, col)

    @Slot()
    def _updatePointerStatus(self):
        """Updates the status label with pointer hover info."""
        info = self.viewModel.pointerHoverInfo
        if info is None:
            self._statusLabel.setText("")
        else:
            row, col, kev = info
            self._statusLabel.setText(
                self.tr("X: {col}  Y: {row}  Value: {kev} keV").format(
                    col=col, row=row, kev=f"{kev:.5f}"
                )
            )

    def _positionMagnifierItem(self, row: int, col: int) -> None:
        """Positions the magnifier near the cursor, clamped to image."""
        imageRect = self.pixmapItem.boundingRect()
        magRect = self._magnifierItem.boundingRect()
        magWidth = magRect.width()
        magHeight = magRect.height()

        desiredX = col - (self._magnifierItem.displaySize / 2)
        desiredY = row - (magHeight / 2)

        clampedX = max(
            imageRect.left(), min(desiredX, imageRect.right() - magWidth)
        )
        clampedY = max(
            imageRect.top(), min(desiredY, imageRect.bottom() - magHeight)
        )

        if magWidth > imageRect.width():
            clampedX = imageRect.left()
        if magHeight > imageRect.height():
            clampedY = imageRect.top()

        self._magnifierItem.setPos(clampedX, clampedY)

    @Slot(int, int, int, int)
    def _onBoxSelectionCompleted(
        self, top: int, left: int, bottom: int, right: int
    ):
        """Handles a completed box selection from the graphics view."""
        self.viewModel.clearRois()
        self.viewModel.addRoi(top, left, bottom, right)

    @Slot(int, int)
    def _onBoxSelectClicked(self, row: int, col: int) -> None:
        """Dismisses the ROI if the click is outside the selection."""
        rois = self.viewModel.rois
        if not rois:
            return
        bbox = rois[-1].geometry()
        if (
            row < bbox.top
            or row >= bbox.bottom
            or col < bbox.left
            or col >= bbox.right
        ):
            self.viewModel.clearRois()

    @Slot()
    def _updateBoxSelection(self):
        """Syncs the BoxSelectionGraphicsItem from ViewModel ROI state."""
        rois = self.viewModel.rois
        if rois:
            bbox = rois[-1].geometry()
            self._boxSelectionItem.setRect(
                bbox.top, bbox.left, bbox.bottom, bbox.right
            )
        else:
            self._boxSelectionItem.clear()

    @Slot()
    def _updateClusteringState(self):
        """Shows/hides overlay and enables/disables UI for clustering."""
        running = (
            self.viewModel.clusteringState == ClusteringState.RUNNING
        )
        if running:
            self._clusteringOverlay.showOverlay()
        else:
            self._clusteringOverlay.hideOverlay()
        self._setInteractionEnabled(not running)
        self._refreshExtractionButton()

    @Slot()
    def _updateClusteringProgress(self):
        """Updates the overlay progress bar from ViewModel state."""
        self._clusteringOverlay.setProgress(
            self.viewModel.clusteringProgress
        )

    @Slot()
    def _showClusteringError(self):
        """Displays a warning dialog with the clustering error message."""
        message = self.viewModel.clusteringError or self.tr(
            "An unknown error occurred during cluster extraction."
        )
        QMessageBox.warning(
            self,
            self.tr("Cluster Extraction Failed"),
            message,
        )

    @Slot()
    def _updateClusteringResults(self):
        """Populates the clustered event widget from ViewModel results."""
        results = self.viewModel.clusteringResults
        self._clusteredEventWidget.setColormap(
            self.viewModel.clusterThumbnailColormap
        )
        self._clusteredEventWidget.setDisplayEnergyInKev(
            self.viewModel.displayEnergyInKev
        )
        self._clusteredEventWidget.setKevConversion(
            self.viewModel.kevConversion
        )
        self._clusteredEventWidget.setResults(results)

    @Slot()
    def _updateSelectedCluster(self):
        """Syncs the widget's selection with ViewModel state."""
        self._clusteredEventWidget.setSelectedIndex(
            self.viewModel.selectedClusterIndex
        )

    @Slot()
    def _refreshExtractionButton(self):
        """Enables Run Extraction when clustering is available."""
        self._btnRunExtraction.setEnabled(
            self.viewModel.isClusteringAvailable
        )

    def _setInteractionEnabled(self, enabled: bool) -> None:
        """Enables or disables interactive controls."""
        self.leftToolbar.setEnabled(enabled)
        self.rightSidebar.setEnabled(enabled)

    def onColormapChanged(self, text):
        self.viewModel.setColormap(text)

    def onRangeChanged(self, vmin, vmax):
        self.viewModel.setVisualizationRange(vmin, vmax)
