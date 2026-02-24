from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ArcSpinner(QWidget):
    """A spinning arc indicator drawn as a semi-closed circle."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._angle: int = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(48, 48)

    def start(self) -> None:
        """Starts the spinning animation."""
        self._angle = 0
        self._timer.start(33)

    def stop(self) -> None:
        """Stops the spinning animation."""
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(4)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        margin = 6
        rect = QRectF(
            margin,
            margin,
            self.width() - 2 * margin,
            self.height() - 2 * margin,
        )

        # Draw a 270-degree arc that rotates
        start = self._angle * 16
        span = 270 * 16
        painter.drawArc(rect, start, span)
        painter.end()
