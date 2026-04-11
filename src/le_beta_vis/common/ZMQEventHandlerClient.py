"""ZMQ ``PUB`` implementation of :class:`EventHandlerClient`.

The client owns a single ``zmq.PUB`` socket.  Each envelope is
sent as a two-part ZMQ multipart message so subscribers can use
cheap prefix filtering on the topic frame before deserializing
the payload:

- Frame 0: UTF-8 encoded event name (the ZMQ topic)
- Frame 1: UTF-8 encoded JSON body of the envelope

``bind_or_connect`` determines whether the PUB socket binds the
endpoint (typical for the backend publisher that owns the IPC
path) or connects to an existing endpoint (rare — useful for
fan-in through an XSUB/XPUB proxy).

A ``zmq.Context`` may be injected at construction for testability;
this mirrors :class:`ZMQBasedEventRepository`.
"""

import logging
import threading
from typing import Literal, Optional

import zmq

from .EventEnvelope import EventEnvelope
from .EventHandlerClient import EventHandlerClient


logger = logging.getLogger(__name__)


_DEFAULT_LINGER_MS = 0
_DEFAULT_SNDHWM = 10_000
"""High-water mark for outbound messages on the PUB socket.  ZMQ
silently drops when exceeded for PUB sockets — by design, the
PUB/SUB pattern prefers dropping over blocking the producer."""


class ZMQEventHandlerClient(EventHandlerClient):
    """Thread-safe ``zmq.PUB`` publisher for :class:`EventEnvelope`.

    Args:
        endpoint: The ZMQ endpoint (e.g. ``"ipc:///tmp/EPCEvents.ipc"``).
        bind_or_connect: ``"bind"`` to bind the endpoint (backend
            publisher); ``"connect"`` to connect to an existing
            endpoint.  Defaults to ``"bind"``.
        context: Optional ``zmq.Context`` to use.  Defaults to
            ``zmq.Context.instance()``.  Injected in tests.
        linger_ms: Socket LINGER option in milliseconds.
        sndhwm: Send high-water mark.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        bind_or_connect: Literal["bind", "connect"] = "bind",
        context: Optional[zmq.Context] = None,
        linger_ms: int = _DEFAULT_LINGER_MS,
        sndhwm: int = _DEFAULT_SNDHWM,
    ) -> None:
        if bind_or_connect not in ("bind", "connect"):
            raise ValueError(
                f"bind_or_connect must be 'bind' or 'connect', "
                f"got {bind_or_connect!r}"
            )
        self._endpoint = endpoint
        self._ctx = context or zmq.Context.instance()
        self._lock = threading.Lock()
        self._closed = False

        self._socket: zmq.Socket = self._ctx.socket(zmq.PUB)
        self._socket.setsockopt(zmq.LINGER, int(linger_ms))
        self._socket.setsockopt(zmq.SNDHWM, int(sndhwm))
        try:
            if bind_or_connect == "bind":
                self._socket.bind(endpoint)
            else:
                self._socket.connect(endpoint)
        except zmq.ZMQError:
            # Release the socket so the caller doesn't leak a
            # half-initialized client.
            self._socket.close(linger=0)
            raise

        logger.debug(
            "ZMQEventHandlerClient %s %s",
            bind_or_connect,
            endpoint,
        )

    # ------------------------------------------------------------------
    # EventHandlerClient
    # ------------------------------------------------------------------

    def publish(self, envelope: EventEnvelope) -> None:
        """Serializes and publishes an envelope.

        Swallows transient transport errors — see
        :class:`EventHandlerClient` contract.  Callers must not
        rely on publish for reliable delivery; PUB/SUB is
        best-effort by design.
        """
        with self._lock:
            if self._closed:
                return
            try:
                self._socket.send_multipart(
                    [envelope.topic_bytes(), envelope.to_json_bytes()],
                    flags=zmq.DONTWAIT,
                )
            except zmq.Again:
                logger.warning(
                    "ZMQEventHandlerClient: PUB send would block "
                    "(event=%s id=%s); dropping",
                    envelope.name,
                    envelope.id,
                )
            except zmq.ZMQError as exc:
                logger.warning(
                    "ZMQEventHandlerClient: send failed for event=%s: %s",
                    envelope.name,
                    exc,
                )
            except Exception:
                logger.exception(
                    "ZMQEventHandlerClient: unexpected error publishing %s",
                    envelope.name,
                )

    def close(self) -> None:
        """Closes the PUB socket.  Idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._socket.close(linger=0)
            except Exception:
                logger.exception("Error closing ZMQEventHandlerClient socket")

    # ------------------------------------------------------------------
    # Context manager support (convenient for smoke tests)
    # ------------------------------------------------------------------

    def __enter__(self) -> "ZMQEventHandlerClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
