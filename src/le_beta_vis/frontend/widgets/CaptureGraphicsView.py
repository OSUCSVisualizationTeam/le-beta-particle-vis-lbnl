from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
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
        self._boxSelectActive: bool = False
        self._panStart: Optional[QPointF] = None
        self._panOrigin: Optional[QPointF] = None
        self._boxSelectStart: Optional[QPointF] = None
        self._boxSelectCurrent: Optional[QPointF] = None
        self._dragCursorOverridden: bool = False
        self.setFocusPolicy(Qt.StrongFocus)

    def setMagnifierActive(self, active: bool) -> None:
        """
        Enables or disables magnifier interaction mode.

        Args:
            active: True to enable magnifier mouse tracking.
        """
        self._magnifierActive = active
        self.setMouseTracking(active or self._boxSelectActive)

    def setBoxSelectActive(self, active: bool) -> None:
        """
        Enables or disables ROI / box selection interaction mode.
        Sets ArrowCursor as the idle cursor and resets drag state.
        Shift+left-click starts ROI selection; unmodified left-click
        pans the viewport.

        Args:
            active: True to enable ROI selection, hover inspect,
                    and left-click pan.
        """
        self._boxSelectActive = active
        self._boxSelectStart = None
        self._boxSelectCurrent = None
        if self._dragCursorOverridden:
            QGuiApplication.restoreOverrideCursor()
            self._dragCursorOverridden = False
        self._panStart = None
        self._panOrigin = None
        self.setMouseTracking(active or self._magnifierActive)
        if active:
            self.viewport().setCursor(Qt.ArrowCursor)
        else:
            self.viewport().unsetCursor()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Starts Shift+left ROI drag, left pan, or delegates to base."""
        if self._boxSelectActive and event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ShiftModifier:
                self._boxSelectStart = self.mapToScene(event.pos())
                self._boxSelectCurrent = self._boxSelectStart
                QGuiApplication.setOverrideCursor(Qt.SizeAllCursor)
                self._dragCursorOverridden = True
            else:
                self._panStart = event.position()
                self._panOrigin = event.position()
                QGuiApplication.setOverrideCursor(Qt.ClosedHandCursor)
                self._dragCursorOverridden = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handles ROI rubber-band, pan, hover inspect, or magnifier."""
        if self._boxSelectActive and self._boxSelectStart is not None:
            self._boxSelectCurrent = self.mapToScene(event.pos())
            self.viewport().update()
            event.accept()
            return
        if self._boxSelectActive and self._panStart is not None:
            delta = event.position() - self._panStart
            self._panStart = event.position()
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - int(delta.x()))
            vs.setValue(vs.value() - int(delta.y()))
            event.accept()
            return
        if self._magnifierActive:
            scene_pos = self.mapToScene(event.pos())
            self.pixelHovered.emit(
                int(scene_pos.y()), int(scene_pos.x())
            )
        elif self._boxSelectActive:
            scene_pos = self.mapToScene(event.pos())
            self.pixelHovered.emit(
                int(scene_pos.y()), int(scene_pos.x())
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Ends Shift+left ROI drag or left-click pan."""
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
                if self._dragCursorOverridden:
                    QGuiApplication.restoreOverrideCursor()
                    self._dragCursorOverridden = False
                if bottom > top and right > left:
                    self.boxSelectionCompleted.emit(
                        top, left, bottom, right
                    )
                else:
                    self.boxSelectClicked.emit(top, left)
            elif self._panStart is not None:
                origin = self._panOrigin
                end_pos = event.position()
                self._panStart = None
                self._panOrigin = None
                if self._dragCursorOverridden:
                    QGuiApplication.restoreOverrideCursor()
                    self._dragCursorOverridden = False
                if origin is not None:
                    dx = end_pos.x() - origin.x()
                    dy = end_pos.y() - origin.y()
                    if (dx * dx + dy * dy) < 9:
                        scene_pos = self.mapToScene(event.pos())
                        self.boxSelectClicked.emit(
                            int(scene_pos.y()), int(scene_pos.x())
                        )
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
        """Scroll wheel adjusts magnification or pans viewport."""
        if self._magnifierActive:
            normalized_delta = event.angleDelta().y() / 120
            if normalized_delta > 0:
                self.magnificationDeltaRequested.emit(1)
            elif normalized_delta < 0:
                self.magnificationDeltaRequested.emit(-1)
            event.accept()
            return
        if self._boxSelectActive:
            angle = event.angleDelta()
            if event.modifiers() & Qt.ShiftModifier:
                hs = self.horizontalScrollBar()
                hs.setValue(hs.value() - angle.y())
            else:
                vs = self.verticalScrollBar()
                vs.setValue(vs.value() - angle.y())
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
