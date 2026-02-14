from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QWidget


class CaptureGraphicsView(QGraphicsView):
    """
    A QGraphicsView subclass that emits pixel-hover coordinates,
    pixel-nudge requests, and magnification-change requests.
    Event interception is conditional on the active tool state.
    """

    pixelHovered = Signal(int, int)
    pixelNudgeRequested = Signal(int, int)
    magnificationDeltaRequested = Signal(int)
    mouseLeft = Signal()
    boxSelectionCompleted = Signal(int, int, int, int)
    boxSelectClicked = Signal(int, int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._magnifierActive: bool = False
        self._pointerActive: bool = False
        self._boxSelectActive: bool = False
        self._panStart: Optional[QPointF] = None
        self._boxSelectStart: Optional[QPointF] = None
        self._boxSelectCurrent: Optional[QPointF] = None
        self.setFocusPolicy(Qt.StrongFocus)

    def setMagnifierActive(self, active: bool) -> None:
        """
        Enables or disables magnifier interaction mode.

        Args:
            active: True to enable magnifier mouse tracking.
        """
        self._magnifierActive = active
        self.setMouseTracking(active or self._pointerActive)

    def setPointerActive(self, active: bool) -> None:
        """
        Enables or disables pointer interaction mode.
        Uses CrossCursor for precision pixel inspection and
        manual panning with ClosedHand cursor on drag.

        Args:
            active: True to enable pointer pan and inspect.
        """
        self._pointerActive = active
        self._panStart = None
        self.setMouseTracking(active or self._magnifierActive)
        if active:
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.viewport().unsetCursor()

    def setBoxSelectActive(self, active: bool) -> None:
        """
        Enables or disables box selection interaction mode.
        Sets CrossCursor and resets any in-progress drag state.

        Args:
            active: True to enable box selection drawing.
        """
        self._boxSelectActive = active
        self._boxSelectStart = None
        self._boxSelectCurrent = None
        if active:
            self.viewport().setCursor(Qt.CrossCursor)
        elif not self._pointerActive:
            self.viewport().unsetCursor()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Starts box selection drag or manual pan on left-click."""
        if self._boxSelectActive and event.button() == Qt.LeftButton:
            self._boxSelectStart = self.mapToScene(event.pos())
            self._boxSelectCurrent = self._boxSelectStart
            event.accept()
            return
        if self._pointerActive and event.button() == Qt.LeftButton:
            self._panStart = event.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Emits pixelHovered, handles panning, or rubber-band drag."""
        if self._boxSelectActive and self._boxSelectStart is not None:
            self._boxSelectCurrent = self.mapToScene(event.pos())
            self.viewport().update()
            event.accept()
            return
        if self._magnifierActive:
            scene_pos = self.mapToScene(event.pos())
            self.pixelHovered.emit(
                int(scene_pos.y()), int(scene_pos.x())
            )
        elif self._pointerActive:
            if self._panStart is not None:
                delta = event.position() - self._panStart
                self._panStart = event.position()
                hs = self.horizontalScrollBar()
                vs = self.verticalScrollBar()
                hs.setValue(hs.value() - int(delta.x()))
                vs.setValue(vs.value() - int(delta.y()))
                event.accept()
                return
            else:
                scene_pos = self.mapToScene(event.pos())
                self.pixelHovered.emit(
                    int(scene_pos.y()), int(scene_pos.x())
                )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Ends box selection drag or manual pan."""
        if self._boxSelectActive and event.button() == Qt.LeftButton:
            if self._boxSelectStart is not None:
                end = self.mapToScene(event.pos())
                start = self._boxSelectStart
                top = int(min(start.y(), end.y()))
                left = int(min(start.x(), end.x()))
                bottom = int(max(start.y(), end.y()))
                right = int(max(start.x(), end.x()))
                self._boxSelectStart = None
                self._boxSelectCurrent = None
                self.viewport().update()
                if bottom > top and right > left:
                    self.boxSelectionCompleted.emit(
                        top, left, bottom, right
                    )
                else:
                    self.boxSelectClicked.emit(top, left)
            event.accept()
            return
        if self._pointerActive and event.button() == Qt.LeftButton:
            self._panStart = None
            self.viewport().setCursor(Qt.CrossCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Emits mouseLeft when the cursor exits the view."""
        self.mouseLeft.emit()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Arrow keys nudge position; +/- adjust magnification."""
        if self._magnifierActive:
            nudge = self._arrowToNudge(event.key())
            if nudge is not None:
                self.pixelNudgeRequested.emit(*nudge)
                event.accept()
                return
            if event.key() == Qt.Key_Plus:
                self.magnificationDeltaRequested.emit(1)
                event.accept()
                return
            elif event.key() == Qt.Key_Minus:
                self.magnificationDeltaRequested.emit(-1)
                event.accept()
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll wheel adjusts magnification when active."""
        if self._magnifierActive:
            normalized_delta = event.angleDelta().y() / 120
            if normalized_delta > 0:
                self.magnificationDeltaRequested.emit(1)
            elif normalized_delta < 0:
                self.magnificationDeltaRequested.emit(-1)
            event.accept()
            return
        super().wheelEvent(event)

    def drawForeground(
        self, painter: QPainter, rect: QRectF
    ) -> None:
        """Draws a dashed rubber-band rectangle during box select drag."""
        super().drawForeground(painter, rect)
        if (
            self._boxSelectActive
            and self._boxSelectStart is not None
            and self._boxSelectCurrent is not None
        ):
            r = QRectF(
                self._boxSelectStart, self._boxSelectCurrent
            ).normalized()
            pen = QPen(QColor("#00BFFF"), 1.5)
            pen.setStyle(Qt.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            fill = QColor(255, 255, 255, 26)  # white, ~0.1 alpha
            painter.setBrush(fill)
            painter.drawRect(r)

    @staticmethod
    def _arrowToNudge(key: int):
        """Maps arrow keys to (row_delta, col_delta) or None."""
        mapping = {
            Qt.Key_Up: (-1, 0),
            Qt.Key_Down: (1, 0),
            Qt.Key_Left: (0, -1),
            Qt.Key_Right: (0, 1),
        }
        return mapping.get(key)
