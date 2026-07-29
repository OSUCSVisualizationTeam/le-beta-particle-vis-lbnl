from typing import List

from PySide6.QtCore import (
    QMetaObject,
    QRectF,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common import AnnotationOverlay
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ParticleType import classify_particle
from ...fitsconverters import Colormap
from ...viewmodels.ClusterAnalysisViewModel import ClusteringState
from ...viewmodels.RawDataViewModel import RawDataViewModel
from ...widgets.ClusteringProgressOverlay import ClusteringProgressOverlay
from ...widgets.HDUVisualizationView import HDUVisualizationView
from ._RawDataManipulationToolbar import _RawDataManipulationToolbar


class _CenterImageAreaView(QWidget):
    """Control surface for the center panel.

    Owns the toolbar, status bar (pixel hover readout + tool hints),
    clustering progress overlay, and ROI / cluster annotation routing.
    The actual visualization (pixmap, scene, magnifier, zoom transform)
    lives in :class:`HDUVisualizationView`, hosted in the middle of the
    vertical stack.

    Emits ``roiSelected(top, left, bottom, right)`` when a box selection
    completes so the parent can instruct the right sidebar to focus the
    ROI tab.
    """

    roiSelected = Signal(int, int, int, int)

    def __init__(self, viewModel: RawDataViewModel) -> None:
        super().__init__()
        self._vm = viewModel
        self._persistentOverlays: List[AnnotationOverlay] = []
        self._selectionOverlays: List[AnnotationOverlay] = []
        self._initUI()
        self._bindViewModel()
        self._applyInitialToolHint()

    @property
    def _cavm(self):
        return self._vm.clusterAnalysisViewModel

    # --- Setup ---

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toolbar = _RawDataManipulationToolbar(self._vm)
        layout.addWidget(self._toolbar)

        self._visualizationView = HDUVisualizationView(self._vm)
        layout.addWidget(self._visualizationView, 1)

        layout.addWidget(self._createStatusBar())

        self._configureHudOverlays()
        self._clusteringOverlay = ClusteringProgressOverlay(self)

    def _configureHudOverlays(self) -> None:
        """Sets ROI-overlay style on the HUD owned by the visualization
        view. ROI styling is a control-surface concern, so it is wired
        from here rather than from inside the visualization view."""
        hud = self._visualizationView.hudWidget
        if hud is None:
            return
        hud.setBoxSelectionColor(self._cavm.boxSelectColor)
        hud.setBoxSelectionBorderWidth(self._cavm.boxSelectBorderWidth)

    def _createStatusBar(self) -> QWidget:
        statusBar = QWidget()
        statusBar.setObjectName("rawDataStatusBar")
        statusBar.setFixedHeight(24)
        statusBarLayout = QHBoxLayout(statusBar)
        statusBarLayout.setContentsMargins(0, 0, 0, 0)
        statusBarLayout.setSpacing(0)

        self._statusLabel = QLabel()
        statusBarLayout.addWidget(self._statusLabel, 1)

        self._hintLabel = QLabel()
        self._hintLabel.setObjectName("rawDataToolHintLabel")
        self._hintLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._hintLabel.setMinimumWidth(220)
        self._hintLabel.setVisible(False)
        statusBarLayout.addWidget(self._hintLabel)

        return statusBar

    def _applyInitialToolHint(self) -> None:
        if self._vm.isBoxSelectActive and self._vm.showToolHints:
            self._hintLabel.setText(self.tr("⇧ Shift + drag to select ROI"))
            self._hintLabel.setVisible(True)

    # --- ViewModel binding ---

    def _bindViewModel(self) -> None:
        self._bindToolHintCallbacks()
        self._bindPointerStatusCallback()
        self._bindVisualizationSignals()
        self._bindRoiCallbacks()
        self._bindClusteringOverlayCallbacks()
        self._bindClusterSelectionCallbacks()
        self._bindAnnotationCallbacks()

    def _bindToolHintCallbacks(self) -> None:
        def on_active_tool_changed():
            QMetaObject.invokeMethod(
                self, "_updateActiveToolHint", Qt.QueuedConnection
            )

        self._vm.add_active_tool_changed_callback(on_active_tool_changed)

    def _bindPointerStatusCallback(self) -> None:
        def on_pointer_hover_changed():
            QMetaObject.invokeMethod(
                self, "_updatePointerStatus", Qt.QueuedConnection
            )

        self._vm.add_pointer_hover_changed_callback(on_pointer_hover_changed)

    def _bindVisualizationSignals(self) -> None:
        self._visualizationView.boxSelectionCompleted.connect(
            self._onBoxSelectionCompleted
        )
        self._visualizationView.boxSelectClicked.connect(self._onBoxSelectClicked)

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

    def _bindAnnotationCallbacks(self) -> None:
        """Wires persistent EPS-backed annotations to the HUD.

        AutoConnection is required: the annotations VM notifies
        synchronously (main thread) when refresh() clears stale state on
        file/HDU change, and again later from its own background fetch
        thread once the EPS round-trip completes.
        """

        def on_annotations_changed():
            QMetaObject.invokeMethod(
                self, "_updatePersistentAnnotationOverlay", Qt.AutoConnection
            )

        self._vm.annotationsViewModel.add_annotations_changed_callback(
            on_annotations_changed
        )

    # --- Tool hint / pointer status ---

    @Slot()
    def _updateActiveToolHint(self) -> None:
        boxSelectActive = self._vm.isBoxSelectActive

        if not boxSelectActive:
            self._vm.clearPointerHover()

        if boxSelectActive and self._vm.showToolHints:
            self._hintLabel.setText(self.tr("⇧ Shift + drag to select ROI"))
            self._hintLabel.setVisible(True)
        else:
            self._hintLabel.setVisible(False)

    @Slot()
    def _updatePointerStatus(self) -> None:
        info = self._vm.pointerHoverInfo
        if info is None:
            self._statusLabel.setText("")
            return
        row, col, kev = info
        text = self.tr("X: {col}  Y: {row}  Value: {kev} keV").format(
            col=col, row=row, kev=f"{kev:.5f}"
        )
        cluster = self._vm.annotationsViewModel.hitTest(row, col)
        if cluster is not None:
            text += "  |  " + self._formatAnnotationClassification(cluster)
        self._statusLabel.setText(text)

    def _formatAnnotationClassification(self, cluster: Cluster) -> str:
        """Formats particle type + per-model scores for the status bar."""
        threshold = self._vm.annotationClassificationThreshold
        particle_type, _ = classify_particle(cluster, threshold)
        return self.tr(
            "{symbol} {name}  cnn {cnn:.0%}  nrg {nrg:.0%}  bdt {bdt:.0%}"
        ).format(
            symbol=particle_type.symbol,
            name=particle_type.display_name,
            cnn=cluster.cnnClassification,
            nrg=cluster.nrgClassification,
            bdt=cluster.bdtClassification,
        )

    # --- Box selection routing ---

    @Slot(int, int, int, int)
    def _onBoxSelectionCompleted(
        self, top: int, left: int, bottom: int, right: int
    ) -> None:
        self._cavm.clearRois()
        self._cavm.addRoi(top, left, bottom, right)
        self.roiSelected.emit(top, left, bottom, right)

    @Slot(int, int)
    def _onBoxSelectClicked(self, row: int, col: int) -> None:
        cluster = self._vm.annotationsViewModel.hitTest(row, col)
        if cluster is not None:
            self._openAnnotationDetailDialog(cluster)
            return
        rois = self._cavm.rois
        if not rois:
            return
        bbox = rois[-1].geometry()
        if row < bbox.top or row >= bbox.bottom or col < bbox.left or col >= bbox.right:
            self._cavm.clearRois()

    def _openAnnotationDetailDialog(self, cluster: Cluster) -> None:
        """Opens the read-only detail dialog for a clicked annotation."""
        from ._AnnotationDetailDialog import _AnnotationDetailDialog

        dialog = _AnnotationDetailDialog(
            cluster,
            physics=self._vm.physics_manager,
            threshold=self._vm.annotationClassificationThreshold,
            colormap=Colormap(self._vm.colormap),
            parent=self.window(),
        )
        dialog.exec()

    @Slot()
    def _updateBoxSelection(self) -> None:
        hud = self._visualizationView.hudWidget
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
        clusters = self._cavm.selectedClusters
        self._selectionOverlays = [
            AnnotationOverlay(c.boundingBox, cluster=c) for c in clusters
        ]
        self._pushAnnotationOverlays()

    @Slot()
    def _clearClusterAnnotationOverlay(self) -> None:
        """Clears the in-session selection overlays only.

        Persistent (EPS-backed) annotations are owned by
        ``RawDataAnnotationsViewModel`` and refresh independently on the
        same file/HDU-change events, so they must not be cleared here.
        """
        self._selectionOverlays = []
        self._pushAnnotationOverlays()

    @Slot()
    def _updatePersistentAnnotationOverlay(self) -> None:
        clusters = self._vm.annotationsViewModel.visibleAnnotations
        self._persistentOverlays = [
            AnnotationOverlay(c.boundingBox, cluster=c) for c in clusters
        ]
        self._pushAnnotationOverlays()

    def _pushAnnotationOverlays(self) -> None:
        """Combines persistent and selection overlays onto the HUD.

        Sole caller of ``hud.setAnnotationOverlays()`` so the two
        annotation sources never stomp on each other.
        """
        hud = self._visualizationView.hudWidget
        if hud is None:
            return
        hud.setAnnotationOverlays(
            self._persistentOverlays + self._selectionOverlays
        )

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

    # --- Public API ---

    def centerOn(self, x: float, y: float) -> None:
        """Delegates pan to the underlying visualization view."""
        self._visualizationView.centerOn(x, y)
