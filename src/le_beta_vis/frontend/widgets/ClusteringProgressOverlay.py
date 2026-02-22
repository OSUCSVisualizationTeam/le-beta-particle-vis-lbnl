from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .ArcSpinner import ArcSpinner


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
            "background-color: rgba(255, 255, 255, 64);"
            " border-radius: 12px;"
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

        # Spinner (indeterminate mode)
        self._spinner = ArcSpinner(self._card)
        card_layout.addWidget(self._spinner, 0, Qt.AlignHCenter)

        # Progress bar (determinate mode, hidden by default)
        self._progressBar = QProgressBar(self._card)
        self._progressBar.setRange(0, 100)
        self._progressBar.setValue(0)
        self._progressBar.setFixedWidth(160)
        self._progressBar.setFixedHeight(20)
        self._progressBar.setStyleSheet(
            "QProgressBar { background: rgba(0, 0, 0, 40);"
            " border-radius: 4px; text-align: center;"
            " color: #000000; }"
            " QProgressBar::chunk { background: #3daee9;"
            " border-radius: 4px; }"
        )
        self._progressBar.hide()
        card_layout.addWidget(self._progressBar, 0, Qt.AlignHCenter)

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
        """Shows the overlay in indeterminate (spinner) mode."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        self._progressBar.hide()
        self._progressBar.setValue(0)
        self._spinner.show()
        self._spinner.start()
        self.show()
        self.raise_()

    def hideOverlay(self) -> None:
        """Hides the overlay and stops the spinner."""
        self._spinner.stop()
        self.hide()

    def setProgress(self, value: float) -> None:
        """Switch to determinate mode and update the progress bar.

        Args:
            value: Progress fraction in [0.0, 1.0].
        """
        if self._spinner.isVisible():
            self._spinner.stop()
            self._spinner.hide()
            self._progressBar.show()
        self._progressBar.setValue(int(value * 100))

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
