"""Compact filter toolbar for the Historical Analysis tab.

Provides quick access to the most common filter fields (time range,
minimum energy, minimum pixel count) and an Advanced button that
opens the full filter dialog.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStyle,
    QWidget,
)

from ..viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)
from .HistoricalAdvancedFilterDialog import (
    HistoricalAdvancedFilterDialog,
)


class _Style:
    BAR = "background-color: #1e1e1e; padding: 2px 4px;"
    LABEL = "color: #cccccc; font-size: 11px;"
    COUNT_LABEL = "color: #aaaaaa; font-size: 11px;"
    COMBO = (
        "QComboBox {"
        "  background-color: #3d3d3d;"
        "  color: #eeeeee;"
        "  border: 1px solid #555555;"
        "  border-radius: 3px;"
        "  padding: 2px 4px;"
        "  font-size: 11px;"
        "  min-width: 110px;"
        "}"
        "QComboBox:focus {"
        "  border: 1px solid #0078d7;"
        "}"
        "QComboBox::drop-down {"
        "  border: none;"
        "}"
        "QComboBox QAbstractItemView {"
        "  background-color: #3d3d3d;"
        "  color: #eeeeee;"
        "  selection-background-color: #0078d7;"
        "}"
    )
    SPINBOX = (
        "QDoubleSpinBox, QSpinBox {"
        "  background-color: #3d3d3d;"
        "  color: #eeeeee;"
        "  border: 1px solid #555555;"
        "  border-radius: 3px;"
        "  padding: 2px;"
        "  font-size: 11px;"
        "  min-width: 80px;"
        "}"
        "QDoubleSpinBox:focus, QSpinBox:focus {"
        "  border: 1px solid #0078d7;"
        "}"
    )
    APPLY_BTN = (
        "QPushButton {"
        "  background-color: #0078d7;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "  padding: 4px 14px;"
        "  font-weight: bold;"
        "  font-size: 11px;"
        "}"
        "QPushButton:hover {"
        "  background-color: #005fa3;"
        "}"
    )
    ADVANCED_BTN = (
        "QPushButton {"
        "  background-color: #3d3d3d;"
        "  color: #cccccc;"
        "  border: 1px solid #555555;"
        "  border-radius: 4px;"
        "  padding: 4px 10px;"
        "  font-size: 11px;"
        "}"
        "QPushButton:hover {"
        "  background-color: #505050;"
        "}"
    )
    ICON_BTN = (
        "QPushButton {"
        "  background-color: #3d3d3d;"
        "  color: #cccccc;"
        "  border: 1px solid #555555;"
        "  border-radius: 4px;"
        "  padding: 4px;"
        "}"
        "QPushButton:hover {"
        "  background-color: #505050;"
        "}"
    )


# Time-preset display labels, in combo order.
_TIME_PRESETS = [
    ("24h", "Last 24 hours"),
    ("3d", "Last 3 days"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("custom", "Custom"),
]


class HistoricalFilterBar(QFrame):
    """Horizontal filter toolbar for the Historical Analysis tab.

    Presents the most-used filter fields inline and delegates
    to ``HistoricalAdvancedFilterDialog`` for the full set.
    """

    def __init__(
        self,
        viewModel: HistoricalFilterBarViewModel,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self._vm = viewModel
        self._initUI()
        self._bindViewModel()

    # --- UI Construction ---

    def _initUI(self) -> None:
        self.setStyleSheet(_Style.BAR)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        # Mode label (updated by HistoricalView)
        self._modeLabel = QLabel()
        layout.addWidget(self._modeLabel)

        # Time combo
        lbl = QLabel(self.tr("Time:"))
        lbl.setStyleSheet(_Style.LABEL)
        layout.addWidget(lbl)

        self._timeCombo = QComboBox()
        self._timeCombo.setStyleSheet(_Style.COMBO)
        for key, label in _TIME_PRESETS:
            self._timeCombo.addItem(self.tr(label), key)
        self._selectTimePreset(self._vm.time_preset)
        self._timeCombo.currentIndexChanged.connect(self._onTimeComboChanged)
        layout.addWidget(self._timeCombo)

        # Energy spinbox
        unit = self._vm.energy_unit_label
        self._energyLabel = QLabel(self.tr("Min Energy ({unit}):").format(unit=unit))
        self._energyLabel.setStyleSheet(_Style.LABEL)
        layout.addWidget(self._energyLabel)

        self._energySpin = QDoubleSpinBox()
        self._energySpin.setStyleSheet(_Style.SPINBOX)
        self._energySpin.setRange(0.0, 999999.0)
        self._energySpin.setDecimals(2)
        self._energySpin.setSingleStep(0.01)
        self._energySpin.setSpecialValueText(self.tr("Any"))
        self._energySpin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        self._energySpin.setValue(0.0)
        layout.addWidget(self._energySpin)

        # Pixels spinbox
        lbl2 = QLabel(self.tr("Min Pixels:"))
        lbl2.setStyleSheet(_Style.LABEL)
        layout.addWidget(lbl2)

        self._pixelsSpin = QSpinBox()
        self._pixelsSpin.setStyleSheet(_Style.SPINBOX)
        self._pixelsSpin.setRange(0, 999999)
        self._pixelsSpin.setSingleStep(1)
        self._pixelsSpin.setSpecialValueText(self.tr("Any"))
        self._pixelsSpin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self._pixelsSpin.setValue(0)
        layout.addWidget(self._pixelsSpin)

        layout.addStretch()

        # Reset button
        self._resetBtn = QPushButton()
        self._resetBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._resetBtn.setToolTip(self.tr("Reset Filters"))
        self._resetBtn.setStyleSheet(_Style.ICON_BTN)
        self._resetBtn.clicked.connect(self._onResetClicked)
        layout.addWidget(self._resetBtn)

        # Advanced button
        self._advancedBtn = QPushButton(self.tr("Advanced\u2026"))
        self._advancedBtn.setStyleSheet(_Style.ADVANCED_BTN)
        self._advancedBtn.clicked.connect(self._onAdvancedClicked)
        layout.addWidget(self._advancedBtn)

        # Apply button
        self._applyBtn = QPushButton(self.tr("Apply"))
        self._applyBtn.setStyleSheet(_Style.APPLY_BTN)
        self._applyBtn.clicked.connect(self._onApplyClicked)
        layout.addWidget(self._applyBtn)

        # Count label (updated by HistoricalView)
        self._countLabel = QLabel()
        self._countLabel.setStyleSheet(_Style.COUNT_LABEL)
        layout.addWidget(self._countLabel)

    @property
    def modeLabel(self) -> QLabel:
        """The mode label widget (written by HistoricalView)."""
        return self._modeLabel

    @property
    def countLabel(self) -> QLabel:
        """The event-count label widget (written by HistoricalView)."""
        return self._countLabel

    # --- ViewModel binding ---

    def _bindViewModel(self) -> None:
        self._vm.add_filter_reset_callback(self._syncFromViewModel)

    def _syncFromViewModel(self) -> None:
        """Pulls current VM state into all widgets."""
        self._selectTimePreset(self._vm.time_preset)

        energy = self._vm.min_total_energy
        self._energySpin.setValue(energy if energy is not None else 0.0)

        pixels = self._vm.min_total_pixels
        self._pixelsSpin.setValue(pixels if pixels is not None else 0)

        unit = self._vm.energy_unit_label
        self._energyLabel.setText(self.tr("Min Energy ({unit}):").format(unit=unit))

    # --- Slots ---

    def _onTimeComboChanged(self, index: int) -> None:
        key = self._timeCombo.itemData(index)
        if key == "custom":
            self._openAdvancedDialog()
            return
        self._vm.time_preset = key

    def _onApplyClicked(self) -> None:
        self._pushToViewModel()
        self._vm.apply()

    def _onResetClicked(self) -> None:
        self._vm.reset()
        self._vm.apply()

    def _onAdvancedClicked(self) -> None:
        self._openAdvancedDialog()

    # --- Helpers ---

    def _pushToViewModel(self) -> None:
        """Writes inline widget values into the VM fields.

        For non-custom time presets the VM also resolves the preset to a
        fresh ``[now-window, now]`` range so clicking Apply always queries
        the most recent window.
        """
        energy = self._energySpin.value()
        self._vm.min_total_energy = energy if energy > 0.0 else None

        pixels = self._pixelsSpin.value()
        self._vm.min_total_pixels = pixels if pixels > 0 else None

        self._vm.apply_time_preset(self._timeCombo.currentData())

    def _selectTimePreset(self, preset: str) -> None:
        """Sets the combo to match a preset key."""
        for i in range(self._timeCombo.count()):
            if self._timeCombo.itemData(i) == preset:
                self._timeCombo.setCurrentIndex(i)
                return

    def _openAdvancedDialog(self) -> None:
        """Opens the advanced filter dialog."""
        self._pushToViewModel()
        dlg = HistoricalAdvancedFilterDialog(self._vm, parent=self)
        dlg.exec()
        # After the dialog closes, sync widgets from VM state
        self._syncFromViewModel()
