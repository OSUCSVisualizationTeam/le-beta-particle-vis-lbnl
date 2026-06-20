"""Tests for EventGridSectionHeaderWidget formatting, size, and navigation.

These tests require a QApplication instance and are excluded from
headless CI via ``--ignore`` in the GitHub Actions workflow.
Run locally with: ``uv run pytest tests/test_SectionHeaderFormatting.py -v``
"""

from le_beta_vis.frontend.widgets.event_grid._EventGridSectionHeaderWidget import (
    EventGridSectionHeaderWidget,
)
import sys

from PySide6.QtCore import QDate, QLocale
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)


class TestSetDateText:
    """Locale-aware date formatting via setDateText."""

    def test_valid_iso_date_is_reformatted(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setDateText("2022-10-08")
        label_text = widget._dateLabel.text()
        assert label_text != "2022-10-08"
        expected = QLocale().toString(
            QDate(2022, 10, 8), QLocale.FormatType.ShortFormat,
        )
        assert label_text == expected

    def test_invalid_date_falls_back_to_raw(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setDateText("bad-input")
        assert widget._dateLabel.text() == "bad-input"

    def test_empty_date_falls_back_to_empty(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setDateText("")
        assert widget._dateLabel.text() == ""


class TestSetFileText:
    """Filename display via setFileText (word-wrap, no elision)."""

    def test_file_text_set_on_label(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setFileText("exposure_data.fits")
        # setFileText inserts zero-width spaces after _ and . for word-wrap
        assert widget._fileLabel.text() == "exposure_\u200bdata.\u200bfits"

    def test_word_wrap_enabled(self) -> None:
        widget = EventGridSectionHeaderWidget()
        assert widget._fileLabel.wordWrap() is True

    def test_file_label_has_max_height(self) -> None:
        widget = EventGridSectionHeaderWidget()
        assert widget._fileLabel.maximumHeight() > 0


class TestSizePolicy:
    """Widget must never force its parent layout wider."""

    def test_minimum_width_is_zero(self) -> None:
        widget = EventGridSectionHeaderWidget()
        assert widget.minimumWidth() == 0

    def test_date_label_minimum_width_is_zero(self) -> None:
        widget = EventGridSectionHeaderWidget()
        assert widget._dateLabel.minimumWidth() == 0

    def test_file_label_minimum_width_is_zero(self) -> None:
        widget = EventGridSectionHeaderWidget()
        assert widget._fileLabel.minimumWidth() == 0


class TestNavigationState:
    """Navigation button enable/disable via setNavigationState."""

    def test_both_disabled(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(False, False)
        assert not widget._prevBtn.isEnabled()
        assert not widget._nextBtn.isEnabled()

    def test_both_enabled(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(True, True)
        assert widget._prevBtn.isEnabled()
        assert widget._nextBtn.isEnabled()

    def test_only_previous(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(True, False)
        assert widget._prevBtn.isEnabled()
        assert not widget._nextBtn.isEnabled()

    def test_only_next(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(False, True)
        assert not widget._prevBtn.isEnabled()
        assert widget._nextBtn.isEnabled()


class TestNavigationSignals:
    """Navigation buttons emit the correct signals."""

    def test_prev_button_emits_navigate_previous(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(True, True)
        received: list = []
        widget.navigatePrevious.connect(lambda: received.append("prev"))
        widget._prevBtn.click()
        assert received == ["prev"]

    def test_next_button_emits_navigate_next(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(True, True)
        received: list = []
        widget.navigateNext.connect(lambda: received.append("next"))
        widget._nextBtn.click()
        assert received == ["next"]

    def test_disabled_button_does_not_emit(self) -> None:
        widget = EventGridSectionHeaderWidget()
        widget.setNavigationState(False, False)
        received: list = []
        widget.navigatePrevious.connect(lambda: received.append("prev"))
        widget.navigateNext.connect(lambda: received.append("next"))
        widget._prevBtn.click()
        widget._nextBtn.click()
        assert received == []
