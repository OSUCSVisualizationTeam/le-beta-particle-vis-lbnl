import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
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
