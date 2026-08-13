"""Live/manual-verification test for the EventRepository dispatcher's
Qt thread marshal (issue #181).

The unit tests in test_ZMQBasedEventRepository.py prove the dispatcher
is *invoked*. They cannot prove the callback actually lands on the Qt
main thread, since that requires a real event loop -- which is the
entire point of the Dispatcher abstraction (ZMQBasedEventRepository
fires callback/on_error from a plain threading.Thread with no Qt
affinity of its own).

This test drives the real cross-thread mechanism MainViewModel wires up
-- a QObject Signal(object) connected with Qt.AutoConnection -- and
asserts the callback executes on the thread that owns the QCoreApplication
event loop, not the worker thread that produced the result.

Requires a running Qt event loop (QCoreApplication; no widgets, no
display server needed). Excluded from headless CI via --ignore in
python-package-conda.yml, per the project's convention for Qt-bug-fix
integration tests tied to a recorded issue. Skipped by default; set
LBNLVIS_LIVE_TESTS=1 to run:

    LBNLVIS_LIVE_TESTS=1 uv run pytest tests/test_live_eventrepository_dispatcher.py -v
"""
import os
import threading
from unittest.mock import MagicMock

import pytest
import zmq
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Qt, Signal

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository

pytestmark = pytest.mark.skipif(
    os.environ.get("LBNLVIS_LIVE_TESTS") != "1",
    reason="Live/manual-verification test; set LBNLVIS_LIVE_TESTS=1 to run.",
)

_TIMEOUT_S = 3.0


class _MainThreadDispatcher(QObject):
    """Mirrors MainViewModel's dispatcher wiring (_dispatchToMainThread /
    _runDispatched): a Signal(object) connected Qt.AutoConnection so
    Signal.emit() always queues onto this object's thread regardless of
    which thread calls it -- the pattern CLAUDE.md prescribes for
    parameterized cross-thread callbacks."""

    _dispatch = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._dispatch.connect(self._run, Qt.AutoConnection)

    def _run(self, fn) -> None:
        fn()

    def as_dispatcher(self):
        return lambda fn: self._dispatch.emit(fn)


def _mock_context():
    ctx = MagicMock(spec=zmq.Context)
    sock = MagicMock(spec=zmq.Socket)
    sock.recv_json.return_value = {"result": "success", "clusters": []}
    ctx.socket.return_value = sock
    return ctx


def test_live_dispatched_callback_runs_on_qt_main_thread():
    app = QCoreApplication.instance() or QCoreApplication([])
    main_thread = threading.current_thread()

    dispatcher = _MainThreadDispatcher()
    repo = ZMQBasedEventRepository(
        MockConfigurationService(),
        context=_mock_context(),
        dispatcher=dispatcher.as_dispatcher(),
    )

    observed = {}
    done = threading.Event()

    def on_success(_clusters) -> None:
        observed["thread"] = threading.current_thread()
        done.set()
        app.quit()

    def on_error(_message) -> None:
        observed["error"] = _message
        done.set()
        app.quit()

    # Failsafe: if the dispatcher silently drops the callable, don't hang
    # the test suite -- fail loudly via the done.wait() assertion below.
    QTimer.singleShot(int(_TIMEOUT_S * 1000), app.quit)

    repo.fetch_clusters(
        query_filter=None,
        limit=10,
        offset=0,
        callback=on_success,
        on_error=on_error,
    )

    app.exec()

    assert done.is_set(), "Timed out waiting for dispatched callback"
    assert "error" not in observed, f"Unexpected on_error: {observed.get('error')}"
    assert observed["thread"] is main_thread, (
        "Callback executed off the Qt main thread -- the dispatcher failed "
        "to marshal it, reintroducing the race issue #181 fixes."
    )
