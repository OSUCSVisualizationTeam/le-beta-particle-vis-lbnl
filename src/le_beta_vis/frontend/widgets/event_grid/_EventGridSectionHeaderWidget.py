"""Composite header widget for EventGrid sections.

Three-column layout: previous-section button, center content
(locale-formatted date + word-wrapped filename), and
next-section button.
"""

from typing import Optional

from PySide6.QtCore import QDate, QLocale, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.frontend.theme import EventGridSectionHeaderColors as _C

_NAV_BTN_SIZE = 28

_DATE_STYLE = (
    f"color: {_C.TEXT};"
    " font-weight: bold; font-size: 12px;"
    " padding: 4px 8px 0px 8px;"
)

_FILE_STYLE = (
    f"color: {_C.TEXT_FILENAME};"
    " font-size: 10px;"
    " padding: 0px 8px 4px 8px;"
)

_NAV_BTN_STYLE = (
    "QToolButton {{"
    f"  color: {_C.NAV_TEXT};"
    "  font-size: 12px;"
    "  border: none;"
    f"  background: {_C.BACKGROUND};"
    "}}"
    "QToolButton:hover {{"
    f"  background: {_C.NAV_HOVER_BACKGROUND};"
    "}}"
    "QToolButton:disabled {{"
    f"  color: {_C.NAV_TEXT_DISABLED};"
    "}}"
)


class EventGridSectionHeaderWidget(QWidget):
    """Three-column section header with navigation buttons.

    Layout: ``[▲ prev] [date + filename] [▼ next]``

    The center area displays a locale-formatted date and a
    word-wrapped filename (up to two lines).  The nav buttons
    scroll to adjacent sections.  Clicking the center text
    scrolls the current section to the top of the viewport.
    """

    navigatePrevious = Signal()
    navigateNext = Signal()
    navigateToSelf = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._initUI()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _initUI(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"background-color: {_C.BACKGROUND};"
        )
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._prevBtn = self._buildNavButton("\u25b2")
        self._prevBtn.clicked.connect(self.navigatePrevious)

        self._nextBtn = self._buildNavButton("\u25bc")
        self._nextBtn.clicked.connect(self.navigateNext)

        center = self._buildCenterWidget()

        root.addWidget(self._prevBtn)
        root.addWidget(center, 1)
        root.addWidget(self._nextBtn)

    def _buildNavButton(self, symbol: str) -> QToolButton:
        """Create a fixed-size, flat navigation button."""
        btn = QToolButton()
        btn.setText(symbol)
        btn.setAutoRaise(True)
        btn.setFixedSize(_NAV_BTN_SIZE, _NAV_BTN_SIZE)
        btn.setStyleSheet(_NAV_BTN_STYLE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _buildCenterWidget(self) -> QWidget:
        """Create the center area with date and filename labels."""
        center = QWidget()
        center.setMinimumWidth(0)
        center.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dateLabel = QLabel()
        self._dateLabel.setStyleSheet(_DATE_STYLE)
        self._dateLabel.setMinimumWidth(0)

        self._fileLabel = QLabel()
        self._fileLabel.setStyleSheet(_FILE_STYLE)
        self._fileLabel.setMinimumWidth(0)
        self._fileLabel.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred,
        )
        self._fileLabel.setWordWrap(True)
        self._applyFileLabelMaxHeight()

        layout.addWidget(self._dateLabel)
        layout.addWidget(self._fileLabel)
        return center

    def _applyFileLabelMaxHeight(self) -> None:
        """Cap the filename label at two lines of text.

        Accounts for the 4px bottom padding from the stylesheet.
        """
        line_h = self._fileLabel.fontMetrics().lineSpacing()
        padding_bottom = 4
        self._fileLabel.setMaximumHeight(line_h * 2 + padding_bottom)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def setDateText(self, date_str: str) -> None:
        """Format and display the observation date.

        Parses *date_str* as ``YYYY-MM-DD`` and renders it using
        the current locale's short date format.  Falls back to the
        raw string when parsing fails.

        Args:
            date_str: ISO date string or fallback text.
        """
        qdate = QDate.fromString(date_str, "yyyy-MM-dd")
        if qdate.isValid():
            locale = QLocale()
            text = locale.toString(qdate, QLocale.FormatType.ShortFormat)
        else:
            text = date_str
        self._dateLabel.setText(text)

    def setFileText(self, file_str: str) -> None:
        """Display the FITS filename with word wrap (max 2 lines).

        Inserts zero-width spaces after common filename separators
        (``_``, ``-``, ``.``) so Qt's word-wrap engine can break
        long filenames that contain no whitespace.

        Args:
            file_str: Basename of the FITS file.
        """
        zwsp = "\u200b"
        breakable = file_str.replace("_", f"_{zwsp}")
        breakable = breakable.replace("-", f"-{zwsp}")
        breakable = breakable.replace(".", f".{zwsp}")
        self._fileLabel.setText(breakable)

    def setNavigationState(
        self, has_previous: bool, has_next: bool,
    ) -> None:
        """Enable or disable the navigation buttons.

        Args:
            has_previous: Whether a previous section exists.
            has_next: Whether a next section exists.
        """
        self._prevBtn.setEnabled(has_previous)
        self._nextBtn.setEnabled(has_next)

    # ------------------------------------------------------------------ #
    # Center-click → navigateToSelf                                        #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit navigateToSelf when clicking the center text area."""
        pos = event.pos()
        if (
            not self._prevBtn.geometry().contains(pos)
            and not self._nextBtn.geometry().contains(pos)
        ):
            self.navigateToSelf.emit()
        super().mousePressEvent(event)
