"""Advanced filter dialog exposing all ClusterQueryFilter fields.

Opened from the HistoricalFilterBar via the "Advanced..." button
or by selecting "Custom..." in the time combo.
"""

from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)


_TIME_PRESETS = [
    ("24h", "Last 24 hours"),
    ("3d", "Last 3 days"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
]


class HistoricalAdvancedFilterDialog(QDialog):
    """Modal dialog exposing every ``ClusterQueryFilter`` field.

    Reads/writes filter state through the shared
    ``HistoricalFilterBarViewModel``.
    """

    def __init__(
        self,
        viewModel: HistoricalFilterBarViewModel,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self._vm = viewModel
        self.setWindowTitle(self.tr("Advanced Filters"))
        self.setMinimumWidth(360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._initUI()
        self._syncFromViewModel()

    # --- UI ---

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        # Time
        self._timeCombo = QComboBox()
        for key, label in _TIME_PRESETS:
            self._timeCombo.addItem(self.tr(label), key)
        form.addRow(QLabel(self.tr("Time Range:")), self._timeCombo)

        # Start / End date-time
        self._startEdit = self._makeDateTimeEdit()
        form.addRow(
            QLabel(self.tr("Start:")),
            self._startEdit,
        )
        self._endEdit = self._makeDateTimeEdit()
        form.addRow(
            QLabel(self.tr("End:")),
            self._endEdit,
        )

        self._timeCombo.currentIndexChanged.connect(self._onTimePresetChanged)

        # Cluster ID
        self._clusterIdSpin = self._makeIntSpin()
        form.addRow(QLabel(self.tr("Cluster ID:")), self._clusterIdSpin)

        # FITS ID
        self._fitsIdSpin = self._makeIntSpin()
        form.addRow(QLabel(self.tr("FITS ID:")), self._fitsIdSpin)

        # HDU ID
        self._hduIdSpin = self._makeIntSpin()
        form.addRow(QLabel(self.tr("HDU ID:")), self._hduIdSpin)

        # Min sigma-x
        self._sigmaXSpin = self._makeDoubleSpin()
        form.addRow(
            QLabel(self.tr("Min \u03c3\u2093:")),
            self._sigmaXSpin,
        )

        # Min sigma-y
        self._sigmaYSpin = self._makeDoubleSpin()
        form.addRow(
            QLabel(self.tr("Min \u03c3\u1d67:")),
            self._sigmaYSpin,
        )

        # Min Energy
        unit = self._vm.energy_unit_label
        self._energySpin = self._makeDoubleSpin()
        self._energyLabel = QLabel(
            self.tr("Min Energy ({unit}):").format(unit=unit)
        )
        form.addRow(self._energyLabel, self._energySpin)

        # Min Pixels
        self._pixelsSpin = self._makeIntSpin()
        form.addRow(QLabel(self.tr("Min Pixels:")), self._pixelsSpin)

        # Classification
        self._classCombo = QComboBox()
        for label, value in self._vm.classification_options:
            self._classCombo.addItem(self.tr(label), value)
        form.addRow(
            QLabel(self.tr("Classification:")),
            self._classCombo,
        )

        root.addLayout(form)
        root.addStretch()

        # Buttons
        btnRow = QHBoxLayout()
        btnRow.addStretch()

        resetBtn = QPushButton(self.tr("Reset"))
        resetBtn.setProperty("styleRole", "secondary")
        resetBtn.clicked.connect(self._onResetClicked)
        btnRow.addWidget(resetBtn)

        applyBtn = QPushButton(self.tr("Apply"))
        applyBtn.setProperty("styleRole", "primary")
        applyBtn.clicked.connect(self._onApplyClicked)
        btnRow.addWidget(applyBtn)

        root.addLayout(btnRow)

    # --- Helpers ---

    def _makeIntSpin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 999999)
        spin.setSingleStep(1)
        spin.setSpecialValueText(self.tr("Any"))
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        spin.setValue(0)
        return spin

    def _makeDoubleSpin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 999999.0)
        spin.setDecimals(4)
        spin.setSingleStep(0.01)
        spin.setSpecialValueText(self.tr("Any"))
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        spin.setValue(0.0)
        return spin

    def _makeDateTimeEdit(self) -> QDateTimeEdit:
        edit = QDateTimeEdit()
        edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        edit.setCalendarPopup(True)
        return edit

    # --- Sync ---

    def _syncFromViewModel(self) -> None:
        """Pulls VM state into all dialog widgets."""
        self._selectComboByData(self._timeCombo, self._vm.time_preset)
        self._syncDateEdits()

        self._setIntSpin(self._clusterIdSpin, self._vm.cluster_id)
        self._setIntSpin(self._fitsIdSpin, self._vm.fits_id)
        self._setIntSpin(self._hduIdSpin, self._vm.hdu_id)

        self._setDoubleSpin(self._sigmaXSpin, self._vm.min_sigma_x)
        self._setDoubleSpin(self._sigmaYSpin, self._vm.min_sigma_y)
        self._setDoubleSpin(self._energySpin, self._vm.min_total_energy)

        self._setIntSpin(self._pixelsSpin, self._vm.min_total_pixels)

        self._selectComboByData(self._classCombo, self._vm.classification)

    def _syncDateEdits(self) -> None:
        """Fills start/end date edits from VM or preset."""
        start = self._vm.start_datetime
        end = self._vm.end_datetime
        if start is None or end is None:
            key = self._timeCombo.currentData()
            start, end = self._vm.compute_dates_for_preset(key)
        self._startEdit.setDateTime(self._toQDateTime(start))
        self._endEdit.setDateTime(self._toQDateTime(end))

    def _pushToViewModel(self) -> None:
        """Writes all dialog widget values into the VM."""
        # The dialog always produces an explicit range from the date edits,
        # so the resulting filter mode is "custom" by definition. The
        # dialog's time combo is a quick-fill helper for the date edits,
        # not a semantic preset choice — a subsequent inline-bar Apply
        # would otherwise clobber these dates via apply_time_preset().
        self._vm.time_preset = "custom"

        self._vm.start_datetime = self._startEdit.dateTime().toPython()
        self._vm.end_datetime = self._endEdit.dateTime().toPython()

        self._vm.cluster_id = self._intOrNone(self._clusterIdSpin)
        self._vm.fits_id = self._intOrNone(self._fitsIdSpin)
        self._vm.hdu_id = self._intOrNone(self._hduIdSpin)

        self._vm.min_sigma_x = self._floatOrNone(self._sigmaXSpin)
        self._vm.min_sigma_y = self._floatOrNone(self._sigmaYSpin)
        self._vm.min_total_energy = self._floatOrNone(self._energySpin)
        self._vm.min_total_pixels = self._intOrNone(self._pixelsSpin)

        self._vm.classification = self._classCombo.currentData()

    # --- Slots ---

    def _onTimePresetChanged(self, _index: int) -> None:
        """Updates date edits when the user picks a preset."""
        key = self._timeCombo.currentData()
        start, end = self._vm.compute_dates_for_preset(key)
        self._startEdit.setDateTime(self._toQDateTime(start))
        self._endEdit.setDateTime(self._toQDateTime(end))

    def _onResetClicked(self) -> None:
        self._vm.reset()
        self._syncFromViewModel()

    def _onApplyClicked(self) -> None:
        self._pushToViewModel()
        self._vm.apply()
        self.accept()

    # --- Utilities ---

    @staticmethod
    def _selectComboByData(combo: QComboBox, data) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    @staticmethod
    def _setIntSpin(spin: QSpinBox, value) -> None:
        spin.setValue(value if value is not None else 0)

    @staticmethod
    def _setDoubleSpin(spin: QDoubleSpinBox, value) -> None:
        spin.setValue(value if value is not None else 0.0)

    @staticmethod
    def _intOrNone(spin: QSpinBox):
        v = spin.value()
        return v if v > 0 else None

    @staticmethod
    def _floatOrNone(spin: QDoubleSpinBox):
        v = spin.value()
        return v if v > 0.0 else None

    @staticmethod
    def _toQDateTime(dt) -> QDateTime:
        """Converts a Python ``datetime`` to a ``QDateTime``."""
        return QDateTime(
            QDate(dt.year, dt.month, dt.day),
            QTime(dt.hour, dt.minute, dt.second),
        )
