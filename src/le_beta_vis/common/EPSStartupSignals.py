"""Dedicated startup-readiness status producer for EPS.

Publishes ``eps.startup.status`` envelopes on their own PUB socket
(``eps:status_pub_endpoint``) — entirely separate from
:class:`~le_beta_vis.common.ZMQEventLoggingHandler.ZMQEventLoggingHandler`'s
log-forwarding socket. Status and logs are unrelated concerns carried on
independent channels so a future distributed-EPS deployment can route them
independently (e.g. different machines, different retention/backpressure
policies) without untangling a shared transport later.

Lives in ``common/`` rather than ``backend/`` because both the EPS producer
and the frontend consumer need to agree on the envelope name and payload
shape, mirroring how :mod:`~le_beta_vis.common.EPSDataClasses` (the EPS wire
format) lives in ``common/`` rather than ``backend/``.
"""

import logging
from typing import Optional

import zmq

from .ConfigurationService import ConfigurationService
from .EventEnvelope import EventEnvelope
from .ZMQEventHandlerClient import ZMQEventHandlerClient

logger = logging.getLogger(__name__)


EPS_STARTUP_STATUS_EVENT = "eps.startup.status"
"""Event name for EPS startup-readiness status envelopes."""

DEFAULT_STATUS_PUB_ENDPOINT = "ipc:///tmp/EPCStatus.ipc"
"""Fallback endpoint if ``eps:status_pub_endpoint`` is unset in config.
Mirrors the default in ``config/defaults.yaml``. Public (mirrors
:data:`~le_beta_vis.common.ZMQEventHandlerClient.DEFAULT_EVENT_PUB_ENDPOINT`)
so callers resolving the same endpoint (e.g. ``app.py``'s startup-phase
subscriber) can import it instead of repeating the literal."""


class EPSStartupSignals:
    """Publishes EPS startup-readiness status on its own dedicated bus.

    Owns a single :class:`ZMQEventHandlerClient` bound to
    ``eps:status_pub_endpoint`` for the lifetime of this instance. Not a
    ``logging.Handler`` and unrelated to
    :class:`~le_beta_vis.common.ZMQEventLoggingHandler.ZMQEventLoggingHandler`
    — a standalone producer dedicated to this one envelope type.
    """

    def __init__(
        self,
        config: ConfigurationService,
        source: str = "eps",
        context: Optional[zmq.Context] = None,
    ) -> None:
        endpoint = config.get("eps:status_pub_endpoint", DEFAULT_STATUS_PUB_ENDPOINT)
        self._source = source
        self._client = ZMQEventHandlerClient(
            endpoint=endpoint,
            bind_or_connect="bind",
            context=context,
            bind_key="eps:status_pub_endpoint",
        )

    def publish_status(
        self,
        db_connected: bool,
        sockets_bound: bool,
        attempt: Optional[int] = None,
        max_attempts: Optional[int] = None,
    ) -> None:
        """Publishes the current EPS startup-readiness status.

        Args:
            db_connected: Whether the MySQL connection is established.
            sockets_bound: Whether the EPS ZMQ data/command sockets are
                bound and serving.
            attempt: Current MySQL connection attempt number, if a retry
                is in progress. ``None`` when not applicable.
            max_attempts: Configured maximum attempt count, paired with
                ``attempt``.
        """
        payload = {
            "db_connected": db_connected,
            "sockets_bound": sockets_bound,
        }
        if attempt is not None:
            payload["attempt"] = attempt
        if max_attempts is not None:
            payload["max_attempts"] = max_attempts
        self._client.publish(
            EventEnvelope(
                name=EPS_STARTUP_STATUS_EVENT,
                payload=payload,
                source=self._source,
            )
        )

    def close(self) -> None:
        """Releases the underlying PUB socket. Idempotent."""
        self._client.close()
