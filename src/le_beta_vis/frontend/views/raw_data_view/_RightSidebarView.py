from PySide6.QtWidgets import (
    QFrame,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.RawDataViewModel import RawDataViewModel
from ..ClusterAnalysisView import ClusterAnalysisView
from ._ROIInfoWidget import _ROIInfoWidget
from ._RawDataViewStyle import _Style
from .filter_pipeline_panel import FilterPipelinePanelView


class _RightSidebarView(QFrame):
    """Right sidebar: visualization controls, clustering tab, ROI info tab.

    Scaling mode and colormap selection used to live in dedicated
    QComboBox controls at the top of the Vis tab; they now live as
    pinned cards inside :class:`FilterPipelinePanelView` so the
    pipeline reads as a single composable chain.
    """

    def __init__(self, viewModel: RawDataViewModel) -> None:
        super().__init__()
        self._vm = viewModel
        self._initUI()

    def _initUI(self) -> None:
        self.setFixedWidth(300)
        self.setStyle(QStyleFactory.create("Fusion"))
        self.setStyleSheet(_Style.RIGHT_SIDEBAR)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._buildVisualizationTab(), self.tr("Vis"))
        self._tabs.addTab(self._buildClusteringTab(), self.tr("Clustering"))
        self._roiInfoTabIndex = self._tabs.addTab(
            self._buildRoiInfoTab(), self.tr("ROI Info")
        )
        layout.addWidget(self._tabs, 1)

    def _buildVisualizationTab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self._filterPipelinePanel = FilterPipelinePanelView(
            self._vm.filterStackViewModel,
            self._vm,
        )
        layout.addWidget(self._filterPipelinePanel, 1)

        return container

    def _buildClusteringTab(self) -> QWidget:
        view = ClusterAnalysisView(self._vm.clusterAnalysisViewModel)
        view.setContentsMargins(4, 4, 4, 4)
        return view

    def _buildRoiInfoTab(self) -> QWidget:
        return _ROIInfoWidget(self._vm)

    def focusRoiTab(self) -> None:
        """Switch the tab widget to the ROI Info tab."""
        self._tabs.setCurrentIndex(self._roiInfoTabIndex)
