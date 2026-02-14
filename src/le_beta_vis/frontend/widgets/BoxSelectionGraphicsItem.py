from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)


class BoxSelectionGraphicsItem(QGraphicsItem):
    """
    A QGraphicsItem that draws a persistent rectangular selection
    (ROI) on the scene with a solid border and translucent fill.
    """

    def __init__(
        self, parent: Optional[QGraphicsItem] = None
    ) -> None:
        super().__init__(parent)
        self._rect: Optional[QRectF] = None
        self._color = QColor("#00BFFF")
        self._borderWidth: int = 2
        self.setZValue(50)

    def setRect(
        self, top: int, left: int, bottom: int, right: int
    ) -> None:
        """Sets the selection rectangle in scene coordinates."""
        self.prepareGeometryChange()
        self._rect = QRectF(left, top, right - left, bottom - top)
        self.setVisible(True)
        self.update()

    def setColor(self, color: str) -> None:
        """Sets the border/fill color from a CSS color string."""
        self._color = QColor(color)
        self.update()

    def setBorderWidth(self, width: int) -> None:
        """Sets the border pen width."""
        self._borderWidth = width
        self.update()

    def clear(self) -> None:
        """Hides the selection rectangle."""
        self.prepareGeometryChange()
        self._rect = None
        self.setVisible(False)
        self.update()

    _LABEL_HEIGHT = 18
    _LABEL_PADDING = 6
    _LABEL_GAP = 2

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle of the selection."""
        if self._rect is None:
            return QRectF()
        margin = self._borderWidth
        label_extra = self._LABEL_GAP + self._LABEL_HEIGHT
        return self._rect.adjusted(
            -margin, -margin, margin, margin + label_extra
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Draws a solid border with a translucent fill."""
        if self._rect is None:
            return

        pen = QPen(self._color, self._borderWidth)
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)

        fill = QColor(255, 255, 255, 26)  # white, ~0.1 alpha
        painter.setBrush(fill)

        painter.drawRect(self._rect)

        self._drawSizeLabel(painter)

    def _drawSizeLabel(self, painter: QPainter) -> None:
        """Draws a 'W x H' label below the selection rectangle."""
        w = int(self._rect.width())
        h = int(self._rect.height())
        if w <= 1 or h <= 1:
            return

        text = f"{w} x {h}"
        font = QFont("Arial", 9)
        font.setStyleHint(QFont.SansSerif)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text)
        pad = self._LABEL_PADDING
        bg_w = text_width + pad * 2
        bg_h = self._LABEL_HEIGHT

        cx = self._rect.center().x()
        label_x = cx - bg_w / 2
        label_y = self._rect.bottom() + self._LABEL_GAP

        bg_rect = QRectF(label_x, label_y, bg_w, bg_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 200))
        painter.drawRoundedRect(bg_rect, 3, 3)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(bg_rect, Qt.AlignCenter, text)
