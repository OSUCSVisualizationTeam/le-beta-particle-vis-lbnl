from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ..theme import ProgressOverlayColors as _C
from .ArcSpinner import ArcSpinner


class ProgressOverlay(QWidget):
    """Semi-transparent overlay with spinner, progress bar, and accessory slot.

    Covers its parent widget, dims the background, and prevents
    interaction with the content underneath.  Subclasses can add
    custom controls (e.g. a Cancel button) to the accessory slot
    returned by ``_accessoryLayout()``.

    Parameters
    ----------
    title:
        Text displayed in the overlay header.
    parent:
        Parent widget the overlay will cover.
    """

    def __init__(self, title: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)
        self._title = title
        self._initUI()
        self.hide()

    # --- UI Setup ---

    def _initUI(self) -> None:
        overlay_layout = QVBoxLayout(self)
        overlay_layout.setAlignment(Qt.AlignCenter)

        self._card = self._buildCard()
        overlay_layout.addWidget(self._card)

    def _buildCard(self) -> QWidget:
        """Builds the centered card containing all overlay content."""
        card = QWidget(self)
        card.setObjectName("progressOverlayCard")
        card.setMinimumSize(200, 140)

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self._headerLabel = self._buildHeaderLabel(card)
        layout.addWidget(self._headerLabel, 0, Qt.AlignHCenter)

        self._spinner = ArcSpinner(card)
        layout.addWidget(self._spinner, 0, Qt.AlignHCenter)

        self._progressBar = self._buildProgressBar(card)
        layout.addWidget(self._progressBar, 0, Qt.AlignHCenter)

        self._messageLabel = self._buildMessageLabel(card)
        layout.addWidget(self._messageLabel, 0, Qt.AlignHCenter)

        self._accessory = QVBoxLayout()
        layout.addLayout(self._accessory)

        return card

    def _buildHeaderLabel(self, parent: QWidget) -> QLabel:
        label = QLabel(self.tr(self._title), parent)
        label.setObjectName("progressOverlayHeaderLabel")
        label.setFixedHeight(24)
        label.setAlignment(Qt.AlignCenter)
        return label

    def _buildProgressBar(self, parent: QWidget) -> QProgressBar:
        bar = QProgressBar(parent)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedWidth(160)
        bar.setFixedHeight(20)
        bar.hide()
        return bar

    def _buildMessageLabel(self, parent: QWidget) -> QLabel:
        label = QLabel("", parent)
        label.setObjectName("progressOverlayMessageLabel")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.hide()
        return label

    # --- Public API ---

    def showOverlay(self) -> None:
        """Shows the overlay in indeterminate (spinner) mode."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        self._progressBar.hide()
        self._progressBar.setValue(0)
        self._messageLabel.hide()
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

    def setMessage(self, text: str) -> None:
        """Update the message label below the spinner.

        Args:
            text: Message to display.  Empty string hides the label.
        """
        if text:
            self._messageLabel.setText(text)
            self._messageLabel.show()
        else:
            self._messageLabel.hide()

    def _accessoryLayout(self) -> QVBoxLayout:
        """Returns the accessory slot layout for subclass controls."""
        return self._accessory

    # --- Geometry ---

    def resizeEvent(self, event) -> None:
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)

    # --- Painting ---

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(*_C.DIM_RGBA))
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
