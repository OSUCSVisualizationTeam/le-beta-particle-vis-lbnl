"""Unit tests for ZMQEventLoggingHandler.

Verifies that LogRecord objects are translated into EventEnvelope
publishes, that the recursive-feedback filter strips ``zmq`` records,
and that exceptions inside the client do not propagate out of
``emit()``.
"""

import logging
from typing import List

import pytest

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerClient import EventHandlerClient
from le_beta_vis.common.ZMQEventLoggingHandler import ZMQEventLoggingHandler


class _RecordingClient(EventHandlerClient):
    """Captures every published envelope in memory."""

    def __init__(self) -> None:
        self.published: List[EventEnvelope] = []
        self.raise_on_publish = False

    def publish(self, envelope: EventEnvelope) -> None:
        if self.raise_on_publish:
            raise RuntimeError("simulated transport failure")
        self.published.append(envelope)

    def close(self) -> None:
        pass


@pytest.fixture
def client():
    return _RecordingClient()


@pytest.fixture
def logger(client):
    handler = ZMQEventLoggingHandler(client, source="test.logger")
    handler.setLevel(logging.DEBUG)  # let everything through for tests
    log = logging.getLogger("le_beta_vis.test_handler")
    log.handlers = []
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    yield log
    log.removeHandler(handler)


class TestEmit:

    def test_warning_becomes_log_warning_envelope(self, logger, client):
        logger.warning("something fishy")
        assert len(client.published) == 1
        env = client.published[0]
        assert env.name == "log.warning"
        assert env.source == "test.logger"
        assert env.payload["level"] == "WARNING"
        assert env.payload["message"] == "something fishy"
        assert env.payload["logger"] == "le_beta_vis.test_handler"

    def test_error_becomes_log_error_envelope(self, logger, client):
        logger.error("boom")
        assert client.published[-1].name == "log.error"

    def test_info_becomes_log_info_envelope(self, logger, client):
        logger.info("heartbeat")
        assert client.published[-1].name == "log.info"

    def test_exception_payload_contains_exc_text(self, logger, client):
        try:
            raise ValueError("bad value")
        except ValueError:
            logger.exception("wrapping exception")

        env = client.published[-1]
        assert "bad value" in (env.payload["exc_text"] or "")
        assert env.payload["level"] == "ERROR"

    def test_record_format_string_args_are_interpolated(self, logger, client):
        logger.warning("cluster %d failed: %s", 42, "network")
        assert client.published[-1].payload["message"] == (
            "cluster 42 failed: network"
        )


class TestRecursiveFeedbackFilter:

    def test_zmq_library_records_are_dropped(self, client):
        handler = ZMQEventLoggingHandler(client, source="test")
        handler.setLevel(logging.DEBUG)
        zmq_logger = logging.getLogger("zmq.some.submodule")
        zmq_logger.handlers = [handler]
        zmq_logger.setLevel(logging.DEBUG)
        zmq_logger.propagate = False

        try:
            zmq_logger.error("would cause recursive feedback")
            assert client.published == []
        finally:
            zmq_logger.removeHandler(handler)

    def test_non_zmq_records_pass_through(self, client):
        handler = ZMQEventLoggingHandler(client, source="test")
        handler.setLevel(logging.DEBUG)
        log = logging.getLogger("le_beta_vis.not_zmq")
        log.handlers = [handler]
        log.setLevel(logging.DEBUG)
        log.propagate = False

        try:
            log.warning("ok")
            assert len(client.published) == 1
        finally:
            log.removeHandler(handler)


class TestEmitErrorPath:

    def test_client_exception_is_swallowed_via_handleError(
        self, logger, client, capsys
    ):
        """emit() must never raise — logging.Handler.handleError swallows
        the exception (and may write to stderr)."""
        client.raise_on_publish = True
        # This must not raise.
        logger.warning("this will fail to publish")
        # handleError by default prints to stderr.  Capture so test output
        # stays clean; we only care that no exception escaped.
        capsys.readouterr()
