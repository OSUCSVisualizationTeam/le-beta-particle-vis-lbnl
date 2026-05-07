"""Ground-truth labeling dialog for exporting clusters to EPS for retraining.

Private to the raw_data_view package. Binds to RawClusterLabelingViewModel.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QMetaObject, QSize, Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
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
from ...theme import RawClusterLabelingDialogColors as _C
from ...viewmodels.RawClusterLabelingViewModel import Phase, RawClusterLabelingViewModel
from ...widgets.ArcSpinner import ArcSpinner
from ...widgets.EnergyClusterWidget import EnergyClusterWidget
from le_beta_vis.common.ParticleType import ParticleType

_THUMBNAIL_SIZE = 64
_PARTICLE_TYPES = list(ParticleType)


class _RawClusterLabelingDialog(QDialog):
    """Shows selected clusters with per-row particle type selectors.

    Three-page flow managed by a QStackedWidget:
      0 — FORM: callout + label-all + scroll area of cluster rows
      1 — SPINNER: ArcSpinner while submission is in flight
      2 — RESULT: summary label + OK button

    Never exceeds the size of the parent window.
    """

    _PAGE_FORM = 0
    _PAGE_SPINNER = 1
    _PAGE_RESULT = 2

    def __init__(
        self,
        viewModel: RawClusterLabelingViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._row_combos: List[QComboBox] = []
        self.setWindowTitle(self.tr("Export for Training"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(480)
        if parent is not None:
            self.setMaximumSize(parent.size() - QSize(40, 40))
        self._initUI()
        self._bindViewModel()

    # ------------------------------------------------------------------- UI

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._buildFormPage())
        self._stack.addWidget(self._buildSpinnerPage())
        self._stack.addWidget(self._buildResultPage())
        root.addWidget(self._stack, 1)

        root.addLayout(self._buildButtonRow())

    def _buildFormPage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(10)

        layout.addWidget(self._buildCallout())
        layout.addWidget(self._buildLabelAllRow())
        layout.addWidget(self._buildScrollArea(), 1)
        return page

    def _buildCallout(self) -> QLabel:
        callout = QLabel(
            self.tr(
                "Assign a particle type to each cluster to add it as a ground-truth "
                "label. Submitted clusters are available for the next CNN, NRG, and "
                "BDT retraining cycle. Clusters left as ‘?’ are not submitted."
            )
        )
        callout.setWordWrap(True)
        callout.setStyleSheet(
            f"background-color: {_C.CALLOUT_BACKGROUND};"
            f"border: 1px solid {_C.CALLOUT_BORDER};"
            f"color: {_C.CALLOUT_TEXT};"
            "border-radius: 4px;"
            "padding: 8px 10px;"
            "font-size: 12px;"
        )
        return callout

    def _buildLabelAllRow(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(self.tr("Label all:")))
        self._labelAllCombo = QComboBox()
        for pt in _PARTICLE_TYPES:
            self._labelAllCombo.addItem(pt.symbol, pt)
        self._labelAllCombo.setCurrentIndex(
            _PARTICLE_TYPES.index(ParticleType.UNCLASSIFIED)
        )
        self._labelAllCombo.currentIndexChanged.connect(self._onLabelAllChanged)
        row.addWidget(self._labelAllCombo)
        row.addStretch()
        return container

    def _buildScrollArea(self) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        self._row_combos = []
        for i, cluster in enumerate(self._vm.clusters):
            row_widget, combo = self._buildClusterRow(i, cluster)
            self._row_combos.append(combo)
            content_layout.addWidget(row_widget)

        content_layout.addStretch()
        area.setWidget(content)
        return area

    def _buildClusterRow(self, index: int, cluster) -> tuple:
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

        sigma_label = QLabel(
            self.tr(
                "σx {sx:.1f}  σy {sy:.1f}  {px} px"
            ).format(
                sx=cluster.sigmaX,
                sy=cluster.sigmaY,
                px=cluster.pixelCount,
            )
        )
        info.addWidget(sigma_label)

        energy_label = QLabel(
            self.tr("{e:.2f} keV").format(e=self._vm.energy_kev(index))
        )
        info.addWidget(energy_label)

        label_row = QHBoxLayout()
        label_row.addWidget(QLabel(self.tr("Label:")))
        combo = QComboBox()
        for pt in _PARTICLE_TYPES:
            combo.addItem(pt.symbol, pt)
        combo.setCurrentIndex(_PARTICLE_TYPES.index(ParticleType.UNCLASSIFIED))
        combo.currentIndexChanged.connect(
            lambda _, idx=index, c=combo: self._onRowLabelChanged(idx, c)
        )
        label_row.addWidget(combo)
        label_row.addStretch()
        info.addLayout(label_row)

        h.addLayout(info, 1)
        return row, combo

    def _buildSpinnerPage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self._spinner = ArcSpinner()
        self._spinner.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self._spinner, 0, Qt.AlignHCenter)

        self._spinnerLabel = QLabel(self.tr("Submitting…"))
        self._spinnerLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._spinnerLabel)
        return page

    def _buildResultPage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self._resultLabel = QLabel()
        self._resultLabel.setAlignment(Qt.AlignCenter)
        self._resultLabel.setWordWrap(True)
        self._resultLabel.setStyleSheet(
            f"color: {_C.RESULT_TEXT}; font-size: 14px;"
        )
        layout.addWidget(self._resultLabel)
        return page

    def _buildButtonRow(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(16, 0, 0, 0)
        row.addStretch()

        self._cancelBtn = QPushButton(self.tr("Cancel"))
        self._cancelBtn.setStyleSheet(
            "QPushButton {"
            f"  background-color: {_C.CANCEL_BUTTON_BACKGROUND};"
            f"  color: {_C.CANCEL_BUTTON_FOREGROUND};"
            f"  border: 1px solid {_C.CANCEL_BUTTON_BORDER};"
            "  border-radius: 4px;"
            "  padding: 6px 16px;"
            "}"
        )
        self._cancelBtn.clicked.connect(self.reject)
        row.addWidget(self._cancelBtn)

        self._submitBtn = QPushButton(self.tr("Submit"))
        self._submitBtn.setStyleSheet(
            "QPushButton {"
            f"  background-color: {_C.SUBMIT_BUTTON_BACKGROUND};"
            f"  color: {_C.SUBMIT_BUTTON_FOREGROUND};"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 6px 16px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover {"
            f"  background-color: {_C.SUBMIT_BUTTON_HOVER};"
            "}"
            "QPushButton:disabled { background-color: #555555; color: #888888; }"
        )
        self._submitBtn.clicked.connect(self._vm.submit)
        row.addWidget(self._submitBtn)

        self._okBtn = QPushButton(self.tr("OK"))
        self._okBtn.setStyleSheet(self._submitBtn.styleSheet())
        self._okBtn.clicked.connect(self.accept)
        self._okBtn.setVisible(False)
        row.addWidget(self._okBtn)

        return row

    # ------------------------------------------------------------ ViewModel binding

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
        if phase == Phase.SUBMITTING:
            self._stack.setCurrentIndex(self._PAGE_SPINNER)
            self._spinner.start()
            self._cancelBtn.setEnabled(False)
            self._submitBtn.setEnabled(False)
        elif phase == Phase.DONE:
            self._spinner.stop()
            total = len(self._vm.clusters)
            stored = self._vm.stored_count
            self._resultLabel.setText(
                self.tr(
                    "✓ {stored} of {total} cluster(s) submitted\n"
                    "for model retraining."
                ).format(stored=stored, total=total)
            )
            self._stack.setCurrentIndex(self._PAGE_RESULT)
            self._cancelBtn.setVisible(False)
            self._submitBtn.setVisible(False)
            self._okBtn.setVisible(True)
        elif phase == Phase.ERROR:
            self._spinner.stop()
            msg = self._vm.error_message or self.tr("Unknown error")
            self._resultLabel.setText(
                self.tr("Submission failed:\n{msg}").format(msg=msg)
            )
            self._resultLabel.setStyleSheet(
                "color: #ff5a5a; font-size: 14px;"
            )
            self._stack.setCurrentIndex(self._PAGE_RESULT)
            self._cancelBtn.setVisible(False)
            self._submitBtn.setVisible(False)
            self._okBtn.setVisible(True)

    def _onLabelAllChanged(self, combo_index: int) -> None:
        pt = _PARTICLE_TYPES[combo_index]
        self._vm.set_all_labels(pt)
        self._refreshAllRowCombos()

    def _onRowLabelChanged(self, cluster_index: int, combo: QComboBox) -> None:
        pt = combo.currentData()
        self._vm.set_label(cluster_index, pt)

    def _refreshAllRowCombos(self) -> None:
        for i, combo in enumerate(self._row_combos):
            combo.blockSignals(True)
            combo.setCurrentIndex(_PARTICLE_TYPES.index(self._vm.label_for(i)))
            combo.blockSignals(False)
