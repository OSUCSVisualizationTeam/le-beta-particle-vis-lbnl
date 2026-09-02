"""``logging.Handler`` that forwards log records through an
:class:`EventHandlerClient`.

Attach this handler to the backend's root logger (or any logger
whose records should be surfaced on the frontend) and every
emitted ``LogRecord`` becomes an :class:`EventEnvelope` with
``name = "log.<levelname>"``.  The frontend's
:class:`EventHandler` can then route these events to a status
bar, a log viewer, or any other consumer.

Recursive-feedback protection: the handler installs a filter
that drops any record whose logger name starts with ``"zmq"``.
Without this, a socket error inside the ZMQ library would emit
a log record, which would be forwarded through the same
``zmq`` socket, which could emit another error, etc.
"""

import logging
from typing import Any, Dict, Literal, Optional

from .EventEnvelope import EventEnvelope
from .EventHandlerClient import EventHandlerClient


_FALLBACK_FORMATTER = logging.Formatter()
"""Used only to format exception tracebacks when the caller has
not installed a custom formatter on this handler."""


def _level_to_event_name(levelname: str) -> str:
    return f"log.{levelname.lower()}"


class _ZMQLogFilter(logging.Filter):
    """Drops records from the ``zmq`` library itself to prevent
    a recursive logging → publish → socket error → logging loop."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith("zmq")


class ZMQEventLoggingHandler(logging.Handler):
    """Publishes ``LogRecord``s as :class:`EventEnvelope`s.

    Args:
        client: The :class:`EventHandlerClient` to publish through.
            Typically a :class:`ZMQEventHandlerClient` shared with
            other producers in the same process.
        source: Free-form identifier stored in the envelope's
            ``source`` field (e.g. ``"eps"``).
        level: Minimum log level to forward.  Defaults to
            ``logging.WARNING`` to avoid flooding the bus.
    """

    def __init__(
        self,
        client: EventHandlerClient,
        source: str,
        level: int = logging.WARNING,
    ) -> None:
        super().__init__(level=level)
        self._client = client
        self._source = source
        self.addFilter(_ZMQLogFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            envelope = EventEnvelope(
                name=_level_to_event_name(record.levelname),
                payload=self._record_to_payload(record),
                source=self._source,
            )
            self._client.publish(envelope)
        except Exception:
            # Defer to the standard Handler error path.  This must
            # never raise or the root logger will blow up.
            self.handleError(record)

    def _record_to_payload(
        self, record: logging.LogRecord
    ) -> Dict[str, Any]:
        exc_text: Optional[str] = None
        if record.exc_info:
            formatter = self.formatter or _FALLBACK_FORMATTER
            exc_text = formatter.formatException(record.exc_info)
        return {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "lineno": record.lineno,
            "created": record.created,
            "exc_text": exc_text,
        }


def attach_to_root_logger(
    endpoint: str,
    source: str,
    level: int = logging.WARNING,
    bind_or_connect: Literal["bind", "connect"] = "bind",
    bind_key: Optional[str] = None,
) -> "ZMQEventLoggingHandler":
    """Create a :class:`ZMQEventLoggingHandler` and attach it to the root logger.

    This is the one-call setup for any backend service that wants its log
    records forwarded to the frontend status bar over the EventHandler bus.
    It creates a :class:`~le_beta_vis.common.ZMQEventHandlerClient` (a ZMQ
    PUB socket), wraps it in a :class:`ZMQEventLoggingHandler`, registers
    the handler on ``logging.root``, and returns the handler so the caller
    can remove it on shutdown.

    Args:
        endpoint: ZMQ endpoint the PUB socket will bind or connect to.
            Must match the ``event_handler:zmq_pub_endpoint`` config key
            used by the frontend's ``ZMQEventHandlerSource``
            (default :data:`~le_beta_vis.common.ZMQEventHandlerClient.DEFAULT_EVENT_PUB_ENDPOINT`).
        source: Free-form identifier stored in every envelope's ``source``
            field, e.g. ``"eps"`` or ``"classifier"``.  Appears in the
            frontend log view so operators know which service emitted the
            message.
        level: Minimum :mod:`logging` level to forward.  Defaults to
            ``logging.WARNING`` — enough to surface actionable problems
            without flooding the bus with routine info records.
            Pass ``logging.INFO`` if info-level progress messages should
            also appear in the status bar.
        bind_or_connect: Whether the PUB socket **binds** the endpoint
            (``"bind"``, the default) or **connects** to an existing one
            (``"connect"``).  Backend services that own the IPC path should
            use ``"bind"``; a secondary producer joining an existing broker
            proxy should use ``"connect"``.
        bind_key: Passed straight through to
            :class:`~le_beta_vis.common.ZMQEventHandlerClient.ZMQEventHandlerClient`
            — the configuration key this endpoint came from, checked
            against the startup IPC bind registry before binding.  See
            that class's docstring for details.

    Returns:
        The :class:`ZMQEventLoggingHandler` that was added to the root
        logger.  Keep a reference and pass it to
        ``logging.root.removeHandler(handler)`` during graceful shutdown to
        avoid dangling sockets.

    Example::

        # In a backend service __init__, after loading config:
        self._log_handler = attach_to_root_logger(
            endpoint=self.config.get("event_handler:zmq_pub_endpoint")
                     or DEFAULT_EVENT_PUB_ENDPOINT,
            source="eps",
        )

        # On shutdown:
        logging.root.removeHandler(self._log_handler)
    """
    # Import here to avoid a circular dependency at module load time:
    # ZMQEventHandlerClient → zmq → (potentially) logging.
    from .ZMQEventHandlerClient import ZMQEventHandlerClient

    client = ZMQEventHandlerClient(
        endpoint=endpoint,
        bind_or_connect=bind_or_connect,
        bind_key=bind_key,
    )
    handler = ZMQEventLoggingHandler(client, source=source, level=level)
    logging.root.addHandler(handler)
    return handler
