import math
from typing import List, Optional, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)


class _HUDMagnifierBorderItem(QGraphicsItem):
    """Widget-space chrome for the magnifier.

    Draws the border of the magnified region, the translucent label
    panel (Min/Max/Val/Zoom), and any hint lines. All rendering uses
    constant screen-pixel dimensions so the overlay stays visually
    stable across zoom levels while the underlying magnified pixmap
    (rendered by :class:`MagnifierGraphicsItem`) scales with the view.
    """

    _LABEL_WIDTH = 120
    _LABEL_PADDING = 10
    _BORDER_WIDTH = 2
    _VALUE_FONT_POINT_SIZE = 8
    _HINT_FONT_POINT_SIZE = 7

    def __init__(
        self,
        parent: Optional[QGraphicsItem] = None,
        fontScale: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._widgetRect: Optional[QRectF] = None
        self._unit: str = ""
        self._magFactor: float = 1.0
        self._figures: Tuple[float, float, float] = (
            math.nan,
            math.nan,
            math.nan,
        )
        self._hintLines: List[str] = []
        self._fontScale = fontScale
        self.setZValue(100)
        self.setVisible(False)

    def _valueFont(self) -> QFont:
        return QFont("Arial", round(self._VALUE_FONT_POINT_SIZE * self._fontScale))

    def _hintFont(self) -> QFont:
        return QFont("Arial", round(self._HINT_FONT_POINT_SIZE * self._fontScale))

    def _scaledLabelWidth(self) -> float:
        return self._LABEL_WIDTH * self._fontScale

    def setState(
        self,
        widgetRect: Optional[QRectF],
        unit: str,
        magFactor: float,
        figures: Tuple[float, float, float],
        hintLines: List[str],
    ) -> None:
        """Update the HUD border geometry and label data."""
        self.prepareGeometryChange()
        self._widgetRect = QRectF(widgetRect) if widgetRect is not None else None
        self._unit = unit
        self._magFactor = magFactor
        self._figures = figures
        self._hintLines = list(hintLines)
        self.setVisible(self._widgetRect is not None)
        self.update()

    def boundingRect(self) -> QRectF:
        if self._widgetRect is None:
            return QRectF()
        lineHeight = QFontMetrics(self._valueFont()).height() + 2
        extraLines = 4 + (len(self._hintLines) + 1 if self._hintLines else 0)
        labelWidth = self._LABEL_PADDING + self._scaledLabelWidth() + 8
        labelHeight = extraLines * lineHeight + 8
        right = self._widgetRect.right() + labelWidth
        bottom = max(self._widgetRect.bottom(), self._widgetRect.top() + labelHeight)
        margin = self._BORDER_WIDTH + 1
        return QRectF(
            self._widgetRect.left() - margin,
            self._widgetRect.top() - margin,
            right - self._widgetRect.left() + margin * 2,
            bottom - self._widgetRect.top() + margin * 2,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if self._widgetRect is None:
            return

        pen = QPen(QColor("blue"), self._BORDER_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self._widgetRect)

        self._drawLabels(painter)
        self._drawHints(painter)

    def _drawLabels(self, painter: QPainter) -> None:
        assert self._widgetRect is not None
        painter.setFont(self._valueFont())
        metrics = painter.fontMetrics()
        lineHeight = metrics.height() + 2

        hintCount = len(self._hintLines)
        totalLines = 4 + (hintCount + 1 if hintCount else 0)
        bgHeight = totalLines * lineHeight + 4

        labelX = self._widgetRect.right() + self._LABEL_PADDING
        labelY = self._widgetRect.top()
        bgRect = QRectF(
            labelX - 4, labelY, self._scaledLabelWidth() + 4, bgHeight
        )
        painter.fillRect(bgRect, QColor(0, 0, 0, int(255 * 0.8)))

        minVal, maxVal, centralVal = self._figures
        unit = self._unit
        painter.setPen(QPen(QColor("white")))
        painter.drawText(
            int(labelX), int(labelY + lineHeight),
            f"Min: {minVal:.2e} {unit}",
        )
        painter.drawText(
            int(labelX), int(labelY + 2 * lineHeight),
            f"Max: {maxVal:.2e} {unit}",
        )
        painter.drawText(
            int(labelX), int(labelY + 3 * lineHeight),
            f"Val: {centralVal:.2e} {unit}",
        )
        painter.drawText(
            int(labelX), int(labelY + 4 * lineHeight),
            f"Zoom: {self._magFactor:.1f}x",
        )

    def _drawHints(self, painter: QPainter) -> None:
        if not self._hintLines or self._widgetRect is None:
            return
        painter.setFont(self._hintFont())
        metrics = painter.fontMetrics()
        lineHeight = metrics.height() + 2
        labelX = self._widgetRect.right() + self._LABEL_PADDING
        startY = self._widgetRect.top() + 5 * lineHeight
        painter.setPen(QPen(QColor("#aaaaaa")))
        for i, line in enumerate(self._hintLines):
            painter.drawText(
                int(labelX),
                int(startY + (i + 1) * lineHeight),
                line,
            )
