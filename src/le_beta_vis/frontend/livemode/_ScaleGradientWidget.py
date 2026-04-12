"""Vertical colormap gradient bar with an energy marker triangle.

Displays the active colormap as a vertical gradient strip.  A
left-pointing triangle marks the position of the featured cluster's
peak energy relative to the observed maximum.
"""

from typing import Optional

import numpy as np

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF
from PySide6.QtWidgets import QWidget

from le_beta_vis.frontend.fitsconverters.cluster_thumbnail import (
    generate_cluster_thumbnail,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.theme import LiveModeColors

_STRIP_WIDTH = 20
_TOTAL_WIDTH = 60
_MARKER_SIZE = 8
_LABEL_MARGIN = 4


class _ScaleGradientWidget(QWidget):
    """Vertical colormap gradient bar with an energy marker.

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
        self._colormap = colormap
        self._marker_ratio: float = 1.0
        self._vmin: float = 0.0
        self._vmax: float = 1.0
        self._unit: str = ""
        self._gradient_cache: Optional[QImage] = None
        self.setFixedWidth(_TOTAL_WIDTH)

    def setColormap(self, colormap: Colormap) -> None:
        """Update the displayed colormap."""
        self._colormap = colormap
        self._gradient_cache = None
        self.update()

    def setMarkerRatio(self, ratio: float) -> None:
        """Set the marker position as a 0.0–1.0 ratio.

        Args:
            ratio: cluster peak energy / observed max energy.
        """
        self._marker_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def setRange(self, vmin: float, vmax: float) -> None:
        """Set the displayed energy range for labels.

        Args:
            vmin: Minimum energy value.
            vmax: Maximum energy value.
        """
        self._vmin = vmin
        self._vmax = vmax
        self.update()

    def setUnit(self, unit: str) -> None:
        """Set the unit suffix for range labels (e.g. ``"keV"``).

        Args:
            unit: Unit string appended to min/max labels.
        """
        self._unit = unit
        self.update()

    def paintEvent(self, event) -> None:
        """Draw gradient strip, marker triangle, and range labels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._drawGradientStrip(painter)
        self._drawMarkerTriangle(painter)
        self._drawRangeLabels(painter)
        painter.end()

    def _drawGradientStrip(self, painter: QPainter) -> None:
        """Renders the colormap as a vertical QImage strip."""
        h = self.height()
        if h < 2:
            return
        if self._gradient_cache is None or self._gradient_cache.height() != h:
            self._gradient_cache = self._buildGradientImage(h)
        x = _TOTAL_WIDTH - _STRIP_WIDTH
        painter.drawImage(x, 0, self._gradient_cache)

    def _drawMarkerTriangle(self, painter: QPainter) -> None:
        """Draws a left-pointing triangle at the marker position."""
        h = self.height()
        y = int((1.0 - self._marker_ratio) * h)
        y = max(0, min(h - 1, y))
        x_tip = _TOTAL_WIDTH - _STRIP_WIDTH - 2
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

    def _drawRangeLabels(self, painter: QPainter) -> None:
        """Draws min/max range labels at bottom/top of strip."""
        painter.setPen(QColor(LiveModeColors.GRADIENT_LABEL))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)

        max_text = self._formatLabel(self._vmax)
        min_text = self._formatLabel(self._vmin)
        painter.drawText(0, _LABEL_MARGIN + 8, max_text)
        painter.drawText(0, self.height() - _LABEL_MARGIN, min_text)

    def _formatLabel(self, value: float) -> str:
        """Format a range label value with optional unit suffix."""
        if self._unit:
            return f"{value:.4f} {self._unit}"
        return f"{value:.0f}"

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
