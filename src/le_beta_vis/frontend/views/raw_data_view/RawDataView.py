from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import (
    QMetaObject,
    Qt,
    Slot,
)
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.EPSDataClasses import (
    ClusterQueryFilter,
    FitsQueryFilter,
    FitsStoreRequest,
)
from le_beta_vis.common.EventRepository import EventRepository
from ...viewmodels.ClusterAnalysisViewModel import ClusteringState
from ...viewmodels.RawDataViewModel import RawDataViewModel
from ..MosaicView import MosaicView
from ._CenterImageAreaView import _CenterImageAreaView
from ._LeftToolbarView import _LeftToolbarView
from ._RightSidebarView import _RightSidebarView


class RawDataView(QWidget):
    def __init__(
        self,
        viewModel: RawDataViewModel,
        repository: Optional[EventRepository] = None,
    ):
        super().__init__()
        self.viewModel = viewModel
        self._repository = repository
        self._pendingClusterFocus: Optional[
            Tuple[Optional[int], Tuple[int, int, int, int]]
        ] = None
        self._pendingClusterRoiAdded: bool = False
        self.initUI()
        self.bindViewModel()

    @property
    def _cavm(self):
        """Shorthand accessor for the ClusterAnalysisViewModel sub-VM."""
        return self.viewModel.clusterAnalysisViewModel

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

        self._leftToolbar = _LeftToolbarView(self.viewModel)
        self.bodyLayout.addWidget(self._leftToolbar)

        self._centerArea = _CenterImageAreaView(self.viewModel)
        self.bodyLayout.addWidget(self._centerArea, 1)

        self._rightSidebar = _RightSidebarView(self.viewModel)
        self.bodyLayout.addWidget(self._rightSidebar)

        self._centerArea.roiSelected.connect(
            lambda *_: self._rightSidebar.focusRoiTab()
        )

    def bindViewModel(self):
        """Bind top-level ViewModel callbacks."""
        self._bindMosaicCallbacks()
        self._bindRangeAndFocusCallbacks()
        self._bindClusteringStateCallback()
        if self._repository is not None:
            self._cavm.setExportHandler(self._onExportRequested)
            self.viewModel.annotationsViewModel.setFitsLookupHandler(
                self._onAnnotationFitsLookup
            )
            self.viewModel.annotationsViewModel.setClusterFetchHandler(
                self._onAnnotationClusterFetch
            )
        self._cavm.setClassifyHandler(self._onClassifyRequested)

    def _bindMosaicCallbacks(self) -> None:
        self.viewModel.mosaicViewModel.add_thumbnails_changed_callback(
            self.updateMosaicVisibility
        )
        self.updateMosaicVisibility()

    def _bindRangeAndFocusCallbacks(self) -> None:
        """Register a single image-changed handler for rangeControl and
        any pending cluster-focus pan."""
        self._leftToolbar.rangeControl.setValues(*self.viewModel.visualizationRange)
        self._leftToolbar.rangeControl.setColormap(self.viewModel.colormap)

        def on_image_changed():
            QMetaObject.invokeMethod(self, "_updateRangeControl", Qt.QueuedConnection)
            QMetaObject.invokeMethod(
                self, "_consumePendingClusterFocus", Qt.QueuedConnection
            )

        self.viewModel.add_image_changed_callback(on_image_changed)

    def _bindClusteringStateCallback(self) -> None:
        """Disable outer controls (left toolbar, right sidebar) while clustering."""

        def on_clustering_state_changed():
            QMetaObject.invokeMethod(
                self, "_onClusteringStateChanged", Qt.AutoConnection
            )

        self._cavm.add_clustering_state_changed_callback(on_clustering_state_changed)

    def updateMosaicVisibility(self):
        count = len(self.viewModel.mosaicViewModel.thumbnails)
        self.mosaicView.setVisible(count > 1)

    @Slot()
    def _updateRangeControl(self) -> None:
        buffer = self.viewModel.currentBuffer
        self._leftToolbar.rangeControl.setVisible(buffer is not None)
        if buffer is None:
            return
        dmin, dmax = self.viewModel.dataRange
        self._leftToolbar.rangeControl.setAbsoluteRange(dmin, dmax)
        if self.viewModel.autoRangeOnLoad:
            self._leftToolbar.rangeControl.resetToFullRange()
        else:
            self._leftToolbar.rangeControl.setValues(*self.viewModel.visualizationRange)
        self._leftToolbar.rangeControl.setColormap(self.viewModel.colormap)

    @Slot()
    def _onClusteringStateChanged(self) -> None:
        running = self._cavm.clusteringState == ClusteringState.RUNNING
        self._leftToolbar.setEnabled(not running)
        self._rightSidebar.setEnabled(not running)

    def _onExportRequested(self, clusters: List[ClusteredEventInfo]) -> None:
        indices_to_remove = list(self._cavm.selectedClusterIndices)

        def fits_info() -> Tuple[int, int]:
            fits_path = self.viewModel.fits_path
            if not fits_path:
                raise RuntimeError("No FITS file is currently loaded.")
            filename = Path(fits_path).name
            records = self._repository.query_fits_sync(
                FitsQueryFilter(filename=filename)
            )
            if records:
                return records[0].fits_id, self.viewModel.activeIndex
            info = self.viewModel.active_capture_info()
            capture_date = info.captureDate() if info else None
            date_str = (
                capture_date.to_datetime().strftime("%Y-%m-%d %H:%M:%S")
                if capture_date is not None
                else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            exposure = info.exposureDuration() if info else None
            new_fits_id = self._repository.store_fits_sync(FitsStoreRequest(
                filename=filename,
                date=date_str,
                min=float(info.min) if info else 0.0,
                max=float(info.max) if info else 0.0,
                exposure_time=float(exposure.sec) if exposure is not None else 0.0,
            ))
            if new_fits_id is None:
                raise RuntimeError(
                    f"Failed to register '{filename}' in EPS. "
                    "Check EPS connectivity."
                )
            return new_fits_id, self.viewModel.activeIndex

        from ...viewmodels.RawClusterLabelingViewModel import (
            RawClusterLabelingViewModel,
        )
        from ._RawClusterLabelingDialog import _RawClusterLabelingDialog

        vm = RawClusterLabelingViewModel(
            clusters=clusters,
            repository=self._repository,
            physics=self.viewModel.physics_manager,
            fits_info_provider=fits_info,
        )
        dialog = _RawClusterLabelingDialog(vm, parent=self.window())
        if dialog.exec() == QDialog.Accepted:
            self._cavm.removeClustersByIndices(indices_to_remove)

    def _onAnnotationFitsLookup(self, fits_path: str) -> Optional[int]:
        """Resolves a FITS path to its EPS fits_id, or None if not ingested.

        Matches on the full path, not the basename: the ingestion pipeline
        (``PollingThread``/``process_file``) registers each FITS file under
        the exact path the filesystem watcher observed it at
        (``pipeline:ingress:polling_location`` + filename), and EPS matches
        ``fileName`` with SQL equality, not a LIKE/substring query.
        """
        records = self._repository.query_fits_sync(
            FitsQueryFilter(filename=fits_path)
        )
        if records:
            return records[0].fits_id
        return None

    def _onAnnotationClusterFetch(
        self, fits_id: int, hdu_id: int
    ) -> List[Cluster]:
        """Fetches clusters for a FITS/HDU and hydrates their pixel data.

        Slices pixel data from the already-loaded raw HDU array rather than
        re-reading the FITS file from disk, since Raw Data Analysis already
        holds it in memory. Returns an empty list if the active raw data is
        unavailable (e.g. the file/HDU changed again while this fetch was
        in flight) rather than risk hydrating from the wrong HDU.

        EPS-sourced clusters store ``boundingBox.top``/``bottom`` with the
        axis flipped relative to locally-extracted ones (see
        ``ClusterLocationMapWidget._draw_bbox``), so the row span is
        normalized with min/max rather than assumed ordered.
        """
        clusters = self._repository.fetch_clusters_sync(
            ClusterQueryFilter(fits_id=fits_id, hdu_id=hdu_id)
        )
        raw = self.viewModel.activeRawData
        if raw is None:
            return []
        for cluster in clusters:
            bb = cluster.boundingBox
            row_lo, row_hi = min(bb.top, bb.bottom), max(bb.top, bb.bottom)
            col_lo, col_hi = min(bb.left, bb.right), max(bb.left, bb.right)
            cluster.data = raw[row_lo:row_hi, col_lo:col_hi]
        return clusters

    def _onClassifyRequested(self, clusters: List[ClusteredEventInfo]) -> None:
        # TODO(#XXX): Replace MockClassifierService with the production
        # ZMQBasedClassifierService once it is wired through ServicesManager.
        from le_beta_vis.common import MockClassifierService
        from ...viewmodels.RawClusterClassificationViewModel import (
            RawClusterClassificationViewModel,
        )
        from ._RawClusterClassificationDialog import _RawClusterClassificationDialog

        vm = RawClusterClassificationViewModel(
            clusters=clusters,
            service=MockClassifierService(),
            physics=self.viewModel.physics_manager,
        )
        dialog = _RawClusterClassificationDialog(vm, parent=self.window())
        dialog.exec()
        # Propagate scores regardless of accept/reject. Scores are only present
        # when the user reached POST phase; empty dict is a safe no-op.
        self._cavm.applyClassificationScores(vm.scores)

    def openClusterForAnalysis(
        self,
        fitsPath: str,
        hdu_id: Optional[int],
        roi: Tuple[int, int, int, int],
    ) -> None:
        """Loads a FITS, selects an HDU, and pans to an ROI at 1× zoom.

        Pre-selects the ROI Info tab, resets the zoom to 1×, clears
        existing ROIs, and stashes the pending pan state. The render
        completes asynchronously; ``_consumePendingClusterFocus`` fires on
        the next image-changed callback to drop the ROI and pan the view.

        Args:
            fitsPath: Absolute path to the FITS file.
            hdu_id: Parent HDU index, or None to keep the default.
            roi: (top, left, bottom, right) in FITS pixel coordinates.
        """
        self._rightSidebar.focusRoiTab()
        self.viewModel.resetZoom()
        self._cavm.clearRois()
        self._pendingClusterFocus = (hdu_id, roi)
        self._pendingClusterRoiAdded = False
        self.viewModel.loadFile(fitsPath)
        if hdu_id is not None:
            self.viewModel.setActiveHDU(hdu_id)

    @Slot()
    def _consumePendingClusterFocus(self) -> None:
        """Adds the ROI and pans the captureView to its center.

        Invoked via image-changed callback after ``openClusterForAnalysis``
        sets ``_pendingClusterFocus``. Latched via ``_pendingClusterRoiAdded``
        so multiple renders (auto-HDU-0 + explicit-HDU) only add the ROI once.
        """
        if self._pendingClusterFocus is None:
            return
        _hdu_id, (top, left, bottom, right) = self._pendingClusterFocus

        if not self._pendingClusterRoiAdded:
            self._cavm.addRoi(top, left, bottom, right)
            self._pendingClusterRoiAdded = True

        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        self._centerArea.centerOn(cx, cy)

        self._pendingClusterFocus = None
        self._pendingClusterRoiAdded = False
