# Citation for Unit Tests: Verifies VerticalRangeControl widget behaviour
# including the degenerate-range guard added for issue #63.
# Date: 02/04/2026
# Adapted from Claude Code:
# Write a Qt UI test for VerticalRangeControl.setAbsoluteRange with
# degenerate ranges (abs_min >= abs_max) to confirm the guard added in
# issue #63 prevents broken widget state.
#
# NOTE: This file requires a display server (QApplication). It is excluded
# from headless CI via --ignore in python-package-conda.yml.

import sys
import pytest

from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.widgets.VerticalRangeControl import VerticalRangeControl


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def test_setAbsoluteRange_equal_min_max_is_ignored(app):
    """setAbsoluteRange with abs_min == abs_max must leave widget state unchanged."""
    ctrl = VerticalRangeControl(0.0, 100.0)
    ctrl.setAbsoluteRange(50.0, 50.0)

    assert ctrl._abs_min == 0.0
    assert ctrl._abs_max == 100.0


def test_setAbsoluteRange_inverted_range_is_ignored(app):
    """setAbsoluteRange with abs_min > abs_max must leave widget state unchanged."""
    ctrl = VerticalRangeControl(0.0, 100.0)
    ctrl.setAbsoluteRange(80.0, 20.0)

    assert ctrl._abs_min == 0.0
    assert ctrl._abs_max == 100.0


def test_setAbsoluteRange_valid_range_updates_state(app):
    """setAbsoluteRange with a valid range must update the widget state."""
    ctrl = VerticalRangeControl(0.0, 100.0)
    ctrl.setAbsoluteRange(10.0, 200.0)

    assert ctrl._abs_min == 10.0
    assert ctrl._abs_max == 200.0
