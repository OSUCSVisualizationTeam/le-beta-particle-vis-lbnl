"""Read-only detail dialog for a persistent cluster annotation.

Private to the raw_data_view package. Shows the same cluster image +
classification presentation used by FeaturedClusterWidget/
HistoricalEventInspector, with a Close action and an Export-to-h5 action.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from ...fitsconverters import Colormap
from ...services.RawClusterExportService import RawClusterExportService
from ...viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from ...widgets.ClusterDetailWidget import ClusterDetailWidget
from ...widgets.EnergyClusterWidget import EnergyClusterWidget

_THUMBNAIL_SIZE = 256


class _AnnotationDetailDialog(QDialog):
    """Read-only cluster inspector with Close and Export actions.

    Stays open after a successful export so the user can keep inspecting
    the cluster; the export outcome is surfaced via QMessageBox only.
    """

    _exportSucceeded = Signal(str)
    _exportFailed = Signal(str)

    def __init__(
        self,
        cluster: Cluster,
        physics: PhysicsConversionManager,
        threshold: float,
        colormap: Colormap,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._cluster = cluster
        self._physics = physics
        self._exportService = RawClusterExportService()
        self.setWindowTitle(self.tr("Cluster Annotation"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        if parent is not None:
            self.setMaximumWidth(parent.width() - 40)
            self.setMaximumHeight(parent.height() - 40)
        self._inspectorVm = HistoricalEventInspectorViewModel(
            physics=physics, threshold=threshold, displayKeV=True,
        )
        self._initUI()
        self._exportSucceeded.connect(self._onExportSucceeded)
        self._exportFailed.connect(self._onExportFailed)
        self._inspectorVm.setEvent(cluster)
        self._detailWidget.setCluster(cluster)
        self._imageWidget.setCluster(cluster.data, colormap)

    # ------------------------------------------------------------------- UI

    def _initUI(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.setSpacing(16)

        self._imageWidget = EnergyClusterWidget(
            size=_THUMBNAIL_SIZE, enable_hover_tooltip=True,
        )
        self._imageWidget.set_kev_converter(self._physics.adu_to_kev)
        top.addWidget(self._imageWidget)

        self._detailWidget = ClusterDetailWidget(
            self._inspectorVm, show_filename=True, show_open_action=False,
        )
        top.addWidget(self._detailWidget, 1)
        root.addLayout(top)

        root.addLayout(self._buildButtonRow())

    def _buildButtonRow(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 12, 0, 0)
        row.addStretch()

        closeBtn = QPushButton(self.tr("Close"))
        closeBtn.setProperty("styleRole", "secondary")
        closeBtn.clicked.connect(self.reject)
        row.addWidget(closeBtn)
        row.addSpacing(8)

        exportBtn = QPushButton(self.tr("Export"))
        exportBtn.setProperty("styleRole", "primary")
        exportBtn.clicked.connect(self._onExportClicked)
        row.addWidget(exportBtn)

        return row

    # ------------------------------------------------------------------ export

    def _onExportClicked(self) -> None:
        suggested = f"cluster_{self._cluster.clusterId}.h5"
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Cluster"),
            suggested,
            self.tr("HDF5 Files (*.h5)"),
        )
        if not path:
            return
        if not path.lower().endswith(".h5"):
            path += ".h5"
        self._exportService.export_cluster(
            self._cluster,
            Path(path),
            self._physics,
            on_complete=lambda out_path: self._exportSucceeded.emit(str(out_path)),
            on_error=self._exportFailed.emit,
        )

    @Slot(str)
    def _onExportSucceeded(self, path: str) -> None:
        QMessageBox.information(
            self,
            self.tr("Export Complete"),
            self.tr("Cluster exported to {path}").format(path=path),
        )

    @Slot(str)
    def _onExportFailed(self, message: str) -> None:
        QMessageBox.critical(self, self.tr("Export Failed"), message)
