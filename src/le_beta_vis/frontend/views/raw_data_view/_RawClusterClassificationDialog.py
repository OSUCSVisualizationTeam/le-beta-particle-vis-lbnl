"""ML classification dialog for raw-data clusters (issue #153).

Private to the raw_data_view package. Binds to RawClusterClassificationViewModel.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...fitsconverters import Colormap
from ...viewmodels.RawClusterClassificationViewModel import (
    Phase,
    RawClusterClassificationViewModel,
)
from ...widgets.ArcSpinner import ArcSpinner
from ...widgets.EnergyClusterWidget import EnergyClusterWidget

_THUMBNAIL_SIZE = 64


class _RawClusterClassificationDialog(QDialog):
    """Shows selected clusters and runs CNN/NRG/BDT classification on demand.

    Three-page flow managed by a QStackedWidget:
      0 — PRE:       cluster list + Classify / Cancel buttons
      1 — IN_FLIGHT: ArcSpinner while models are running
      2 — POST:      per-cluster CNN/NRG/BDT scores + particle badge

    Results are propagated to ClusterAnalysisViewModel by the caller after
    dialog.exec() returns regardless of accept/reject outcome.
    Never exceeds the size of the parent window.
    """

    _PAGE_PRE = 0
    _PAGE_SPINNER = 1
    _PAGE_POST = 2

    def __init__(
        self,
        viewModel: RawClusterClassificationViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._score_rows: List[QWidget] = []
        self.setWindowTitle(self.tr("Classify Clusters"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(480)
        self.setMaximumHeight(500)
        if parent is not None:
            self.setMaximumWidth(parent.width() - 40)
        self._initUI()
        self._bindViewModel()

    # ------------------------------------------------------------------- UI

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._buildPrePage())
        self._stack.addWidget(self._buildSpinnerPage())
        self._stack.addWidget(self._buildPostPage())
        root.addWidget(self._stack, 1)

        root.addLayout(self._buildButtonRow())

    def _buildCallout(self, text: str) -> QLabel:
        callout = QLabel(text)
        callout.setWordWrap(True)
        callout.setProperty("class", "callout")
        return callout

    def _buildPrePage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(10)

        layout.addWidget(
            self._buildCallout(
                self.tr(
                    "Run the CNN, NRG, and BDT models on the selected clusters. "
                    "Each cluster receives a tritium confidence score (0–100%) "
                    "from each model."
                )
            )
        )
        layout.addWidget(self._buildPreScrollArea(), 1)
        return page

    def _buildPreScrollArea(self) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        for i, cluster in enumerate(self._vm.clusters):
            content_layout.addWidget(self._buildPreRow(i, cluster))

        content_layout.addStretch()
        area.setWidget(content)
        return area

    def _buildPreRow(self, index: int, cluster) -> QFrame:
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        h = QHBoxLayout(row)
        h.setContentsMargins(6, 6, 6, 6)
        h.setSpacing(10)

        thumb = EnergyClusterWidget(size=_THUMBNAIL_SIZE)
        thumb.setCluster(cluster.data, Colormap.VIRIDIS)
        h.addWidget(thumb)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.addWidget(
            QLabel(
                self.tr("σx {sx:.1f}  σy {sy:.1f}  {px} px").format(
                    sx=cluster.sigmaX,
                    sy=cluster.sigmaY,
                    px=cluster.pixelCount,
                )
            )
        )
        info.addWidget(
            QLabel(
                self.tr("{e:.2f} keV").format(e=self._vm.energy_kev(index))
            )
        )
        h.addLayout(info, 1)
        return row

    def _buildSpinnerPage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self._spinner = ArcSpinner()
        self._spinner.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self._spinner, 0, Qt.AlignHCenter)

        lbl = QLabel(self.tr("Classifying…"))
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        return page

    def _buildPostPage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(10)

        layout.addWidget(
            self._buildCallout(self.tr("Classification complete."))
        )

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._postContent = QWidget()
        self._postLayout = QVBoxLayout(self._postContent)
        self._postLayout.setContentsMargins(0, 0, 0, 0)
        self._postLayout.setSpacing(6)
        self._postLayout.addStretch()

        area.setWidget(self._postContent)
        layout.addWidget(area, 1)
        return page

    def _buildButtonRow(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(16, 12, 16, 12)
        row.addStretch()

        self._cancelBtn = QPushButton(self.tr("Cancel"))
        self._cancelBtn.setProperty("styleRole", "secondary")
        self._cancelBtn.clicked.connect(self._onCancelClicked)
        row.addWidget(self._cancelBtn)
        row.addSpacing(8)

        self._classifyBtn = QPushButton(self.tr("Classify"))
        self._classifyBtn.setProperty("styleRole", "primary")
        self._classifyBtn.clicked.connect(self._vm.classify)
        row.addWidget(self._classifyBtn)

        return row

    # --------------------------------------------------------- ViewModel binding

    def _bindViewModel(self) -> None:
        self._vm.add_phase_changed_callback(
            lambda: QMetaObject.invokeMethod(
                self, "_onPhaseChanged", Qt.AutoConnection
            )
        )

    # ------------------------------------------------------------------ slots

    @Slot()
    def _onPhaseChanged(self) -> None:
        phase = self._vm.phase
        if phase == Phase.IN_FLIGHT:
            self._stack.setCurrentIndex(self._PAGE_SPINNER)
            self._spinner.start()
            self._classifyBtn.setEnabled(False)
            self._cancelBtn.setEnabled(False)
        elif phase == Phase.POST:
            self._spinner.stop()
            self._populatePostRows()
            self._stack.setCurrentIndex(self._PAGE_POST)
            self._classifyBtn.setEnabled(False)
            self._cancelBtn.setEnabled(True)
            self._cancelBtn.setText(self.tr("Close"))

    def _populatePostRows(self) -> None:
        """Rebuilds the POST page with per-cluster score rows."""
        while self._postLayout.count() > 1:
            item = self._postLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scores = self._vm.scores
        for i, cluster in enumerate(self._vm.clusters):
            cluster_scores = scores.get(i)
            row = self._buildPostRow(i, cluster, cluster_scores)
            self._postLayout.insertWidget(self._postLayout.count() - 1, row)

    def _buildPostRow(self, index: int, cluster, cluster_scores) -> QFrame:
        from le_beta_vis.common.ParticleType import (
            CLASSIFICATION_THRESHOLD,
            ParticleType,
        )

        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        h = QHBoxLayout(row)
        h.setContentsMargins(6, 6, 6, 6)
        h.setSpacing(10)

        thumb = EnergyClusterWidget(size=_THUMBNAIL_SIZE)
        thumb.setCluster(cluster.data, Colormap.VIRIDIS)
        h.addWidget(thumb)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.addWidget(
            QLabel(
                self.tr("σx {sx:.1f}  σy {sy:.1f}  {px} px").format(
                    sx=cluster.sigmaX,
                    sy=cluster.sigmaY,
                    px=cluster.pixelCount,
                )
            )
        )
        info.addWidget(
            QLabel(
                self.tr("{e:.2f} keV").format(e=self._vm.energy_kev(index))
            )
        )

        if cluster_scores is not None:
            for model, val in (
                ("CNN", cluster_scores.cnn),
                ("NRG", cluster_scores.nrg),
                ("BDT", cluster_scores.bdt),
            ):
                score_str = f"{val * 100:.0f}%" if val is not None else "?"
                lbl = QLabel(
                    self.tr("{model}: <b>{score}</b>").format(
                        model=model, score=score_str
                    )
                )
                lbl.setProperty("scoreLevel", self._score_level(val))
                info.addWidget(lbl)

            valid = [
                v
                for v in (cluster_scores.cnn, cluster_scores.nrg, cluster_scores.bdt)
                if v is not None
            ]
            particle = (
                ParticleType.TRITIUM
                if valid and max(valid) >= CLASSIFICATION_THRESHOLD
                else ParticleType.UNCLASSIFIED
            )
            badge = QLabel(
                self.tr("Type: {symbol}").format(symbol=particle.symbol)
            )
            info.addWidget(badge)

        h.addLayout(info, 1)
        return row

    @staticmethod
    def _score_level(val: Optional[float]) -> str:
        if val is None:
            return "low"
        if val >= 0.75:
            return "good"
        if val >= 0.5:
            return "medium"
        return "low"

    @Slot()
    def _onCancelClicked(self) -> None:
        if self._vm.phase == Phase.POST:
            self.accept()
        else:
            self.reject()
