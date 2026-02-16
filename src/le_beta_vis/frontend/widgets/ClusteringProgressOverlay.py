from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _ArcSpinner(QWidget):
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


class ClusteringProgressOverlay(QWidget):
    """Semi-transparent overlay with a spinning indicator and cancel button.

    Covers its parent widget, dims the background, and prevents
    interaction with the content underneath.
    """

    cancelRequested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)
        self._initUI()
        self.hide()

    def _initUI(self) -> None:
        # Full-overlay layout centres a card widget
        overlay_layout = QVBoxLayout(self)
        overlay_layout.setAlignment(Qt.AlignCenter)

        # Card container
        self._card = QWidget(self)
        self._card.setFixedSize(200, 160)
        self._card.setStyleSheet(
            "background-color: rgba(255, 255, 255, 64);" " border-radius: 12px;"
        )

        card_layout = QVBoxLayout(self._card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(12)

        # Header label
        self._headerLabel = QLabel(self.tr("Clustering"), self._card)
        self._headerLabel.setFixedHeight(24)
        self._headerLabel.setStyleSheet(
            "background: transparent; color: #000000;" " font-size: 16px;"
        )
        self._headerLabel.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._headerLabel, 0, Qt.AlignHCenter)

        # Spinner
        self._spinner = _ArcSpinner(self._card)
        card_layout.addWidget(self._spinner, 0, Qt.AlignHCenter)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        self._cancelBtn = QPushButton(self.tr("Cancel"))
        self._cancelBtn.setFixedWidth(80)
        self._cancelBtn.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180);"
            " color: #ffffff; border-radius: 4px;"
            " padding: 4px 8px;"
        )
        self._cancelBtn.clicked.connect(self.cancelRequested.emit)
        btn_row.addWidget(self._cancelBtn)
        card_layout.addLayout(btn_row)

        overlay_layout.addWidget(self._card)

    # --- Lifecycle ---

    def showOverlay(self) -> None:
        """Shows the overlay and starts the spinner."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        self._spinner.start()
        self.show()
        self.raise_()

    def hideOverlay(self) -> None:
        """Hides the overlay and stops the spinner."""
        self._spinner.stop()
        self.hide()

    def resizeEvent(self, event) -> None:
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)

    # --- Painting ---

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        painter.end()

    # --- Event interception ---

    def mousePressEvent(self, event) -> None:
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        event.accept()

    def keyPressEvent(self, event) -> None:
        event.accept()
