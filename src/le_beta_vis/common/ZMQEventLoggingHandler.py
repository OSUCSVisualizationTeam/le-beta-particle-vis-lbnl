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
from typing import Any, Dict, Optional

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
