from PySide6.QtWidgets import QGraphicsView, QWidget
from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent


class CCDCaptureGraphicsView(QGraphicsView):
    """
    A specialized QGraphicsView for displaying CCD capture data and overlays.

    This subclass provides a dedicated place for any future custom behavior,
    event handling, or specialized rendering logic specific to the CCD visualization.
    """

    # Signal to emit pixel coordinates (row, col)
    pixelHovered = Signal(int, int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Overrides mouseMoveEvent to emit pixel coordinates when the mouse moves.
        """
        scene_pos = self.mapToScene(event.pos())
        self.pixelHovered.emit(int(scene_pos.y()), int(scene_pos.x()))
        super().mouseMoveEvent(event)
