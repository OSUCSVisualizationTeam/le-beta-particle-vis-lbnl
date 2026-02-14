from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
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

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle of the selection."""
        if self._rect is None:
            return QRectF()
        margin = self._borderWidth
        return self._rect.adjusted(-margin, -margin, margin, margin)

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

        fill = QColor(self._color)
        fill.setAlpha(40)
        painter.setBrush(fill)

        painter.drawRect(self._rect)
