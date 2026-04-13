"""Vertical colormap gradient bar with an energy marker triangle.

Displays the active colormap as a vertical gradient strip between
max/min energy labels.  A left-pointing triangle marks the position
of the featured cluster's peak energy relative to the observed maximum.
"""

from typing import Optional

import numpy as np

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from le_beta_vis.frontend.fitsconverters.cluster_thumbnail import (
    generate_cluster_thumbnail,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.theme import LiveModeColors

_STRIP_WIDTH = 20
_TOTAL_WIDTH = 60
_MARKER_SIZE = 8


class _GradientStripWidget(QWidget):
    """Inner widget that paints the gradient strip and marker triangle.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._colormap: Optional[Colormap] = None
        self._marker_ratio: float = 1.0
        self._gradient_cache: Optional[QImage] = None
        self.setFixedWidth(_STRIP_WIDTH + _MARKER_SIZE + 2)

    def setColormap(self, colormap: Colormap) -> None:
        """Update the displayed colormap."""
        self._colormap = colormap
        self._gradient_cache = None
        self.update()

    def setMarkerRatio(self, ratio: float) -> None:
        """Set the marker position as a 0.0-1.0 ratio."""
        self._marker_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event) -> None:
        """Draw gradient strip and marker triangle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._drawGradientStrip(painter)
        self._drawMarkerTriangle(painter)
        painter.end()

    def _drawGradientStrip(self, painter: QPainter) -> None:
        """Renders the colormap as a vertical QImage strip."""
        h = self.height()
        if h < 2:
            return
        if self._gradient_cache is None or self._gradient_cache.height() != h:
            self._gradient_cache = self._buildGradientImage(h)
        x = _MARKER_SIZE + 2
        painter.drawImage(x, 0, self._gradient_cache)

    def _drawMarkerTriangle(self, painter: QPainter) -> None:
        """Draws a left-pointing triangle at the marker position."""
        h = self.height()
        y = int((1.0 - self._marker_ratio) * h)
        y = max(0, min(h - 1, y))
        x_tip = _MARKER_SIZE
        triangle = QPolygonF(
            [
                QPointF(x_tip, y),
                QPointF(x_tip - _MARKER_SIZE, y - _MARKER_SIZE // 2),
                QPointF(x_tip - _MARKER_SIZE, y + _MARKER_SIZE // 2),
            ]
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(LiveModeColors.GRADIENT_MARKER))
        painter.drawPolygon(triangle)

    def _buildGradientImage(self, height: int) -> QImage:
        """Creates a vertical gradient QImage from the colormap."""
        ramp = np.linspace(1.0, 0.0, height).reshape(height, 1)
        ramp = ramp.astype(np.float64)
        buf = generate_cluster_thumbnail(
            ramp,
            colormap=self._colormap,
            pad_to_square=False,
        )
        if buf.ndim == 3:
            strip = buf[:, :1, :]
            strip = np.broadcast_to(strip, (height, _STRIP_WIDTH, 3))
            strip = np.ascontiguousarray(strip)
            return QImage(
                strip.data,
                _STRIP_WIDTH,
                height,
                _STRIP_WIDTH * 3,
                QImage.Format_RGB888,
            ).copy()
        else:
            strip = buf[:, :1]
            strip = np.broadcast_to(strip, (height, _STRIP_WIDTH))
            strip = np.ascontiguousarray(strip)
            return QImage(
                strip.data,
                _STRIP_WIDTH,
                height,
                _STRIP_WIDTH,
                QImage.Format_Grayscale8,
            ).copy()


class _ScaleGradientWidget(QWidget):
    """Vertical colormap gradient bar with labeled energy range.

    Lays out a max-value QLabel above a gradient strip widget and a
    min-value QLabel below, eliminating text-over-gradient overlap.

    Args:
        colormap: Initial colormap to display.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        colormap: Colormap,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vmin: float = 0.0
        self._vmax: float = 1.0
        self._unit: str = ""
        self._buildLayout(colormap)
        self.setFixedWidth(_TOTAL_WIDTH)

    def _buildLayout(self, colormap: Colormap) -> None:
        """Construct the vertical label / strip / label layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_style = (
            f"color: {LiveModeColors.GRADIENT_LABEL}; font-size: 7pt;"
        )

        self._maxLabel = QLabel()
        self._maxLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._maxLabel.setStyleSheet(label_style)
        layout.addWidget(self._maxLabel)

        self._strip = _GradientStripWidget()
        self._strip.setColormap(colormap)
        layout.addWidget(self._strip, stretch=1)

        self._minLabel = QLabel()
        self._minLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._minLabel.setStyleSheet(label_style)
        layout.addWidget(self._minLabel)

    def setColormap(self, colormap: Colormap) -> None:
        """Update the displayed colormap."""
        self._strip.setColormap(colormap)

    def setMarkerRatio(self, ratio: float) -> None:
        """Set the marker position as a 0.0-1.0 ratio.

        Args:
            ratio: cluster peak energy / observed max energy.
        """
        self._strip.setMarkerRatio(ratio)

    def setRange(self, vmin: float, vmax: float) -> None:
        """Set the displayed energy range and update labels.

        Args:
            vmin: Minimum energy value.
            vmax: Maximum energy value.
        """
        self._vmin = vmin
        self._vmax = vmax
        self._maxLabel.setText(self._formatLabel(vmax))
        self._minLabel.setText(self._formatLabel(vmin))

    def setUnit(self, unit: str) -> None:
        """Set the unit suffix for range labels (e.g. ``"keV"``).

        Args:
            unit: Unit string appended to min/max labels.
        """
        self._unit = unit
        self._maxLabel.setText(self._formatLabel(self._vmax))
        self._minLabel.setText(self._formatLabel(self._vmin))

    def _formatLabel(self, value: float) -> str:
        """Format a range label value with optional unit suffix."""
        if self._unit:
            return f"{value:.4f} {self._unit}"
        return f"{value:.0f}"
