import sys

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.widgets.CaptureGraphicsView import (
    CaptureGraphicsView,
)

app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def view():
    v = CaptureGraphicsView()
    v.resize(200, 200)
    return v


def test_default_magnifier_inactive(view):
    """Test magnifier starts inactive."""
    assert view._magnifierActive is False


def test_set_magnifier_active(view):
    """Test setMagnifierActive enables mouse tracking."""
    view.setMagnifierActive(True)
    assert view._magnifierActive is True
    assert view.hasMouseTracking() is True


def test_set_magnifier_inactive(view):
    """Test setMagnifierActive(False) disables mouse tracking."""
    view.setMagnifierActive(True)
    view.setMagnifierActive(False)
    assert view._magnifierActive is False
    assert view.hasMouseTracking() is False


def _send_key_and_capture_mag(view, key):
    """Helper: sends a key and returns magnificationDeltaRequested."""
    emitted = []
    view.magnificationDeltaRequested.connect(
        lambda d: emitted.append(d)
    )
    event = QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier)
    view.keyPressEvent(event)
    return emitted


def _send_key_and_capture_nudge(view, key):
    """Helper: sends a key and returns pixelNudgeRequested."""
    emitted = []
    view.pixelNudgeRequested.connect(
        lambda r, c: emitted.append((r, c))
    )
    event = QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier)
    view.keyPressEvent(event)
    return emitted


# --- Arrow keys emit nudge, not magnification ---

def test_arrow_up_emits_nudge(view):
    """Test Up arrow emits nudge (-1, 0) when magnifier is active."""
    view.setMagnifierActive(True)
    emitted = _send_key_and_capture_nudge(view, Qt.Key_Up)
    assert emitted == [(-1, 0)]


def test_arrow_down_emits_nudge(view):
    """Test Down arrow emits nudge (1, 0) when magnifier is active."""
    view.setMagnifierActive(True)
    emitted = _send_key_and_capture_nudge(view, Qt.Key_Down)
    assert emitted == [(1, 0)]


def test_arrow_left_emits_nudge(view):
    """Test Left arrow emits nudge (0, -1) when magnifier is active."""
    view.setMagnifierActive(True)
    emitted = _send_key_and_capture_nudge(view, Qt.Key_Left)
    assert emitted == [(0, -1)]


def test_arrow_right_emits_nudge(view):
    """Test Right arrow emits nudge (0, 1) when magnifier is active."""
    view.setMagnifierActive(True)
    emitted = _send_key_and_capture_nudge(view, Qt.Key_Right)
    assert emitted == [(0, 1)]


# --- +/- still emit magnification delta ---

def test_magnification_delta_on_key_plus(view):
    """Test + key emits +1 delta when magnifier is active."""
    view.setMagnifierActive(True)
    emitted = _send_key_and_capture_mag(view, Qt.Key_Plus)
    assert emitted == [1]


def test_magnification_delta_on_key_minus(view):
    """Test - key emits -1 delta when magnifier is active."""
    view.setMagnifierActive(True)
    emitted = _send_key_and_capture_mag(view, Qt.Key_Minus)
    assert emitted == [-1]


# --- No signals when inactive ---

def test_no_nudge_when_inactive(view):
    """Test arrow keys do not emit nudge when inactive."""
    emitted = _send_key_and_capture_nudge(view, Qt.Key_Up)
    assert emitted == []


def test_no_magnification_when_inactive(view):
    """Test +/- keys do not emit delta when inactive."""
    emitted = _send_key_and_capture_mag(view, Qt.Key_Plus)
    assert emitted == []


# --- Box select interaction model ---

def test_left_click_starts_pan_in_box_select(view):
    """Left click (no Shift) sets _panStart, not _boxSelectStart."""
    view.setBoxSelectActive(True)
    event = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPointF(100, 100),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    view.mousePressEvent(event)
    assert view._panStart is not None
    assert view._panOrigin is not None
    assert view._boxSelectStart is None


def test_shift_left_click_starts_box_select(view):
    """Shift+Left click sets _boxSelectStart, not _panStart."""
    view.setBoxSelectActive(True)
    event = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPointF(100, 100),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.ShiftModifier,
    )
    view.mousePressEvent(event)
    assert view._boxSelectStart is not None
    assert view._panStart is None


def test_box_select_default_cursor_is_arrow(view):
    """Default cursor in box select mode is ArrowCursor."""
    view.setBoxSelectActive(True)
    assert view.viewport().cursor().shape() == Qt.ArrowCursor


def test_left_click_no_action_when_inactive(view):
    """Left click does nothing when box select mode is off."""
    event = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPointF(100, 100),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    view.mousePressEvent(event)
    assert view._panStart is None
    assert view._boxSelectStart is None
