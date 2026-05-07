from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QLabel,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...fitsconverters import Colormap, ScalingFunction
from ...viewmodels.RawDataViewModel import RawDataViewModel
from ..ClusterAnalysisView import ClusterAnalysisView
from ._ROIInfoWidget import _ROIInfoWidget
from ._RawDataViewStyle import _Style


class _RightSidebarView(QFrame):
    """Right sidebar: visualization controls, clustering tab, ROI info tab."""

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

        vizGroup = QGroupBox("")
        vizLayout = QVBoxLayout(vizGroup)

        vizLayout.addWidget(QLabel(self.tr("Scaling")))
        self.scalingSelector = QComboBox()
        self.scalingSelector.addItems([s.value for s in ScalingFunction])
        self.scalingSelector.currentTextChanged.connect(
            lambda text: self._vm.setScalingFunction(text)
        )
        vizLayout.addWidget(self.scalingSelector)

        vizLayout.addWidget(QLabel(self.tr("Colormap")))
        self.cmapSelector = QComboBox()
        self.cmapSelector.addItems([c.value for c in Colormap])
        self.cmapSelector.currentTextChanged.connect(
            lambda text: self._vm.setColormap(text)
        )
        vizLayout.addWidget(self.cmapSelector)

        layout.addWidget(vizGroup)

        filterGroup = QGroupBox(self.tr("Filtering Pipeline"))
        filterLayout = QVBoxLayout(filterGroup)
        filterLayout.addWidget(QLabel(self.tr("(Not implemented yet)")))
        layout.addWidget(filterGroup)

        layout.addStretch()
        return container

    def _buildClusteringTab(self) -> QWidget:
        view = ClusterAnalysisView(self._vm.clusterAnalysisViewModel)
        view.setContentsMargins(4, 4, 4, 4)
        return view

    def _buildRoiInfoTab(self) -> QWidget:
        return _ROIInfoWidget(self._vm)

    def syncSelectors(self) -> None:
        """Sync selector widgets to match current ViewModel state."""
        self.cmapSelector.setCurrentText(self._vm.colormap)
        self.scalingSelector.setCurrentText(self._vm.scalingFunction)

    def focusRoiTab(self) -> None:
        """Switch the tab widget to the ROI Info tab."""
        self._tabs.setCurrentIndex(self._roiInfoTabIndex)
