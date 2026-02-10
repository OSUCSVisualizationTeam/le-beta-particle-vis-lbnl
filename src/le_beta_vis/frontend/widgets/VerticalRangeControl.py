from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QDoubleSpinBox,
    QSizePolicy,
    QLabel,
    QStackedLayout,
)
from PySide6.QtCore import Qt, Signal
from superqt import QRangeSlider
from typing import Tuple, Optional
from le_beta_vis.frontend.fitsconverters.colormaps import generate_gradient_pixmap

# QSS Stylesheet for the transparent range slider
SLIDER_STYLE = """
    QRangeSlider {
        background: transparent;
    }
    QRangeSlider::groove:vertical {
        background: transparent;
        width: 20px; /* Wider hit area for better interaction */
    }
    QRangeSlider::handle:vertical {
        background: #ffffff;
        border: 1px solid #5c5c5c;
        border-radius: 2px;
        height: 10px;
        margin: 0 -4px; /* Expand handle slightly beyond the groove */
    }
"""


class GradientBar(QLabel):
    """
    Vertical bar displaying a colormap gradient pixmap.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(20)  # Prevent collapse to 0 height
        # Default gradient
        self.setColormap("viridis")

    def setColormap(self, name: str):
        pixmap = generate_gradient_pixmap(name)
        if not pixmap.isNull():
            self.setPixmap(pixmap)


class VerticalRangeControl(QWidget):
    """
    Unified vertical control for setting visualization thresholds.
    Features:
    - Top SpinBox (Max)
    - Vertical Slider overlaid on Gradient Legend
    - Bottom SpinBox (Min)

    The slider operates in integer steps mapped to the float range [abs_min, abs_max].
    """

    rangeChanged = Signal(float, float)

    def __init__(self, abs_min: float, abs_max: float, steps: int = 1000, parent=None):
        super().__init__(parent)

        self._abs_min = abs_min
        self._abs_max = abs_max
        self._steps = steps

        if self._abs_max <= self._abs_min:
            raise ValueError("abs_max must be greater than abs_min")

        self.initUI()

    def initUI(self):
        """Initializes the UI layout and components."""
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(2, 2, 2, 2)
        self.mainLayout.setSpacing(5)

        self._setupLabels()
        self._setupSpinBoxes()
        self._setupSliderStack()

        self.mainLayout.addWidget(self.lblAbsMax)
        self.mainLayout.addWidget(self.spinMax)
        self.mainLayout.addWidget(self.midContainer)
        self.mainLayout.addWidget(self.spinMin)
        self.mainLayout.addWidget(self.lblAbsMin)

    def _setupLabels(self):
        """Initializes the absolute range labels."""
        self.lblAbsMax = QLabel(self._formatLabel(self._abs_max))
        self.lblAbsMax.setAlignment(Qt.AlignCenter)
        self.lblAbsMax.setStyleSheet("color: #888; font-size: 10px;")
        self.lblAbsMax.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.lblAbsMin = QLabel(self._formatLabel(self._abs_min))
        self.lblAbsMin.setAlignment(Qt.AlignCenter)
        self.lblAbsMin.setStyleSheet("color: #888; font-size: 10px;")
        self.lblAbsMin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _setupSpinBoxes(self):
        """Initializes the top and bottom spinboxes."""
        self.spinMax = QDoubleSpinBox()
        self.spinMax.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spinMax.setAlignment(Qt.AlignCenter)
        self.spinMax.setRange(self._abs_min, self._abs_max)
        self.spinMax.setDecimals(2)
        self.spinMax.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.spinMax.editingFinished.connect(self._onSpinBoxChanged)

        self.spinMin = QDoubleSpinBox()
        self.spinMin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spinMin.setAlignment(Qt.AlignCenter)
        self.spinMin.setRange(self._abs_min, self._abs_max)
        self.spinMin.setDecimals(2)
        self.spinMin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.spinMin.editingFinished.connect(self._onSpinBoxChanged)

    def _setupSliderStack(self):
        """Initializes the stacked layout containing the gradient and slider."""
        self.midContainer = QWidget()
        self.midContainer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.midContainer.setMinimumHeight(50)  # Ensure minimum interaction area

        stackLayout = QStackedLayout(self.midContainer)
        stackLayout.setStackingMode(QStackedLayout.StackAll)

        self.gradient = GradientBar()
        stackLayout.addWidget(self.gradient)

        self.slider = QRangeSlider(Qt.Vertical)
        self.slider.setRange(0, self._steps)
        self.slider.setStyleSheet(SLIDER_STYLE)
        self.slider.valueChanged.connect(self._onSliderChanged)

        stackLayout.addWidget(self.slider)
        stackLayout.setCurrentWidget(self.slider)

    def setAbsoluteRange(self, abs_min: float, abs_max: float):
        """Sets the absolute limits of the control."""
        self._abs_min = abs_min
        self._abs_max = abs_max

        # Update Labels
        self.lblAbsMax.setText(self._formatLabel(abs_max))
        self.lblAbsMin.setText(self._formatLabel(abs_min))

        self.spinMin.setRange(abs_min, abs_max)
        self.spinMax.setRange(abs_min, abs_max)

        cur_min = max(self.spinMin.value(), abs_min)
        cur_max = min(self.spinMax.value(), abs_max)
        self.setValues(cur_min, cur_max)

    def _formatLabel(self, value: float) -> str:
        """Formats the value for display (compact, with units)."""
        if abs(value) >= 1000 or (abs(value) < 0.01 and value != 0):
            return f"{value:.1e} keV"
        return f"{value:.1f} keV"

    def setValues(self, vmin: float, vmax: float):
        """Sets the current active threshold range."""
        self.blockSignals(True)

        self.spinMin.blockSignals(True)
        self.spinMax.blockSignals(True)
        self.spinMin.setValue(vmin)
        self.spinMax.setValue(vmax)
        self.spinMin.blockSignals(False)
        self.spinMax.blockSignals(False)

        s_min = self._to_slider(vmin)
        s_max = self._to_slider(vmax)

        self.slider.blockSignals(True)
        self.slider.setValue((s_min, s_max))
        self.slider.blockSignals(False)

        self.blockSignals(False)

    def setColormap(self, name: str):
        self.gradient.setColormap(name)

    def _onSliderChanged(self, values: Tuple[int, int]):
        vmin = self._from_slider(values[0])
        vmax = self._from_slider(values[1])

        self.spinMin.blockSignals(True)
        self.spinMax.blockSignals(True)
        self.spinMin.setValue(vmin)
        self.spinMax.setValue(vmax)
        self.spinMin.blockSignals(False)
        self.spinMax.blockSignals(False)

        self.rangeChanged.emit(vmin, vmax)

    def _onSpinBoxChanged(self):
        vmin = self.spinMin.value()
        vmax = self.spinMax.value()

        if vmin > vmax:
            vmin, vmax = vmax, vmin
            self.spinMin.setValue(vmin)
            self.spinMax.setValue(vmax)

        s_min = self._to_slider(vmin)
        s_max = self._to_slider(vmax)

        self.slider.blockSignals(True)
        self.slider.setValue((s_min, s_max))
        self.slider.blockSignals(False)

        self.rangeChanged.emit(vmin, vmax)

    def _to_slider(self, val: float) -> int:
        denom = self._abs_max - self._abs_min
        if denom <= 0:
            return 0
        ratio = (val - self._abs_min) / denom
        return int(ratio * self._steps)

    def _from_slider(self, val: int) -> float:
        ratio = val / self._steps
        return self._abs_min + ratio * (self._abs_max - self._abs_min)
