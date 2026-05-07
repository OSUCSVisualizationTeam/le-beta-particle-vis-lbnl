from typing import Optional, Tuple

from PySide6.QtCore import (
    QMetaObject,
    Qt,
    Slot,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.ClusterAnalysisViewModel import ClusteringState
from ...viewmodels.RawDataViewModel import RawDataViewModel
from ..MosaicView import MosaicView
from ._CenterImageAreaView import _CenterImageAreaView
from ._LeftToolbarView import _LeftToolbarView
from ._RightSidebarView import _RightSidebarView


class RawDataView(QWidget):
    def __init__(self, viewModel: RawDataViewModel):
        super().__init__()
        self.viewModel = viewModel
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
        self._rightSidebar.syncSelectors()

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
