"""Unit tests for StartupReadinessViewModel.

Uses a real ``EventHandler`` and dispatches synthetic ``EventEnvelope``s
directly — no ZMQ transport needed, since ``EventHandler`` is pure
Python. Callback delivery is asynchronous (a worker thread), so tests
synchronize on a ``threading.Event`` set by a second callback registered
after the ViewModel's — ``CallbackRegistry`` delivers callbacks for the
same event name in registration order, so by the time that second
callback fires, the ViewModel's own callback has already updated its
state. This mirrors the pattern in ``tests/test_EventHandler.py``.
"""

import threading
import unittest
from unittest.mock import patch

from le_beta_vis.common.EPSStartupSignals import EPS_STARTUP_STATUS_EVENT
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandler import EventHandler
from le_beta_vis.frontend.viewmodels.StartupReadinessViewModel import (
    StartupReadinessViewModel,
)
from mock_configuration_service import MockConfigurationService


def _dispatch_and_wait(handler: EventHandler, envelope: EventEnvelope) -> None:
    """Dispatches ``envelope`` and blocks until every registered callback
    for its event name has run, so the caller can assert on ViewModel
    state deterministically despite EventHandler's async dispatch."""
    done = threading.Event()
    callback_id = handler.register_callback(envelope.name, lambda _env: done.set())
    try:
        handler.dispatch(envelope)
        assert done.wait(timeout=1.0), "dispatch did not complete in time"
    finally:
        handler.unregister(callback_id)


class TestInitialState(unittest.TestCase):

    def test_not_ready_before_any_event(self):
        config = MockConfigurationService()
        handler = EventHandler(config)
        vm = StartupReadinessViewModel(config, handler)

        snapshot = vm.poll()

        self.assertFalse(snapshot.ready)
        self.assertFalse(snapshot.degraded)
        self.assertFalse(snapshot.db_connected)
        self.assertFalse(snapshot.sockets_bound)
        self.assertEqual(snapshot.message, "Starting backend services…")


class TestSocketsBoundIsFinalWord(unittest.TestCase):

    def test_sockets_bound_and_db_connected_is_ready_not_degraded(self):
        config = MockConfigurationService()
        handler = EventHandler(config)
        vm = StartupReadinessViewModel(config, handler)

        _dispatch_and_wait(
            handler,
            EventEnvelope(
                name=EPS_STARTUP_STATUS_EVENT,
                payload={"db_connected": True, "sockets_bound": True},
            ),
        )

        snapshot = vm.poll()
        self.assertTrue(snapshot.ready)
        self.assertFalse(snapshot.degraded)
        self.assertEqual(snapshot.message, "Ready.")

    def test_sockets_bound_without_db_connected_is_ready_and_degraded(self):
        """EPS having given up on the DB is EPS's final word — the splash
        should proceed immediately rather than waiting out its own
        timeout on top of EPS's already-exhausted retry budget."""
        config = MockConfigurationService()
        handler = EventHandler(config)
        vm = StartupReadinessViewModel(config, handler)

        _dispatch_and_wait(
            handler,
            EventEnvelope(
                name=EPS_STARTUP_STATUS_EVENT,
                payload={"db_connected": False, "sockets_bound": True},
            ),
        )

        snapshot = vm.poll()
        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.degraded)
        self.assertIn("database", snapshot.message)


class TestWaitingMessage(unittest.TestCase):

    def test_reports_retry_attempt_progress(self):
        config = MockConfigurationService()
        handler = EventHandler(config)
        vm = StartupReadinessViewModel(config, handler)

        _dispatch_and_wait(
            handler,
            EventEnvelope(
                name=EPS_STARTUP_STATUS_EVENT,
                payload={
                    "db_connected": False,
                    "sockets_bound": False,
                    "attempt": 3,
                    "max_attempts": 20,
                },
            ),
        )

        snapshot = vm.poll()
        self.assertFalse(snapshot.ready)
        self.assertEqual(snapshot.message, "Connecting to database (attempt 3/20)…")


class TestOverallTimeout(unittest.TestCase):

    @patch(
        "le_beta_vis.frontend.viewmodels.StartupReadinessViewModel.time.monotonic"
    )
    def test_degrades_after_timeout_with_no_events_at_all(self, mock_monotonic):
        config = MockConfigurationService()
        config.set("gui:startup:ready_timeout_ms", 12000)
        handler = EventHandler(config)

        mock_monotonic.return_value = 0.0
        vm = StartupReadinessViewModel(config, handler)

        mock_monotonic.return_value = 20.0  # 20s later, past the 12s timeout
        snapshot = vm.poll()

        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.degraded)
        self.assertFalse(snapshot.sockets_bound)
        self.assertIn("backend service", snapshot.message)

    @patch(
        "le_beta_vis.frontend.viewmodels.StartupReadinessViewModel.time.monotonic"
    )
    def test_not_yet_degraded_before_timeout(self, mock_monotonic):
        config = MockConfigurationService()
        config.set("gui:startup:ready_timeout_ms", 12000)
        handler = EventHandler(config)

        mock_monotonic.return_value = 0.0
        vm = StartupReadinessViewModel(config, handler)

        mock_monotonic.return_value = 5.0  # 5s later, still under the 12s timeout
        snapshot = vm.poll()

        self.assertFalse(snapshot.ready)
        self.assertFalse(snapshot.degraded)


if __name__ == '__main__':
    unittest.main()
