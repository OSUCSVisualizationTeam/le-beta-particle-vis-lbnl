from PySide6.QtCore import QMetaObject, QRectF, QSize, Qt, Slot
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
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QStyleFactory,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..fitsconverters import Colormap, ScalingFunction
from ..viewmodels.RawDataViewModel import (
    ActiveTool,
    ClusteringState,
    RawDataViewModel,
)
from ..widgets.CaptureGraphicsView import CaptureGraphicsView
from ..widgets.MagnifierGraphicsItem import MagnifierGraphicsItem
from ..widgets.ClusteringProgressOverlay import ClusteringProgressOverlay
from ..widgets.HDUVisualizationWidget import HDUVisualizationWidget
from ..widgets.ROIInfoWidget import ROIInfoWidget
from ..widgets.VerticalRangeControl import VerticalRangeControl
from .ClusterAnalysisView import ClusterAnalysisView
from .MosaicView import MosaicView
from ._RawDataViewStyle import _Style


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
        layout.setSpacing(0)

        self.rangeControl = VerticalRangeControl(abs_min=0.0, abs_max=1.0)
        self.rangeControl.setVisible(False)
        self.rangeControl.rangeChanged.connect(self.onRangeChanged)
        layout.addWidget(self.rangeControl, 1)

        self.bodyLayout.addWidget(self.leftToolbar)

    def _setupTopToolbar(self) -> None:
        """Creates the horizontal top toolbar with tool and zoom buttons."""
        self.topToolbar = QFrame()
        self.topToolbar.setFixedHeight(46)
        self.topToolbar.setStyleSheet(_Style.TOP_TOOLBAR)
        layout = QHBoxLayout(self.topToolbar)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(4)

        self._createToolButtons(layout)
        self._createZoomButtons(layout)

    def _createToolButtons(self, layout: QHBoxLayout) -> None:
        """Creates the exclusive tool button group (ROI + Magnifier)
        and adds them to the given toolbar layout."""
        btn_size = QSize(36, 36)
        style = _Style.LEFT_TOOLBAR_BUTTON

        self._toolButtonGroup = QButtonGroup(self)
        self._toolButtonGroup.setExclusive(True)

        self.btnBoxSelect = QToolButton()
        self.btnBoxSelect.setIcon(self._createBoxSelectIcon())
        self.btnBoxSelect.setToolTip(self.tr("Region Of Interest"))
        self.btnBoxSelect.setCheckable(True)
        self.btnBoxSelect.setChecked(True)
        self.btnBoxSelect.setFixedSize(btn_size)
        self.btnBoxSelect.setStyleSheet(style)
        self.btnBoxSelect.clicked.connect(
            lambda: self.viewModel.setActiveTool(ActiveTool.BOX_SELECT)
        )
        self._toolButtonGroup.addButton(self.btnBoxSelect)
        layout.addWidget(self.btnBoxSelect)

        self.btnMagnifier = QToolButton()
        self.btnMagnifier.setIcon(self._createMagnifierIcon())
        self.btnMagnifier.setToolTip(self.tr("Magnifier: Inspect pixels in detail"))
        self.btnMagnifier.setCheckable(True)
        self.btnMagnifier.setFixedSize(btn_size)
        self.btnMagnifier.setStyleSheet(style)
        self.btnMagnifier.clicked.connect(
            lambda: self.viewModel.setActiveTool(ActiveTool.MAGNIFIER)
        )
        self._toolButtonGroup.addButton(self.btnMagnifier)
        layout.addWidget(self.btnMagnifier)

    def _createZoomButtons(self, layout: QHBoxLayout) -> None:
        """Adds a vertical separator and the three zoom buttons
        (Zoom In, Reset, Zoom Out) plus a trailing stretch."""
        btn_size = QSize(36, 36)
        style = _Style.LEFT_TOOLBAR_BUTTON

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet(_Style.LEFT_TOOLBAR_DIVIDER)
        sep.setFixedHeight(28)
        layout.addWidget(sep)

        self.btnZoomIn = QToolButton()
        self.btnZoomIn.setText("+")
        self.btnZoomIn.setToolTip(self.tr("Zoom In"))
        self.btnZoomIn.setFixedSize(btn_size)
        self.btnZoomIn.setStyleSheet(_Style.ZOOM_IN)
        self.btnZoomIn.clicked.connect(self.viewModel.zoomIn)
        layout.addWidget(self.btnZoomIn)

        self.btnZoomReset = QToolButton()
        self.btnZoomReset.setText("1x")
        self.btnZoomReset.setToolTip(self.tr("Reset Zoom (1:1)"))
        self.btnZoomReset.setFixedSize(btn_size)
        self.btnZoomReset.setStyleSheet(style)
        self.btnZoomReset.clicked.connect(self.viewModel.resetZoom)
        layout.addWidget(self.btnZoomReset)

        self.btnZoomOut = QToolButton()
        self.btnZoomOut.setText("-")
        self.btnZoomOut.setToolTip(self.tr("Zoom Out"))
        self.btnZoomOut.setFixedSize(btn_size)
        self.btnZoomOut.setStyleSheet(_Style.ZOOM_OUT)
        self.btnZoomOut.clicked.connect(self.viewModel.zoomOut)
        layout.addWidget(self.btnZoomOut)

        layout.addStretch()

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
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "\U0001f50d")
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
            painter.drawRect(cx - handle // 2, cy - handle // 2, handle, handle)
        painter.end()
        return QIcon(pixmap)

    def _setupCenterImageArea(self) -> None:
        """Assembles the center image area: toolbar, graphics scene,
        overlays, status bar, and clustering overlay."""
        self._centerContainer = HDUVisualizationWidget()
        centerLayout = self._centerContainer.contentLayout

        self._setupTopToolbar()
        centerLayout.addWidget(self.topToolbar)

        self._setupGraphicsScene(centerLayout)
        self._setupSceneOverlays()
        centerLayout.addWidget(self._createStatusBar())
        self._activateDefaultTool()

        self._clusteringOverlay = ClusteringProgressOverlay(self._centerContainer)
        self.bodyLayout.addWidget(self._centerContainer)

    def _setupGraphicsScene(self, centerLayout: QVBoxLayout) -> None:
        """Creates and wires the QGraphicsScene, view, and base pixmap item."""
        self.scene = QGraphicsScene()
        self.graphicsView = CaptureGraphicsView()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setStyleSheet(_Style.GRAPHICS_VIEW)
        self.graphicsView.setAlignment(Qt.AlignCenter)

        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)
        self._centerContainer.addSourceView(self.graphicsView)

    def _setupSceneOverlays(self) -> None:
        """Adds the MagnifierGraphicsItem and BoxSelectionGraphicsItem
        to the scene. Both start hidden."""
        self._magnifierItem = MagnifierGraphicsItem(
            fixedDisplaySize=127,
            initialMagnificationFactor=3.0,
        )
        self._magnifierItem.setUnitLabel(self.tr("keV"))
        self._magnifierItem.setVisible(False)
        if self.viewModel.showToolHints:
            self._magnifierItem.setHintLines(
                [
                    self.tr("Arrow keys: fine movement"),
                    self.tr("Scroll wheel: zoom in/out"),
                ]
            )
        self.scene.addItem(self._magnifierItem)

        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.setBoxSelectionColor(self.viewModel.boxSelectColor)
            hud.setBoxSelectionBorderWidth(self.viewModel.boxSelectBorderWidth)
            hud.bindMagnifier(self._magnifierItem)

    def _createStatusBar(self) -> QWidget:
        """Builds the pixel-info / tool-hint status bar widget."""
        statusBar = QWidget()
        statusBar.setFixedHeight(24)
        statusBar.setStyleSheet(_Style.STATUS_BAR)
        statusBarLayout = QHBoxLayout(statusBar)
        statusBarLayout.setContentsMargins(0, 0, 0, 0)
        statusBarLayout.setSpacing(0)

        self._statusLabel = QLabel()
        statusBarLayout.addWidget(self._statusLabel, 1)

        self._hintLabel = QLabel()
        self._hintLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._hintLabel.setStyleSheet("padding-right: 8px;")
        self._hintLabel.setMinimumWidth(220)
        self._hintLabel.setVisible(False)
        statusBarLayout.addWidget(self._hintLabel)

        return statusBar

    def _activateDefaultTool(self) -> None:
        """Sets the box-select cursor mode and shows the initial hint."""
        self.graphicsView.setBoxSelectActive(True)
        if self.viewModel.showToolHints:
            self._hintLabel.setText(self.tr("\u21e7 Shift + drag to select ROI"))
            self._hintLabel.setVisible(True)

    def _setupRightSidebar(self):
        self.rightSidebar = QFrame()
        self.rightSidebar.setFixedWidth(300)
        self.rightSidebar.setStyle(QStyleFactory.create("Fusion"))
        self.rightSidebar.setStyleSheet(_Style.RIGHT_SIDEBAR)
        self.rightLayout = QVBoxLayout(self.rightSidebar)
        self.rightLayout.setContentsMargins(10, 10, 10, 10)
        self.rightLayout.setSpacing(15)

        self._setupRightSidebarTabs()

        self.bodyLayout.addWidget(self.rightSidebar)

    def _setupRightSidebarTabs(self):
        self._rightSidebarTabs = QTabWidget()
        self._rightSidebarTabs.addTab(self._buildVisualizationTab(), self.tr("Vis"))
        self._rightSidebarTabs.addTab(self._buildClusteringTab(), self.tr("Clustering"))
        self._roiInfoTabIndex = self._rightSidebarTabs.addTab(
            self._buildRoiInfoTab(), self.tr("ROI Info")
        )
        self.rightLayout.addWidget(self._rightSidebarTabs, 1)

    def _buildVisualizationTab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        vizGroup = QGroupBox("")
        vizLayout = QVBoxLayout(vizGroup)

        vizLayout.addWidget(QLabel(self.tr("Scaling")))
        self.scalingSelector = QComboBox()
        self.scalingSelector.addItems([s.value for s in ScalingFunction])
        self.scalingSelector.currentTextChanged.connect(self.onScalingChanged)
        vizLayout.addWidget(self.scalingSelector)

        vizLayout.addWidget(QLabel(self.tr("Colormap")))
        self.cmapSelector = QComboBox()
        self.cmapSelector.addItems([c.value for c in Colormap])
        self.cmapSelector.currentTextChanged.connect(self.onColormapChanged)
        vizLayout.addWidget(self.cmapSelector)

        layout.addWidget(vizGroup)

        filterGroup = QGroupBox(self.tr("Filtering Pipeline"))
        filterLayout = QVBoxLayout(filterGroup)
        filterLayout.addWidget(QLabel(self.tr("(Not implemented yet)")))
        layout.addWidget(filterGroup)

        layout.addStretch()
        return container

    def _buildClusteringTab(self) -> QWidget:
        view = ClusterAnalysisView(self.viewModel.clusterAnalysisViewModel)
        view.setContentsMargins(4, 4, 4, 4)
        return view

    def _buildRoiInfoTab(self) -> QWidget:
        return ROIInfoWidget(self.viewModel)

    def bindViewModel(self):
        """Bind all ViewModel callbacks and View signals."""
        self._bindImageCallbacks()
        self._bindToolCallbacks()
        self._bindGraphicsViewSignals()
        self._bindRoiCallbacks()
        self._bindClusteringOverlayCallbacks()

    def _bindImageCallbacks(self):
        """Wire image rendering, scale, mosaic, and range control."""

        def on_image_changed():
            QMetaObject.invokeMethod(self, "updateImage", Qt.QueuedConnection)

        def on_scale_changed():
            QMetaObject.invokeMethod(self, "updateZoom", Qt.QueuedConnection)

        self.viewModel.add_image_changed_callback(on_image_changed)
        self.viewModel.mosaicViewModel.add_thumbnails_changed_callback(
            self.updateMosaicVisibility
        )
        self.viewModel.add_scale_changed_callback(on_scale_changed)
        self.updateMosaicVisibility()

        vmin, vmax = self.viewModel.visualizationRange
        self.rangeControl.setValues(vmin, vmax)
        self.rangeControl.setColormap(self.viewModel.colormap)
        self.cmapSelector.setCurrentText(self.viewModel.colormap)
        self.scalingSelector.setCurrentText(self.viewModel.scalingFunction)

    def _bindToolCallbacks(self):
        """Wire active tool, magnifier, and pointer hover callbacks."""

        def on_active_tool_changed():
            QMetaObject.invokeMethod(self, "_updateActiveTool", Qt.QueuedConnection)

        def on_magnifier_state_changed():
            QMetaObject.invokeMethod(self, "_updateMagnifierState", Qt.QueuedConnection)

        def on_magnifier_position_changed():
            QMetaObject.invokeMethod(
                self,
                "_updateMagnifierPosition",
                Qt.QueuedConnection,
            )

        def on_pointer_hover_changed():
            QMetaObject.invokeMethod(
                self,
                "_updatePointerStatus",
                Qt.QueuedConnection,
            )

        self.viewModel.add_active_tool_changed_callback(on_active_tool_changed)
        self.viewModel.add_magnifier_state_changed_callback(on_magnifier_state_changed)
        self.viewModel.add_magnifier_position_changed_callback(
            on_magnifier_position_changed
        )
        self.viewModel.add_pointer_hover_changed_callback(on_pointer_hover_changed)

    def _bindGraphicsViewSignals(self):
        """Connect CaptureGraphicsView Qt signals to handlers."""
        self.graphicsView.pixelHovered.connect(self._onPixelHovered)
        self.graphicsView.pixelNudgeRequested.connect(self._onPixelNudged)
        self.graphicsView.magnificationDeltaRequested.connect(
            self.viewModel.adjustMagnification
        )
        self.graphicsView.mouseLeft.connect(self.viewModel.clearPointerHover)
        self.graphicsView.boxSelectionCompleted.connect(self._onBoxSelectionCompleted)
        self.graphicsView.boxSelectClicked.connect(self._onBoxSelectClicked)

    def _bindRoiCallbacks(self):
        """Wire ROI change callback for the box selection visual."""

        def on_roi_changed():
            QMetaObject.invokeMethod(self, "_updateBoxSelection", Qt.QueuedConnection)

        self.viewModel.add_roi_changed_callback(on_roi_changed)

    def _bindClusteringOverlayCallbacks(self):
        """Wire clustering overlay (progress, state, error, cancel).

        Uses Qt.AutoConnection so the overlay shows immediately when
        triggerClustering runs on the main thread, while still queuing
        safely from the extractor background thread.
        """

        def on_clustering_state_changed():
            QMetaObject.invokeMethod(
                self,
                "_updateClusteringState",
                Qt.AutoConnection,
            )

        self.viewModel.add_clustering_state_changed_callback(
            on_clustering_state_changed
        )

        def on_clustering_progress():
            QMetaObject.invokeMethod(
                self,
                "_updateClusteringProgress",
                Qt.AutoConnection,
            )

        self.viewModel.add_clustering_progress_callback(on_clustering_progress)

        self._clusteringOverlay.cancelRequested.connect(self.viewModel.cancelClustering)

        def on_clustering_error():
            QMetaObject.invokeMethod(
                self,
                "_showClusteringError",
                Qt.QueuedConnection,
            )

        self.viewModel.add_clustering_error_callback(on_clustering_error)

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
                buffer.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(q_img.copy())

            self.pixmapItem.setPixmap(pixmap)
            self.scene.setSceneRect(0, 0, width, height)

            # Ensure zoom is correct for new image
            self.updateZoom()

            # Update Range Control Limits (Sync with ViewModel data range)
            dmin, dmax = self.viewModel.dataRange
            self.rangeControl.setAbsoluteRange(dmin, dmax)

            if self.viewModel.autoRangeOnLoad:
                self.rangeControl.resetToFullRange()
            else:
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
            hud = self._centerContainer.hudWidget
            if hud is not None:
                hud.refreshMagnifier()

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
        self.btnMagnifier.setChecked(tool == ActiveTool.MAGNIFIER)
        self.btnBoxSelect.setChecked(tool == ActiveTool.BOX_SELECT)

        magnifierActive = self.viewModel.isMagnifierActive
        boxSelectActive = self.viewModel.isBoxSelectActive

        self.graphicsView.setMagnifierActive(magnifierActive)
        self.graphicsView.setBoxSelectActive(boxSelectActive)
        self._magnifierItem.setVisible(magnifierActive)
        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.setMagnifierVisible(magnifierActive)

        if not boxSelectActive:
            self.viewModel.clearPointerHover()

        if boxSelectActive and self.viewModel.showToolHints:
            self._hintLabel.setText(self.tr("\u21e7 Shift + drag to select ROI"))
            self._hintLabel.setVisible(True)
        else:
            self._hintLabel.setVisible(False)

        if magnifierActive:
            self.graphicsView.setFocus()

    @Slot()
    def _updateMagnifierState(self):
        """Updates the magnifier graphics item's magnification factor."""
        self._magnifierItem.setMagnificationFactor(self.viewModel.magnificationFactor)
        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.refreshMagnifier()

    @Slot(int, int)
    def _onPixelHovered(self, row: int, col: int):
        """Routes mouse hover to the active tool in the ViewModel."""
        if self.viewModel.isMagnifierActive:
            self.viewModel.setMagnifierPosition(row, col)
        else:
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
        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.refreshMagnifier()

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

        clampedX = max(imageRect.left(), min(desiredX, imageRect.right() - magWidth))
        clampedY = max(imageRect.top(), min(desiredY, imageRect.bottom() - magHeight))

        if magWidth > imageRect.width():
            clampedX = imageRect.left()
        if magHeight > imageRect.height():
            clampedY = imageRect.top()

        self._magnifierItem.setPos(clampedX, clampedY)

    @Slot(int, int, int, int)
    def _onBoxSelectionCompleted(self, top: int, left: int, bottom: int, right: int):
        """Handles a completed box selection from the graphics view."""
        self.viewModel.clearRois()
        self.viewModel.addRoi(top, left, bottom, right)
        self._rightSidebarTabs.setCurrentIndex(self._roiInfoTabIndex)

    @Slot(int, int)
    def _onBoxSelectClicked(self, row: int, col: int) -> None:
        """Dismisses the ROI if the click is outside the selection."""
        rois = self.viewModel.rois
        if not rois:
            return
        bbox = rois[-1].geometry()
        if row < bbox.top or row >= bbox.bottom or col < bbox.left or col >= bbox.right:
            self.viewModel.clearRois()

    @Slot()
    def _updateBoxSelection(self):
        """Syncs the HUD ROI overlay from ViewModel ROI state."""
        hud = self._centerContainer.hudWidget
        if hud is None:
            return
        rois = self.viewModel.rois
        if rois:
            bbox = rois[-1].geometry()
            sceneRect = QRectF(
                bbox.left,
                bbox.top,
                bbox.right - bbox.left,
                bbox.bottom - bbox.top,
            )
            hud.setBoxSelectionSceneRect(sceneRect)
        else:
            hud.setBoxSelectionSceneRect(None)

    @Slot()
    def _updateClusteringState(self):
        """Shows/hides overlay and enables/disables UI for clustering."""
        running = self.viewModel.clusteringState == ClusteringState.RUNNING
        if running:
            self._clusteringOverlay.showOverlay()
        else:
            self._clusteringOverlay.hideOverlay()
        self._setInteractionEnabled(not running)

    @Slot()
    def _updateClusteringProgress(self):
        """Updates the overlay progress bar from ViewModel state."""
        self._clusteringOverlay.setProgress(self.viewModel.clusteringProgress)

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

    def _setInteractionEnabled(self, enabled: bool) -> None:
        """Enables or disables interactive controls."""
        self.topToolbar.setEnabled(enabled)
        self.leftToolbar.setEnabled(enabled)
        self.rightSidebar.setEnabled(enabled)

    def onColormapChanged(self, text):
        self.viewModel.setColormap(text)

    def onScalingChanged(self, text: str) -> None:
        self.viewModel.setScalingFunction(text)

    def onRangeChanged(self, vmin, vmax):
        self.viewModel.setVisualizationRange(vmin, vmax)
