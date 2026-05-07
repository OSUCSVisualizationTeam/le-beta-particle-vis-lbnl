from typing import List, Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from le_beta_vis.frontend.theme import HUDAnnotationOverlayColors

_BORDER_COLOR = QColor(HUDAnnotationOverlayColors.BORDER)
_BORDER_WIDTH = 2


class _HUDAnnotationOverlaysItem(QGraphicsItem):
    """Widget-space rendering of zero or more annotation overlay rectangles.

    Rectangles are set in HUD widget pixels by HDUVisualizationHUDWidget,
    which reprojects AnnotationOverlay.bounding_box coords on every viewport
    change. Drawn with a yellow border and no fill.
    """

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self._widgetRects: List[QRectF] = []
        self.setZValue(60)
        self.setVisible(False)

    def setWidgetRects(self, rects: List[QRectF]) -> None:
        """Replace the displayed rectangles in HUD widget pixels."""
        self.prepareGeometryChange()
        self._widgetRects = [QRectF(r) for r in rects]
        self.setVisible(bool(self._widgetRects))
        self.update()

    def boundingRect(self) -> QRectF:
        if not self._widgetRects:
            return QRectF()
        result = QRectF(self._widgetRects[0])
        for r in self._widgetRects[1:]:
            result = result.united(r)
        m = _BORDER_WIDTH
        return result.adjusted(-m, -m, m, m)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if not self._widgetRects:
            return
        pen = QPen(_BORDER_COLOR, _BORDER_WIDTH)
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        for rect in self._widgetRects:
            painter.drawRect(rect)
