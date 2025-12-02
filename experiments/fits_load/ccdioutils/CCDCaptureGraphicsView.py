from PySide6.QtWidgets import QGraphicsView, QWidget
from PySide6.QtCore import Signal, Qt  # Import Qt for Key enums
from PySide6.QtGui import QMouseEvent, QKeyEvent, QWheelEvent  # Import QWheelEvent


class CCDCaptureGraphicsView(QGraphicsView):
    """
    A specialized QGraphicsView for displaying CCD capture data and overlays.

    This subclass extends QGraphicsView to provide custom interaction behaviors
    essential for the CCD visualization application. It handles mouse tracking
    to emit pixel coordinates for display, and processes keyboard (Up/Down arrows)
    and mouse wheel events to control the magnification factor of a magnifier overlay.
    """

    # Signal to emit pixel coordinates (row, col)
    pixelHovered = Signal(int, int)
    magnificationFactorChanged = Signal(int)

    def __init__(self, parent: QWidget = None):
        """
        Initializes the CCDCaptureGraphicsView.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Overrides mouseMoveEvent to emit the pixel coordinates (row, col)
        under the mouse cursor via the `pixelHovered` signal.

        Args:
            event (QMouseEvent): The mouse move event.
        """
        scene_pos = self.mapToScene(event.pos())
        self.pixelHovered.emit(int(scene_pos.y()), int(scene_pos.x()))
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Overrides keyPressEvent to handle magnifier zoom controls.
        Emits `magnificationFactorChanged` signal with -1 for 'Down' arrow (zoom out)
        and +1 for 'Up' arrow (zoom in).

        Args:
            event (QKeyEvent): The key press event.
        """
        if event.key() == Qt.Key_Down:
            self.magnificationFactorChanged.emit(-1)
            event.accept()
        elif event.key() == Qt.Key_Up:
            self.magnificationFactorChanged.emit(1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """
        Overrides wheelEvent to handle zooming with the mouse scroll wheel.
        Normalizes the scroll delta and emits `magnificationFactorChanged` signal
        with +1 for scroll up (zoom in) and -1 for scroll down (zoom out).

        Args:
            event (QWheelEvent): The mouse wheel event.
        """
        normalized_delta = event.angleDelta().y() / 120

        if normalized_delta > 0:
            self.magnificationFactorChanged.emit(1)
        elif normalized_delta < 0:
            self.magnificationFactorChanged.emit(-1)
        event.accept()
