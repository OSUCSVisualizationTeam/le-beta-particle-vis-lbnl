from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)


class _HUDBoxSelectionItem(QGraphicsItem):
    """Widget-space rendering of the ROI selection rectangle + size label.

    Lives inside the HUD scene, so pens and fonts are expressed in
    screen pixels and remain constant regardless of the source-view
    zoom. The rectangle is set in widget coordinates by the HUD widget
    which re-projects the source-scene rect on every viewport change.
    """

    _LABEL_HEIGHT = 18
    _LABEL_PADDING = 6
    _LABEL_GAP = 2
    _LABEL_FONT_POINT_SIZE = 9

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self._widgetRect: Optional[QRectF] = None
        self._sizeText: str = ""
        self._color = QColor("#00BFFF")
        self._borderWidth: int = 2
        self.setZValue(50)
        self.setVisible(False)

    def setColor(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def setBorderWidth(self, width: int) -> None:
        self._borderWidth = max(1, int(width))
        self.update()

    def setWidgetRect(
        self,
        rect: Optional[QRectF],
        sizeText: str = "",
    ) -> None:
        """Sets the rectangle in HUD widget pixels and the label text."""
        self.prepareGeometryChange()
        self._widgetRect = QRectF(rect) if rect is not None else None
        self._sizeText = sizeText
        self.setVisible(self._widgetRect is not None)
        self.update()

    def boundingRect(self) -> QRectF:
        if self._widgetRect is None:
            return QRectF()
        margin = self._borderWidth
        labelExtra = self._LABEL_GAP + self._LABEL_HEIGHT
        return self._widgetRect.adjusted(
            -margin, -margin, margin, margin + labelExtra
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if self._widgetRect is None:
            return

        pen = QPen(self._color, self._borderWidth)
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 26))
        painter.drawRect(self._widgetRect)

        self._drawSizeLabel(painter)

    def _drawSizeLabel(self, painter: QPainter) -> None:
        if not self._sizeText or self._widgetRect is None:
            return
        if self._widgetRect.width() <= 1 or self._widgetRect.height() <= 1:
            return

        font = QFont("Arial", self._LABEL_FONT_POINT_SIZE)
        font.setStyleHint(QFont.SansSerif)
        painter.setFont(font)

        fm = painter.fontMetrics()
        textWidth = fm.horizontalAdvance(self._sizeText)
        pad = self._LABEL_PADDING
        bgW = textWidth + pad * 2
        bgH = self._LABEL_HEIGHT

        cx = self._widgetRect.center().x()
        labelX = cx - bgW / 2
        labelY = self._widgetRect.bottom() + self._LABEL_GAP

        bgRect = QRectF(labelX, labelY, bgW, bgH)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 200))
        painter.drawRoundedRect(bgRect, 3, 3)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(bgRect, Qt.AlignCenter, self._sizeText)
