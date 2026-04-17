"""Unit tests for EventHandler — the full registry + per-type queues."""

import threading
import time
from typing import List

import pytest

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandler import EventHandler
from le_beta_vis.common.EventHandlerExceptions import EventHandlerShutdownError
from mock_configuration_service import MockConfigurationService


@pytest.fixture
def config():
    cfg = MockConfigurationService()
    # Keep defaults permissive so tests don't trip on missing keys.
    cfg.set("event_handler:default_queue_size", 50)
    cfg.set("event_handler:default_overflow_policy", "drop_oldest")
    cfg.set("event_handler:default_coalesce_ms", 0)
    cfg.set("event_handler:default_throttle_ms", 0)
    cfg.set("event_handler:worker_join_timeout_ms", 1000)
    return cfg


@pytest.fixture
def handler(config):
    h = EventHandler(config)
    yield h
    h.shutdown(timeout_ms=1000)


class TestRegistration:

    def test_register_returns_uuid(self, handler):
        cb_id = handler.register_callback("foo", lambda e: None)
        assert isinstance(cb_id, str) and len(cb_id) == 32

    def test_register_creates_queue_lazily(self, handler):
        assert handler.queue_for("foo") is None
        handler.register_callback("foo", lambda e: None)
        assert handler.queue_for("foo") is not None

    def test_unregister_removes_callback(self, handler):
        cb_id = handler.register_callback("foo", lambda e: None)
        assert handler.unregister(cb_id) is True
        assert handler.has_callbacks("foo") is False

    def test_unregister_all_by_event_name(self, handler):
        handler.register_callback("foo", lambda e: None)
        handler.register_callback("foo", lambda e: None)
        assert handler.unregister_all("foo") == 2
        assert handler.has_callbacks("foo") is False


class TestDispatch:

    def test_dispatch_delivers_to_callback(self, handler):
        received: List[EventEnvelope] = []
        done = threading.Event()

        def cb(env):
            received.append(env)
            done.set()

        handler.register_callback("cluster.classified", cb)
        handler.dispatch(EventEnvelope(name="cluster.classified", payload={"x": 1}))

        assert done.wait(timeout=1.0)
        assert len(received) == 1
        assert received[0].payload == {"x": 1}

    def test_dispatch_without_handler_is_silently_dropped(self, handler, caplog):
        import logging
        caplog.set_level(logging.DEBUG)
        handler.dispatch(EventEnvelope(name="nobody.cares"))
        # No crash. A DEBUG log line should be present.
        assert any(
            "No handler registered" in record.message
            for record in caplog.records
        )

    def test_different_event_types_dispatch_in_parallel(self, handler):
        """Ensures a slow handler on one event type does not block another."""
        slow_gate = threading.Event()
        fast_done = threading.Event()
        slow_done = threading.Event()

        def slow_cb(env):
            slow_gate.wait(timeout=2.0)
            slow_done.set()

        def fast_cb(env):
            fast_done.set()

        handler.register_callback("slow.event", slow_cb)
        handler.register_callback("fast.event", fast_cb)

        handler.dispatch(EventEnvelope(name="slow.event"))
        handler.dispatch(EventEnvelope(name="fast.event"))

        # Fast callback must complete even though slow is blocked.
        assert fast_done.wait(timeout=1.0)
        assert not slow_done.is_set()
        slow_gate.set()
        assert slow_done.wait(timeout=1.0)

    def test_multiple_callbacks_for_same_event_run_sequentially(self, handler):
        order: List[int] = []
        done = threading.Event()

        def make_cb(i):
            def cb(env):
                order.append(i)
                if len(order) == 3:
                    done.set()
            return cb

        handler.register_callback("foo", make_cb(0))
        handler.register_callback("foo", make_cb(1))
        handler.register_callback("foo", make_cb(2))
        handler.dispatch(EventEnvelope(name="foo"))

        assert done.wait(timeout=1.0)
        assert order == [0, 1, 2]


class TestShutdown:

    def test_shutdown_prevents_further_work(self, config):
        h = EventHandler(config)
        h.shutdown(timeout_ms=500)

        with pytest.raises(EventHandlerShutdownError):
            h.register_callback("foo", lambda e: None)

        with pytest.raises(EventHandlerShutdownError):
            h.dispatch(EventEnvelope(name="foo"))

    def test_shutdown_is_idempotent(self, config):
        h = EventHandler(config)
        h.shutdown(timeout_ms=500)
        h.shutdown(timeout_ms=500)  # must not raise

    def test_shutdown_joins_all_worker_threads(self, config):
        h = EventHandler(config)
        h.register_callback("a", lambda e: None)
        h.register_callback("b", lambda e: None)
        h.register_callback("c", lambda e: None)

        q_a = h.queue_for("a")
        q_b = h.queue_for("b")
        q_c = h.queue_for("c")
        assert q_a is not None and q_b is not None and q_c is not None

        h.shutdown(timeout_ms=1000)

        # Give join a moment to complete.
        time.sleep(0.05)
        assert not q_a._thread.is_alive()
        assert not q_b._thread.is_alive()
        assert not q_c._thread.is_alive()


class TestPerEventConfig:

    def test_per_event_queue_size_override(self, config):
        config.set("event_handler:foo:queue_size", 7)
        h = EventHandler(config)
        try:
            h.register_callback("foo", lambda e: None)
            q = h.queue_for("foo")
            assert q is not None
            # queue.Queue exposes maxsize directly.
            assert q._queue.maxsize == 7
        finally:
            h.shutdown(timeout_ms=500)

    def test_unknown_overflow_policy_falls_back(self, config):
        config.set("event_handler:default_overflow_policy", "unknown_policy")
        h = EventHandler(config)
        try:
            # Registering still works with a warning; no crash.
            cb_id = h.register_callback("foo", lambda e: None)
            assert isinstance(cb_id, str)
        finally:
            h.shutdown(timeout_ms=500)
