"""View for cluster extraction controls and results.

Extracted from RawDataView to live inside a tabbed sidebar.
Binds to ``ClusterAnalysisViewModel`` for all clustering state.
"""

from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.ClusterAnalysisViewModel import ClusterAnalysisViewModel
from ..widgets.ClusteredEventWidget import ClusteredEventWidget


class ClusterAnalysisView(QWidget):
    """Cluster extraction controls plus clustered event results list."""

    def __init__(
        self,
        viewModel: ClusterAnalysisViewModel,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._initUI()
        self._bindViewModel()

    # --- UI Setup ---

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._addExtractionSection(layout)
        self._addResultsSection(layout)

    def _addExtractionSection(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox(self.tr("Cluster Extraction"))
        vbox = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("\u03c3 threshold")))
        self._thresholdSpinBox = QDoubleSpinBox()
        self._thresholdSpinBox.setRange(0.1, 100.0)
        self._thresholdSpinBox.setSingleStep(0.5)
        self._thresholdSpinBox.setDecimals(1)
        self._thresholdSpinBox.setValue(self._vm.clusteringThreshold)
        row.addWidget(self._thresholdSpinBox)
        vbox.addLayout(row)

        self._btnRunExtraction = QPushButton(self.tr("Run Extraction"))
        self._btnRunExtraction.setEnabled(False)
        self._btnRunExtraction.clicked.connect(self._vm.triggerClustering)
        vbox.addWidget(self._btnRunExtraction)

        parent_layout.addWidget(group)

    def _addResultsSection(self, parent_layout: QVBoxLayout) -> None:
        self._clusteredEventWidget = ClusteredEventWidget()
        self._clusteredEventWidget.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Expanding,
        )
        parent_layout.addWidget(self._clusteredEventWidget, 1)

    # --- ViewModel Bindings ---

    def _bindViewModel(self) -> None:
        self._bindClusteringCallbacks()
        self._bindExtractionButton()
        self._bindWidgetSignals()
        self._bindClassificationScoresCallback()

    def _bindClusteringCallbacks(self) -> None:
        def on_completed() -> None:
            QMetaObject.invokeMethod(
                self,
                "_updateClusteringResults",
                Qt.AutoConnection,
            )

        self._vm.add_clustering_completed_callback(on_completed)

        def on_selected_changed() -> None:
            QMetaObject.invokeMethod(
                self,
                "_updateSelectedCluster",
                Qt.QueuedConnection,
            )

        self._vm.add_selected_cluster_changed_callback(
            on_selected_changed,
        )

    def _bindClassificationScoresCallback(self) -> None:
        def on_scores_changed() -> None:
            QMetaObject.invokeMethod(
                self,
                "_updateClassificationScores",
                Qt.AutoConnection,
            )

        self._vm.add_classification_scores_changed_callback(on_scores_changed)

    def _bindExtractionButton(self) -> None:
        def refresh() -> None:
            QMetaObject.invokeMethod(
                self,
                "_refreshExtractionButton",
                Qt.QueuedConnection,
            )

        self._vm.add_active_tool_changed_callback(refresh)
        self._vm.add_roi_changed_callback(refresh)
        self._vm.add_clustering_state_changed_callback(refresh)

    def _bindWidgetSignals(self) -> None:
        self._clusteredEventWidget.clustersSelected.connect(
            self._vm.selectClusters,
        )
        self._clusteredEventWidget.classifyRequested.connect(
            self._vm.classifySelectedCluster,
        )
        self._clusteredEventWidget.exportRequested.connect(
            self._vm.exportSelectedCluster,
        )

    # --- Slots ---

    @Slot()
    def _updateClusteringResults(self) -> None:
        """Populates the clustered event widget from ViewModel results."""
        self._clusteredEventWidget.setColormap(
            self._vm.clusterThumbnailColormap,
        )
        self._clusteredEventWidget.setDisplayEnergyInKev(
            self._vm.displayEnergyInKev,
        )
        self._clusteredEventWidget.setKevConversion(
            self._vm.kevConversion,
        )
        self._clusteredEventWidget.setResults(
            self._vm.clusteringResults,
        )

    @Slot()
    def _updateSelectedCluster(self) -> None:
        """Syncs the widget's multi-selection with ViewModel state."""
        self._clusteredEventWidget.setSelectedIndices(
            self._vm.selectedClusterIndices,
        )

    @Slot()
    def _updateClassificationScores(self) -> None:
        """Overlays ML scores on cluster rows after classification completes."""
        self._clusteredEventWidget.updateClassificationResults(
            self._vm.classificationScores,
        )

    @Slot()
    def _refreshExtractionButton(self) -> None:
        """Enables Run Extraction when clustering is available."""
        self._btnRunExtraction.setEnabled(
            self._vm.isClusteringAvailable,
        )
