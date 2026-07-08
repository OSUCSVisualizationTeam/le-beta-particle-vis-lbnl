import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QDoubleSpinBox,
    QPushButton,
    QSizePolicy,
    QLabel,
    QStackedLayout,
    QToolTip,
)
from PySide6.QtCore import Qt, Signal, QEvent
from superqt import QRangeSlider
from typing import Tuple
from le_beta_vis.frontend.fitsconverters.colormaps import generate_gradient_pixmap
from le_beta_vis.frontend.theme import TooltipStyle

logger = logging.getLogger(__name__)


# superqt.QRangeSlider pseudo-state styling — sanctioned exception to the
# QSS-only rule: this groove/handle/sub-page geometry is tightly coupled to
# this widget's 80px vertical slider-over-gradient layout and isn't reused
# anywhere else, so it stays a direct setStyleSheet call rather than a QSS
# rule.
_SLIDER_STYLESHEET = """
    QRangeSlider {
        background: transparent;
    }
    QRangeSlider::groove:vertical {
        background: transparent;
        width: 80px;
    }
    QRangeSlider::handle:vertical {
        background: rgba(255, 255, 255, 150);
        border: 1px solid #ffffff;
        border-radius: 0px;
        height: 4px;
        width: 80px;
    }
    QRangeSlider::sub-page:vertical {
        background: transparent;
    }
"""


class GradientBar(QLabel):
    """
    Vertical bar displaying a colormap gradient pixmap.

    The gradient is compressed between ``vmin_ratio`` and ``vmax_ratio``
    so that the colormap visually matches the active slider range.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(20)  # Prevent collapse to 0 height
        self._colormap_name: str = "viridis"
        self._vmin_ratio: float = 0.0
        self._vmax_ratio: float = 1.0
        # Default gradient
        self.setColormap("viridis")

    def setColormap(self, name: str) -> None:
        """Update the colormap and re-render the gradient."""
        self._colormap_name = name
        self._updatePixmap()

    def updateRatios(self, vmin_ratio: float, vmax_ratio: float) -> None:
        """Update the visible gradient compression range."""
        self._vmin_ratio = vmin_ratio
        self._vmax_ratio = vmax_ratio
        self._updatePixmap()

    def _updatePixmap(self) -> None:
        """Re-render the gradient pixmap from current state."""
        pixmap = generate_gradient_pixmap(
            self._colormap_name,
            self._vmin_ratio,
            self._vmax_ratio,
        )
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
        """
        Initializes the unified vertical range control.

        :param abs_min: The absolute minimum value of the data range.
        :param abs_max: The absolute maximum value of the data range.
        :param steps: The number of discrete steps in the internal slider (integer).
        :param parent: Optional parent QWidget.
        """
        super().__init__(parent)

        self._abs_min = abs_min
        self._abs_max = abs_max
        self._steps = steps

        if self._abs_max <= self._abs_min:
            raise ValueError("abs_max must be greater than abs_min")

        self._initUI()

    def _initUI(self):
        """Initializes the UI layout and components."""
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(2, 2, 2, 2)
        self.mainLayout.setSpacing(5)

        self._setupLabels()
        self._setupSpinBoxes()
        self._setupSliderStack()

        self._setupAutoRangeButton()

        self.mainLayout.addWidget(self.lblAbsMax)
        self.mainLayout.addWidget(self.spinMax)
        self.mainLayout.addWidget(self.midContainer)
        self.mainLayout.addWidget(self.spinMin)
        self.mainLayout.addWidget(self.lblAbsMin)
        self.mainLayout.addWidget(self.btnAutoRange)

    def _setupLabels(self):
        """Initializes the absolute range labels."""
        self.lblAbsMax = QLabel(f"{self.tr('Max:')} {self._formatLabel(self._abs_max)}")
        self.lblAbsMax.setAlignment(Qt.AlignCenter)
        self.lblAbsMax.setProperty("class", "rangeAbsLabel")
        self.lblAbsMax.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.lblAbsMin = QLabel(f"{self.tr('Min:')} {self._formatLabel(self._abs_min)}")
        self.lblAbsMin.setAlignment(Qt.AlignCenter)
        self.lblAbsMin.setProperty("class", "rangeAbsLabel")
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
        self.slider.setStyleSheet(_SLIDER_STYLESHEET)
        self.slider.setMouseTracking(True)
        self.slider.installEventFilter(self)
        self.slider.valueChanged.connect(self._onSliderChanged)

        stackLayout.addWidget(self.slider)
        stackLayout.setCurrentWidget(self.slider)

    def _setupAutoRangeButton(self) -> None:
        """Creates the Auto Range button that resets to full data extent."""
        self.btnAutoRange = QPushButton(self.tr("\u27f3 Auto"))
        self.btnAutoRange.setToolTip(
            self.tr("Reset range to cover the full data extent")
        )
        self.btnAutoRange.setProperty("styleRole", "secondary")
        self.btnAutoRange.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btnAutoRange.clicked.connect(self.resetToFullRange)

    def resetToFullRange(self) -> None:
        """Resets the active range to cover the full data extent."""
        self.setValues(self._abs_min, self._abs_max)
        self.rangeChanged.emit(self._abs_min, self._abs_max)

    def eventFilter(self, obj, event):
        if obj == self.slider and event.type() == QEvent.MouseMove:
            height = self.slider.height()
            if height > 0:
                # ratio = 1.0 is top (max), 0.0 is bottom (min)
                ratio = 1.0 - (event.position().y() / height)
                ratio = max(0.0, min(1.0, ratio))
                val = self._abs_min + ratio * (self._abs_max - self._abs_min)
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    self._getTooltipText(val),
                    self.slider,
                )
        return super().eventFilter(obj, event)

    def _getTooltipText(self, value: float) -> str:
        """Generates styled HTML for the energy tooltip."""
        return f"<span style='{TooltipStyle.BODY}'>{self._formatLabel(value)}</span>"

    def setAbsoluteRange(self, abs_min: float, abs_max: float):
        """
        Sets the absolute limits of the control and updates the labels.

        :param abs_min: The new absolute minimum value.
        :param abs_max: The new absolute maximum value.
        """
        if abs_min >= abs_max:
            logger.warning(
                "setAbsoluteRange called with degenerate range (%s >= %s); ignoring",
                abs_min,
                abs_max,
            )
            return

        self._abs_min = abs_min
        self._abs_max = abs_max

        # Update Labels
        self.lblAbsMax.setText(f"{self.tr('Max:')} {self._formatLabel(abs_max)}")
        self.lblAbsMin.setText(f"{self.tr('Min:')} {self._formatLabel(abs_min)}")

        self.spinMin.setRange(abs_min, abs_max)
        self.spinMax.setRange(abs_min, abs_max)

        cur_min = max(self.spinMin.value(), abs_min)
        cur_max = min(self.spinMax.value(), abs_max)
        self.setValues(cur_min, cur_max)

    def _formatLabel(self, value: float) -> str:
        """Formats the value for display (compact, with units)."""
        if abs(value) >= 1000 or (abs(value) < 0.01 and value != 0):
            return f"{value:.1e} {self.tr('keV')}"
        return f"{value:.1f} {self.tr('keV')}"

    def setValues(self, vmin: float, vmax: float):
        """
        Sets the current active threshold range and updates the UI components.

        :param vmin: The active minimum threshold.
        :param vmax: The active maximum threshold.
        """
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

        self._updateGradientRatios()

        self.blockSignals(False)

    def setColormap(self, name: str):
        """
        Updates the colormap gradient legend.

        :param name: The name of the colormap to display (e.g., 'viridis').
        """
        self.gradient.setColormap(name)

    def _updateGradientRatios(self) -> None:
        """Recompute and apply gradient compression ratios."""
        span = self._abs_max - self._abs_min
        if span <= 0:
            return
        vmin_ratio = (self.spinMin.value() - self._abs_min) / span
        vmax_ratio = (self.spinMax.value() - self._abs_min) / span
        self.gradient.updateRatios(vmin_ratio, vmax_ratio)

    def _onSliderChanged(self, values: Tuple[int, int]):
        vmin = self._from_slider(values[0])
        vmax = self._from_slider(values[1])

        self.spinMin.blockSignals(True)
        self.spinMax.blockSignals(True)
        self.spinMin.setValue(vmin)
        self.spinMax.setValue(vmax)
        self.spinMin.blockSignals(False)
        self.spinMax.blockSignals(False)

        self._updateGradientRatios()
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

        self._updateGradientRatios()
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
