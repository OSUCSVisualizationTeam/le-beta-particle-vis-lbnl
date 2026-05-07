from PySide6.QtCore import (
    QMetaObject,
    QRectF,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QImage,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common import AnnotationOverlay
from ...viewmodels.ClusterAnalysisViewModel import ClusteringState
from ...viewmodels.RawDataViewModel import RawDataViewModel
from ...widgets.CaptureGraphicsView import CaptureGraphicsView
from ...widgets.ClusteringProgressOverlay import ClusteringProgressOverlay
from ...widgets.HDUVisualizationWidget import HDUVisualizationWidget
from ...widgets.MagnifierGraphicsItem import MagnifierGraphicsItem
from ._RawDataManipulationToolbar import _RawDataManipulationToolbar
from ._RawDataViewStyle import _Style

from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene


class _CenterImageAreaView(QWidget):
    """Center panel: toolbar, graphics scene, overlays, and status bar.

    Emits ``roiSelected(top, left, bottom, right)`` when a box selection
    completes so the parent can instruct the right sidebar to focus the ROI
    tab.
    """

    roiSelected = Signal(int, int, int, int)

    def __init__(self, viewModel: RawDataViewModel) -> None:
        super().__init__()
        self._vm = viewModel
        self._initUI()
        self._bindViewModel()

    @property
    def _cavm(self):
        return self._vm.clusterAnalysisViewModel

    # --- Setup ---

    def _initUI(self) -> None:
        self._centerContainer = HDUVisualizationWidget()
        centerLayout = self._centerContainer.contentLayout

        self._toolbar = _RawDataManipulationToolbar(self._vm)
        centerLayout.addWidget(self._toolbar)

        self._setupGraphicsScene(centerLayout)
        self._setupSceneOverlays()
        centerLayout.addWidget(self._createStatusBar())
        self._activateDefaultTool()

        self._clusteringOverlay = ClusteringProgressOverlay(self._centerContainer)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._centerContainer)

    def _setupGraphicsScene(self, centerLayout: QVBoxLayout) -> None:
        self.scene = QGraphicsScene()
        self.graphicsView = CaptureGraphicsView()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setStyleSheet(_Style.GRAPHICS_VIEW)
        self.graphicsView.setAlignment(Qt.AlignCenter)

        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)
        self._centerContainer.addSourceView(self.graphicsView)

    def _setupSceneOverlays(self) -> None:
        self._magnifierItem = MagnifierGraphicsItem(
            fixedDisplaySize=127,
            initialMagnificationFactor=3.0,
        )
        self._magnifierItem.setUnitLabel(self.tr("keV"))
        self._magnifierItem.setVisible(False)
        if self._vm.showToolHints:
            self._magnifierItem.setHintLines(
                [
                    self.tr("Arrow keys: fine movement"),
                    self.tr("Scroll wheel: zoom in/out"),
                ]
            )
        self.scene.addItem(self._magnifierItem)

        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.setBoxSelectionColor(self._cavm.boxSelectColor)
            hud.setBoxSelectionBorderWidth(self._cavm.boxSelectBorderWidth)
            hud.bindMagnifier(self._magnifierItem)

    def _createStatusBar(self) -> QWidget:
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
        self.graphicsView.setBoxSelectActive(True)
        if self._vm.showToolHints:
            self._hintLabel.setText(self.tr("⇧ Shift + drag to select ROI"))
            self._hintLabel.setVisible(True)

    # --- ViewModel binding ---

    def _bindViewModel(self) -> None:
        self._bindImageCallbacks()
        self._bindToolCallbacks()
        self._bindGraphicsViewSignals()
        self._bindRoiCallbacks()
        self._bindClusteringOverlayCallbacks()
        self._bindClusterSelectionCallbacks()

    def _bindImageCallbacks(self) -> None:
        def on_image_changed():
            QMetaObject.invokeMethod(self, "updateImage", Qt.QueuedConnection)

        def on_scale_changed():
            QMetaObject.invokeMethod(self, "updateZoom", Qt.QueuedConnection)

        self._vm.add_image_changed_callback(on_image_changed)
        self._vm.add_scale_changed_callback(on_scale_changed)

    def _bindToolCallbacks(self) -> None:
        def on_active_tool_changed():
            QMetaObject.invokeMethod(self, "_updateActiveTool", Qt.QueuedConnection)

        def on_magnifier_state_changed():
            QMetaObject.invokeMethod(self, "_updateMagnifierState", Qt.QueuedConnection)

        def on_magnifier_position_changed():
            QMetaObject.invokeMethod(
                self, "_updateMagnifierPosition", Qt.QueuedConnection
            )

        def on_pointer_hover_changed():
            QMetaObject.invokeMethod(self, "_updatePointerStatus", Qt.QueuedConnection)

        self._vm.add_active_tool_changed_callback(on_active_tool_changed)
        self._vm.add_magnifier_state_changed_callback(on_magnifier_state_changed)
        self._vm.add_magnifier_position_changed_callback(on_magnifier_position_changed)
        self._vm.add_pointer_hover_changed_callback(on_pointer_hover_changed)

    def _bindGraphicsViewSignals(self) -> None:
        self.graphicsView.pixelHovered.connect(self._onPixelHovered)
        self.graphicsView.pixelNudgeRequested.connect(self._onPixelNudged)
        self.graphicsView.magnificationDeltaRequested.connect(
            self._vm.adjustMagnification
        )
        self.graphicsView.mouseLeft.connect(self._vm.clearPointerHover)
        self.graphicsView.boxSelectionCompleted.connect(self._onBoxSelectionCompleted)
        self.graphicsView.boxSelectClicked.connect(self._onBoxSelectClicked)

    def _bindRoiCallbacks(self) -> None:
        def on_roi_changed():
            QMetaObject.invokeMethod(self, "_updateBoxSelection", Qt.QueuedConnection)

        self._cavm.add_roi_changed_callback(on_roi_changed)

    def _bindClusteringOverlayCallbacks(self) -> None:
        """Wire clustering overlay (progress, state, error, cancel).

        Uses Qt.AutoConnection so the overlay shows immediately when
        triggerClustering runs on the main thread, while still queuing
        safely from the extractor background thread.
        """

        def on_clustering_state_changed():
            QMetaObject.invokeMethod(
                self, "_updateClusteringState", Qt.AutoConnection
            )

        self._cavm.add_clustering_state_changed_callback(on_clustering_state_changed)

        def on_clustering_progress():
            QMetaObject.invokeMethod(
                self, "_updateClusteringProgress", Qt.AutoConnection
            )

        self._cavm.add_clustering_progress_callback(on_clustering_progress)
        self._clusteringOverlay.cancelRequested.connect(self._cavm.cancelClustering)

        def on_clustering_error():
            QMetaObject.invokeMethod(
                self, "_showClusteringError", Qt.QueuedConnection
            )

        self._cavm.add_clustering_error_callback(on_clustering_error)

    def _bindClusterSelectionCallbacks(self) -> None:
        """Wire cluster selection to the annotation overlay on the HUD.

        AutoConnection is required: selectCluster fires on the main thread
        (user click), while clearClusteringResults can fire from a background
        thread (new extraction result). File-load and HDU-change come from
        background threads, so they use QueuedConnection.
        """

        def on_selection_changed():
            QMetaObject.invokeMethod(
                self, "_updateClusterAnnotationOverlay", Qt.AutoConnection
            )

        def on_context_changed():
            QMetaObject.invokeMethod(
                self, "_clearClusterAnnotationOverlay", Qt.QueuedConnection
            )

        self._cavm.add_selected_cluster_changed_callback(on_selection_changed)
        self._vm.add_file_loaded_callback(on_context_changed)
        self._vm.add_active_hdu_changed_callback(on_context_changed)

    # --- Public API ---

    def setZoomControlsEnabled(self, enabled: bool) -> None:
        """Proxy used by parent when disabling controls during clustering."""
        self._toolbar.setZoomControlsEnabled(enabled)

    def setToolbarEnabled(self, enabled: bool) -> None:
        """Enables or disables the manipulation toolbar."""
        self._toolbar.setEnabled(enabled)

    # --- Image / zoom ---

    @Slot()
    def updateImage(self) -> None:
        """Thread-safe update of the displayed pixmap."""
        buffer = self._vm.currentBuffer

        if buffer is not None:
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
            self.updateZoom()
            self._updateMagnifierSourceData(pixmap)
        else:
            self.pixmapItem.setPixmap(QPixmap())

    def _updateMagnifierSourceData(self, pixmap: QPixmap) -> None:
        rawData = self._vm.activeRawData
        if rawData is not None:
            kevFactor = self._vm.kevConversionFactor
            self._magnifierItem.setSourceData(
                pixmap, rawData, lambda val: val * kevFactor
            )
            hud = self._centerContainer.hudWidget
            if hud is not None:
                hud.refreshMagnifier()

    @Slot()
    def updateZoom(self) -> None:
        """Updates the graphics view transform based on scale."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._toolbar.setZoomControlsEnabled(False)
        try:
            scale = self._vm.scale
            transform = QTransform()
            transform.scale(scale, scale)
            self.graphicsView.setTransform(transform)
        finally:
            self._toolbar.setZoomControlsEnabled(True)
            QApplication.restoreOverrideCursor()

    # --- Tool state ---

    @Slot()
    def _updateActiveTool(self) -> None:
        magnifierActive = self._vm.isMagnifierActive
        boxSelectActive = self._vm.isBoxSelectActive

        self.graphicsView.setMagnifierActive(magnifierActive)
        self.graphicsView.setBoxSelectActive(boxSelectActive)
        self._magnifierItem.setVisible(magnifierActive)
        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.setMagnifierVisible(magnifierActive)

        if not boxSelectActive:
            self._vm.clearPointerHover()

        if boxSelectActive and self._vm.showToolHints:
            self._hintLabel.setText(self.tr("⇧ Shift + drag to select ROI"))
            self._hintLabel.setVisible(True)
        else:
            self._hintLabel.setVisible(False)

        if magnifierActive:
            self.graphicsView.setFocus()

    @Slot()
    def _updateMagnifierState(self) -> None:
        self._magnifierItem.setMagnificationFactor(self._vm.magnificationFactor)
        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.refreshMagnifier()

    @Slot(int, int)
    def _onPixelHovered(self, row: int, col: int) -> None:
        if self._vm.isMagnifierActive:
            self._vm.setMagnifierPosition(row, col)
        else:
            self._vm.setPointerHoverPosition(row, col)

    @Slot(int, int)
    def _onPixelNudged(self, drow: int, dcol: int) -> None:
        self._vm.moveMagnifier(drow, dcol)

    @Slot()
    def _updateMagnifierPosition(self) -> None:
        row, col = self._vm.magnifierPosition
        self._magnifierItem.setPixelPos(row, col)
        self._positionMagnifierItem(row, col)
        hud = self._centerContainer.hudWidget
        if hud is not None:
            hud.refreshMagnifier()

    @Slot()
    def _updatePointerStatus(self) -> None:
        info = self._vm.pointerHoverInfo
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

    # --- Box selection ---

    @Slot(int, int, int, int)
    def _onBoxSelectionCompleted(
        self, top: int, left: int, bottom: int, right: int
    ) -> None:
        self._cavm.clearRois()
        self._cavm.addRoi(top, left, bottom, right)
        self.roiSelected.emit(top, left, bottom, right)

    @Slot(int, int)
    def _onBoxSelectClicked(self, row: int, col: int) -> None:
        rois = self._cavm.rois
        if not rois:
            return
        bbox = rois[-1].geometry()
        if row < bbox.top or row >= bbox.bottom or col < bbox.left or col >= bbox.right:
            self._cavm.clearRois()

    @Slot()
    def _updateBoxSelection(self) -> None:
        hud = self._centerContainer.hudWidget
        if hud is None:
            return
        rois = self._cavm.rois
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

    # --- Cluster annotation overlay ---

    @Slot()
    def _updateClusterAnnotationOverlay(self) -> None:
        hud = self._centerContainer.hudWidget
        if hud is None:
            return
        clusters = self._cavm.selectedClusters
        if not clusters:
            hud.setAnnotationOverlays([])
            return
        hud.setAnnotationOverlays(
            [AnnotationOverlay(c.boundingBox) for c in clusters]
        )

    @Slot()
    def _clearClusterAnnotationOverlay(self) -> None:
        hud = self._centerContainer.hudWidget
        if hud is None:
            return
        hud.setAnnotationOverlays([])

    # --- Clustering state ---

    @Slot()
    def _updateClusteringState(self) -> None:
        running = self._cavm.clusteringState == ClusteringState.RUNNING
        if running:
            self._clusteringOverlay.showOverlay()
        else:
            self._clusteringOverlay.hideOverlay()

    @Slot()
    def _updateClusteringProgress(self) -> None:
        self._clusteringOverlay.setProgress(self._cavm.clusteringProgress)

    @Slot()
    def _showClusteringError(self) -> None:
        message = self._cavm.clusteringError or self.tr(
            "An unknown error occurred during cluster extraction."
        )
        QMessageBox.warning(
            self,
            self.tr("Cluster Extraction Failed"),
            message,
        )

    def centerOn(self, x: float, y: float) -> None:
        """Delegates pan to the underlying CaptureGraphicsView."""
        self.graphicsView.centerOn(x, y)
