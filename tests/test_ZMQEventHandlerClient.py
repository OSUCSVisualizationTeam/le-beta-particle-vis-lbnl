"""Unit tests for ZMQEventHandlerClient (PUB publisher).

Uses ``MagicMock(spec=zmq.Context)`` — no real sockets touched, so the
tests run headless in CI.
"""

import json
from unittest.mock import MagicMock

import pytest
import zmq

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.ZMQEventHandlerClient import ZMQEventHandlerClient


def _mock_context():
    ctx = MagicMock(spec=zmq.Context)
    sock = MagicMock(spec=zmq.Socket)
    ctx.socket.return_value = sock
    return ctx, sock


class TestConstruction:

    def test_bind_calls_socket_bind(self):
        ctx, sock = _mock_context()
        client = ZMQEventHandlerClient(
            "ipc:///tmp/test.ipc",
            bind_or_connect="bind",
            context=ctx,
        )
        try:
            sock.bind.assert_called_once_with("ipc:///tmp/test.ipc")
            sock.connect.assert_not_called()
        finally:
            client.close()

    def test_connect_calls_socket_connect(self):
        ctx, sock = _mock_context()
        client = ZMQEventHandlerClient(
            "ipc:///tmp/test.ipc",
            bind_or_connect="connect",
            context=ctx,
        )
        try:
            sock.connect.assert_called_once_with("ipc:///tmp/test.ipc")
            sock.bind.assert_not_called()
        finally:
            client.close()

    def test_rejects_invalid_bind_or_connect(self):
        ctx, _sock = _mock_context()
        with pytest.raises(ValueError, match="bind_or_connect"):
            ZMQEventHandlerClient(
                "ipc:///tmp/test.ipc",
                bind_or_connect="invalid",  # type: ignore[arg-type]
                context=ctx,
            )

    def test_bind_failure_closes_socket(self):
        ctx, sock = _mock_context()
        sock.bind.side_effect = zmq.ZMQError("eaddrinuse")
        with pytest.raises(zmq.ZMQError):
            ZMQEventHandlerClient(
                "ipc:///tmp/test.ipc",
                bind_or_connect="bind",
                context=ctx,
            )
        sock.close.assert_called()


class TestPublish:

    def test_publish_sends_multipart_with_topic_and_json(self):
        ctx, sock = _mock_context()
        client = ZMQEventHandlerClient("ipc:///tmp/test.ipc", context=ctx)
        env = EventEnvelope(name="cluster.classified", payload={"fits_id": 42})
        try:
            client.publish(env)
            sock.send_multipart.assert_called_once()
            args, kwargs = sock.send_multipart.call_args
            frames = args[0]
            assert len(frames) == 2
            assert frames[0] == b"cluster.classified"
            decoded = json.loads(frames[1].decode("utf-8"))
            assert decoded["name"] == "cluster.classified"
            assert decoded["payload"] == {"fits_id": 42}
            assert kwargs.get("flags") == zmq.DONTWAIT
        finally:
            client.close()

    def test_publish_swallows_zmq_again(self):
        ctx, sock = _mock_context()
        sock.send_multipart.side_effect = zmq.Again("would block")
        client = ZMQEventHandlerClient("ipc:///tmp/test.ipc", context=ctx)
        try:
            # Must not raise.
            client.publish(EventEnvelope(name="x"))
        finally:
            client.close()

    def test_publish_swallows_zmq_error(self):
        ctx, sock = _mock_context()
        sock.send_multipart.side_effect = zmq.ZMQError("transport error")
        client = ZMQEventHandlerClient("ipc:///tmp/test.ipc", context=ctx)
        try:
            client.publish(EventEnvelope(name="x"))
        finally:
            client.close()

    def test_publish_after_close_is_noop(self):
        ctx, sock = _mock_context()
        client = ZMQEventHandlerClient("ipc:///tmp/test.ipc", context=ctx)
        client.close()
        sock.send_multipart.reset_mock()
        client.publish(EventEnvelope(name="x"))
        sock.send_multipart.assert_not_called()


class TestClose:

    def test_close_is_idempotent(self):
        ctx, sock = _mock_context()
        client = ZMQEventHandlerClient("ipc:///tmp/test.ipc", context=ctx)
        client.close()
        client.close()
        # close was called on the socket at most once — the second client
        # close is a no-op guarded by the _closed flag.
        assert sock.close.call_count == 1

    def test_context_manager_closes_on_exit(self):
        ctx, sock = _mock_context()
        with ZMQEventHandlerClient("ipc:///tmp/test.ipc", context=ctx) as client:
            assert client is not None
        sock.close.assert_called()
