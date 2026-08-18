"""Unit tests for EPSStartupSignals.

Uses ``MagicMock(spec=zmq.Context)`` — no real sockets touched, so the
tests run headless in CI, mirroring ``tests/test_ZMQEventHandlerClient.py``.
"""

from unittest.mock import MagicMock

import zmq

from le_beta_vis.common.EPSStartupSignals import (
    EPS_STARTUP_STATUS_EVENT,
    EPSStartupSignals,
)
from mock_configuration_service import MockConfigurationService


def _mock_context():
    ctx = MagicMock(spec=zmq.Context)
    sock = MagicMock(spec=zmq.Socket)
    ctx.socket.return_value = sock
    return ctx, sock


class TestConstruction:

    def test_binds_configured_endpoint(self):
        ctx, sock = _mock_context()
        config = MockConfigurationService()
        config.set("eps:status_pub_endpoint", "ipc:///tmp/test_status.ipc")

        signals = EPSStartupSignals(config, source="eps", context=ctx)

        sock.bind.assert_called_once_with("ipc:///tmp/test_status.ipc")
        signals.close()

    def test_falls_back_to_default_endpoint_when_unset(self):
        ctx, sock = _mock_context()
        config = MockConfigurationService()

        signals = EPSStartupSignals(config, source="eps", context=ctx)

        sock.bind.assert_called_once_with("ipc:///tmp/EPCStatus.ipc")
        signals.close()


class TestPublishStatus:

    def test_publishes_envelope_with_expected_shape(self):
        ctx, sock = _mock_context()
        config = MockConfigurationService()
        signals = EPSStartupSignals(config, source="eps", context=ctx)

        signals.publish_status(db_connected=True, sockets_bound=False)

        sock.send_multipart.assert_called_once()
        topic, body = sock.send_multipart.call_args[0][0]
        assert topic == EPS_STARTUP_STATUS_EVENT.encode("utf-8")
        assert b'"db_connected":true' in body
        assert b'"sockets_bound":false' in body
        assert b'"eps"' in body
        signals.close()

    def test_publishes_attempt_fields_when_provided(self):
        ctx, sock = _mock_context()
        config = MockConfigurationService()
        signals = EPSStartupSignals(config, source="eps", context=ctx)

        signals.publish_status(
            db_connected=False, sockets_bound=False, attempt=3, max_attempts=20
        )

        _topic, body = sock.send_multipart.call_args[0][0]
        assert b'"attempt":3' in body
        assert b'"max_attempts":20' in body
        signals.close()

    def test_omits_attempt_fields_when_not_provided(self):
        ctx, sock = _mock_context()
        config = MockConfigurationService()
        signals = EPSStartupSignals(config, source="eps", context=ctx)

        signals.publish_status(db_connected=True, sockets_bound=True)

        _topic, body = sock.send_multipart.call_args[0][0]
        assert b'"attempt"' not in body
        assert b'"max_attempts"' not in body
        signals.close()


class TestClose:

    def test_close_releases_socket(self):
        ctx, sock = _mock_context()
        config = MockConfigurationService()
        signals = EPSStartupSignals(config, source="eps", context=ctx)

        signals.close()

        sock.close.assert_called_once()
