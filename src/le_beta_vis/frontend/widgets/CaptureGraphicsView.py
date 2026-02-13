from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsView, QWidget


class CaptureGraphicsView(QGraphicsView):
    """
    A QGraphicsView subclass that emits pixel-hover coordinates,
    pixel-nudge requests, and magnification-change requests.
    Event interception is conditional on the magnifier tool state.
    """

    pixelHovered = Signal(int, int)
    pixelNudgeRequested = Signal(int, int)
    magnificationDeltaRequested = Signal(int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._magnifierActive: bool = False
        self.setFocusPolicy(Qt.StrongFocus)

    def setMagnifierActive(self, active: bool) -> None:
        """
        Enables or disables magnifier interaction mode.

        Args:
            active: True to enable magnifier mouse tracking.
        """
        self._magnifierActive = active
        self.setMouseTracking(active)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Emits pixelHovered when magnifier is active."""
        if self._magnifierActive:
            scene_pos = self.mapToScene(event.pos())
            self.pixelHovered.emit(
                int(scene_pos.y()), int(scene_pos.x())
            )
        super().mouseMoveEvent(event)

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
