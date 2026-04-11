"""Unit tests for ZMQEventHandlerSource (SUB-side recv loop).

The tests mock ``zmq.Context`` and inject preset multipart frames via
a fake socket.  No real IPC is used, so the tests are headless and
deterministic.
"""

import threading
import time
from typing import List
from unittest.mock import MagicMock

import pytest
import zmq

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface
from le_beta_vis.common.ZMQEventHandlerSource import ZMQEventHandlerSource
from mock_configuration_service import MockConfigurationService


class _RecordingHandler(EventHandlerInterface):
    """Minimal EventHandlerInterface stub that records every dispatch."""

    def __init__(self) -> None:
        self.received: List[EventEnvelope] = []
        self.cv = threading.Condition()

    def register_callback(self, event_name, callback):
        raise NotImplementedError

    def register_batch_callback(self, event_name, callback):
        raise NotImplementedError

    def unregister(self, callback_id):
        raise NotImplementedError

    def unregister_all(self, event_name):
        raise NotImplementedError

    def dispatch(self, envelope):
        with self.cv:
            self.received.append(envelope)
            self.cv.notify_all()

    def shutdown(self, timeout_ms=2000):
        pass

    def wait_for(self, count: int, timeout: float = 2.0) -> bool:
        with self.cv:
            deadline = time.monotonic() + timeout
            while len(self.received) < count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.cv.wait(timeout=remaining)
            return True


def _fake_socket_with_frames(frames_sequence: List[List[bytes]]) -> MagicMock:
    """Creates a mock SUB socket that yields preset multipart frames,
    then blocks on further poll() calls."""
    sock = MagicMock(spec=zmq.Socket)
    frames_iter = iter(frames_sequence)
    done_event = threading.Event()

    def poll_side_effect(timeout=0):
        try:
            next_frames = next(frames_iter)  # noqa: F841 peek nothing
            # Rewind: we'll deliver via recv_multipart immediately.
            frames_iter.__class__  # no-op
            sock.__pending_frames = next_frames  # type: ignore[attr-defined]
            return zmq.POLLIN
        except StopIteration:
            done_event.wait(timeout=(timeout or 0) / 1000.0)
            return 0

    def recv_multipart_side_effect(flags=0):
        pending = getattr(sock, "__pending_frames", None)
        if pending is None:
            raise zmq.Again("no data")
        sock.__pending_frames = None  # type: ignore[attr-defined]
        return pending

    sock.poll.side_effect = poll_side_effect
    sock.recv_multipart.side_effect = recv_multipart_side_effect
    sock._done_event = done_event  # type: ignore[attr-defined]
    return sock


def _mock_context(sock: MagicMock) -> MagicMock:
    ctx = MagicMock(spec=zmq.Context)
    ctx.socket.return_value = sock
    return ctx


@pytest.fixture
def config():
    cfg = MockConfigurationService()
    cfg.set("event_handler:reconnect_backoff_ms_min", 10)
    cfg.set("event_handler:reconnect_backoff_ms_max", 50)
    return cfg


class TestDispatch:

    def test_delivers_received_envelope_to_handler(self, config):
        env = EventEnvelope(name="cluster.classified", payload={"i": 1})
        sock = _fake_socket_with_frames(
            [[env.topic_bytes(), env.to_json_bytes()]]
        )
        ctx = _mock_context(sock)

        handler = _RecordingHandler()
        source = ZMQEventHandlerSource(
            endpoint="ipc:///tmp/test.ipc",
            event_handler=handler,
            config=config,
            context=ctx,
        )
        source.start()
        try:
            assert handler.wait_for(1, timeout=2.0)
            assert handler.received[0].name == "cluster.classified"
            assert handler.received[0].payload == {"i": 1}
        finally:
            sock._done_event.set()  # type: ignore[attr-defined]
            source.shutdown(timeout_ms=500)

    def test_subscription_prefixes_passed_to_socket(self, config):
        sock = _fake_socket_with_frames([])
        ctx = _mock_context(sock)

        handler = _RecordingHandler()
        source = ZMQEventHandlerSource(
            endpoint="ipc:///tmp/test.ipc",
            event_handler=handler,
            config=config,
            context=ctx,
            subscriptions=["cluster.", "log.error"],
        )
        source.start()
        try:
            # Give the recv loop time to open the socket.
            time.sleep(0.05)
            subscribe_calls = [
                call
                for call in sock.setsockopt.call_args_list
                if call.args and call.args[0] == zmq.SUBSCRIBE
            ]
            subscribed_prefixes = {call.args[1] for call in subscribe_calls}
            assert b"cluster." in subscribed_prefixes
            assert b"log.error" in subscribed_prefixes
        finally:
            sock._done_event.set()  # type: ignore[attr-defined]
            source.shutdown(timeout_ms=500)

    def test_default_subscription_is_catch_all(self, config):
        sock = _fake_socket_with_frames([])
        ctx = _mock_context(sock)

        handler = _RecordingHandler()
        source = ZMQEventHandlerSource(
            endpoint="ipc:///tmp/test.ipc",
            event_handler=handler,
            config=config,
            context=ctx,
        )
        source.start()
        try:
            time.sleep(0.05)
            subscribe_calls = [
                call
                for call in sock.setsockopt.call_args_list
                if call.args and call.args[0] == zmq.SUBSCRIBE
            ]
            subscribed_prefixes = {call.args[1] for call in subscribe_calls}
            assert b"" in subscribed_prefixes
        finally:
            sock._done_event.set()  # type: ignore[attr-defined]
            source.shutdown(timeout_ms=500)


class TestErrorHandling:

    def test_malformed_frames_are_skipped(self, config):
        # One malformed (single-frame) message, then a valid one.
        valid_env = EventEnvelope(name="valid.event")
        sock = _fake_socket_with_frames(
            [
                [b"only-one-frame"],
                [valid_env.topic_bytes(), valid_env.to_json_bytes()],
            ]
        )
        ctx = _mock_context(sock)

        handler = _RecordingHandler()
        source = ZMQEventHandlerSource(
            endpoint="ipc:///tmp/test.ipc",
            event_handler=handler,
            config=config,
            context=ctx,
        )
        source.start()
        try:
            assert handler.wait_for(1, timeout=2.0)
            assert handler.received[0].name == "valid.event"
        finally:
            sock._done_event.set()  # type: ignore[attr-defined]
            source.shutdown(timeout_ms=500)

    def test_invalid_json_is_skipped(self, config):
        valid_env = EventEnvelope(name="valid.event")
        sock = _fake_socket_with_frames(
            [
                [b"bad", b"not-json"],
                [valid_env.topic_bytes(), valid_env.to_json_bytes()],
            ]
        )
        ctx = _mock_context(sock)

        handler = _RecordingHandler()
        source = ZMQEventHandlerSource(
            endpoint="ipc:///tmp/test.ipc",
            event_handler=handler,
            config=config,
            context=ctx,
        )
        source.start()
        try:
            assert handler.wait_for(1, timeout=2.0)
            assert handler.received[0].name == "valid.event"
        finally:
            sock._done_event.set()  # type: ignore[attr-defined]
            source.shutdown(timeout_ms=500)


class TestConnectionState:

    def test_on_connection_changed_fires_on_first_message(self, config):
        env = EventEnvelope(name="ping")
        sock = _fake_socket_with_frames(
            [[env.topic_bytes(), env.to_json_bytes()]]
        )
        ctx = _mock_context(sock)

        handler = _RecordingHandler()
        state_changes: List[bool] = []
        state_cv = threading.Condition()

        def on_change(connected: bool):
            with state_cv:
                state_changes.append(connected)
                state_cv.notify_all()

        source = ZMQEventHandlerSource(
            endpoint="ipc:///tmp/test.ipc",
            event_handler=handler,
            config=config,
            context=ctx,
            on_connection_changed=on_change,
        )
        source.start()
        try:
            with state_cv:
                deadline = time.monotonic() + 2.0
                while True not in state_changes:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    state_cv.wait(timeout=remaining)
            assert True in state_changes
            assert source.connected is True
        finally:
            sock._done_event.set()  # type: ignore[attr-defined]
            source.shutdown(timeout_ms=500)
