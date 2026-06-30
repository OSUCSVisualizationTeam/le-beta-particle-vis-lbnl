# Verifies _DragHandle survives the C++ object being deleted mid-drag,
# reproducing the macOS crash recorded in issue #203.
#
# NOTE: This file requires a display server (QApplication). It is excluded
# from headless CI via --ignore in python-package-conda.yml.

import sys

import pytest
import shiboken6
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.views.raw_data_view.filter_pipeline_panel._FilterStackEntryView import (
    _DragHandle,
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def test_begin_drag_survives_handle_deleted_during_exec(app, monkeypatch):
    """_beginDrag must not raise when the drop handler rebuilds the filter
    stack and deletes the source handle's C++ object before exec() returns.
    """
    handle = _DragHandle("entry-1")

    def fake_exec(self, action):
        # QDrag.exec() blocks until drop; here a drop has just rebuilt the
        # filter stack, tearing down the source card (and this handle).
        shiboken6.delete(handle)
        return action

    monkeypatch.setattr(QDrag, "exec", fake_exec)

    handle._beginDrag()

    assert not shiboken6.isValid(handle)
