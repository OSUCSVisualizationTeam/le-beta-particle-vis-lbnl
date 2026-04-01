"""Composite header widget for sectioned event grid sections.

Displays a locale-formatted observation date on the first line
and an elided FITS filename on the second line.
"""

from typing import Optional

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.frontend.theme import (
    COLOR_BACKGROUND_SECTION_HEADER,
    COLOR_TEXT_SECTION_HEADER,
    COLOR_TEXT_SECTION_HEADER_FILENAME,
)

_DATE_STYLE = (
    f"color: {COLOR_TEXT_SECTION_HEADER};"
    " font-weight: bold; font-size: 12px;"
    " padding: 4px 8px 0px 8px;"
)

_FILE_STYLE = (
    f"color: {COLOR_TEXT_SECTION_HEADER_FILENAME};"
    " font-size: 10px;"
    " padding: 0px 8px 4px 8px;"
)


class SectionHeaderWidget(QWidget):
    """Two-line section header: locale date + elided filename.

    The widget sizes itself naturally from its label contents.
    Both labels have ``minimumWidth(0)`` so the header never forces
    its parent layout wider than the configured column constraints.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rawFileText: str = ""
        self._initUI()

    def _initUI(self) -> None:
        self.setStyleSheet(
            f"background-color: {COLOR_BACKGROUND_SECTION_HEADER};"
        )
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dateLabel = QLabel()
        self._dateLabel.setStyleSheet(_DATE_STYLE)
        self._dateLabel.setMinimumWidth(0)

        self._fileLabel = QLabel()
        self._fileLabel.setStyleSheet(_FILE_STYLE)
        self._fileLabel.setMinimumWidth(0)

        layout.addWidget(self._dateLabel)
        layout.addWidget(self._fileLabel)

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
        """Store and display the FITS filename, eliding if needed.

        Args:
            file_str: Basename of the FITS file.
        """
        self._rawFileText = file_str
        self._elideFileText()

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _elideFileText(self) -> None:
        """Re-compute the elided filename to fit the current width."""
        avail = self._fileLabel.width()
        if avail <= 0:
            avail = self.width()
        if avail <= 0:
            self._fileLabel.setText(self._rawFileText)
            return
        metrics = self._fileLabel.fontMetrics()
        elided = metrics.elidedText(
            self._rawFileText,
            Qt.TextElideMode.ElideRight,
            avail,
        )
        self._fileLabel.setText(elided)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Re-elide filename when the widget is resized."""
        super().resizeEvent(event)
        if self._rawFileText:
            self._elideFileText()
