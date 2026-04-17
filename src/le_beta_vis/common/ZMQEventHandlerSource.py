"""ZMQ ``SUB`` receiver that feeds an :class:`EventHandler`.

Owns one ``zmq.SUB`` socket and one daemon recv thread.  On each
received multipart frame it parses the :class:`EventEnvelope`
and calls :meth:`EventHandler.dispatch` — which in turn enqueues
the envelope onto its per-event-type queue.

Resilience:
- ZMQ automatically reconnects SUB sockets, so transient
  publisher restarts are handled at the socket layer.
- Unrecoverable socket errors trigger an internal reconnect
  with exponential backoff bounded by
  ``event_handler:reconnect_backoff_ms_min`` and
  ``event_handler:reconnect_backoff_ms_max``.
- The :attr:`connected` property exposes whether the recv loop
  believes the connection is healthy, and ``connection_changed``
  fires when that state flips — used by Views to display a
  degraded-mode indicator.
"""

import logging
import threading
from typing import Callable, List, Optional

import zmq

from .ConfigurationService import ConfigurationService
from .EventEnvelope import EventEnvelope
from .EventHandlerInterface import EventHandlerInterface


logger = logging.getLogger(__name__)


_DEFAULT_BACKOFF_MS_MIN = 250
_DEFAULT_BACKOFF_MS_MAX = 8000
_RECV_POLL_TIMEOUT_MS = 250
"""How long ``socket.poll`` waits before returning with no data.
Short enough that ``shutdown()`` is responsive."""


ConnectionChangedCallback = Callable[[bool], None]
"""Signature of the optional connection-state callback.  Fires
with ``True`` on the first successful recv and with ``False``
when the recv loop falls into a reconnect cycle."""


class ZMQEventHandlerSource:
    """SUB-socket reader that dispatches envelopes to an
    :class:`EventHandlerInterface`.

    Args:
        endpoint: The ZMQ endpoint to connect to
            (e.g. ``"ipc:///tmp/EPCEvents.ipc"``).
        event_handler: Destination for every received envelope.
        config: Configuration service used for backoff and
            timeout values.
        context: Optional ``zmq.Context``; defaults to the
            shared instance.  Inject a mock in tests.
        subscriptions: Optional list of topic prefixes to
            subscribe to.  ``None`` subscribes to everything
            (``b""``).  Each entry is a string prefix such as
            ``"cluster."`` or the exact event name.
        on_connection_changed: Optional callback invoked on
            connected→disconnected transitions (and vice versa).
    """

    def __init__(
        self,
        endpoint: str,
        event_handler: EventHandlerInterface,
        config: ConfigurationService,
        *,
        context: Optional[zmq.Context] = None,
        subscriptions: Optional[List[str]] = None,
        on_connection_changed: Optional[ConnectionChangedCallback] = None,
    ) -> None:
        self._endpoint = endpoint
        self._handler = event_handler
        self._config = config
        self._ctx = context or zmq.Context.instance()
        self._subscriptions: List[str] = (
            list(subscriptions) if subscriptions is not None else []
        )
        self._on_connection_changed = on_connection_changed

        self._stop = threading.Event()
        self._socket_lock = threading.Lock()
        self._socket: Optional[zmq.Socket] = None
        self._connected = False

        self._thread = threading.Thread(
            target=self._run,
            name=f"ZMQEventHandlerSource-{endpoint}",
            daemon=True,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Whether the recv loop believes the connection is healthy."""
        return self._connected

    def start(self) -> None:
        """Starts the recv thread.  Idempotent."""
        if self._thread.is_alive():
            return
        self._stop.clear()
        self._thread.start()

    def shutdown(self, timeout_ms: int = 2000) -> None:
        """Stops the recv loop and joins the thread.

        The recv loop's ``poll()`` has a 250 ms timeout so it exits on
        its own once ``_stop`` is set — it then closes its own socket
        in its ``finally`` block.  We only force-close the socket as a
        safety net if the thread fails to exit in time; closing it
        while the recv thread is mid-poll races the poll and produces
        a benign "Socket operation on non-socket" warning.
        """
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(0.0, timeout_ms / 1000.0))
        with self._socket_lock:
            if self._socket is not None:
                try:
                    self._socket.close(linger=0)
                except Exception:
                    logger.exception("Error closing ZMQEventHandlerSource socket")
                self._socket = None

    # ------------------------------------------------------------------
    # Socket management
    # ------------------------------------------------------------------

    def _open_socket(self) -> Optional[zmq.Socket]:
        try:
            socket = self._ctx.socket(zmq.SUB)
            socket.setsockopt(zmq.LINGER, 0)
            socket.setsockopt(zmq.RCVHWM, 10_000)
            if not self._subscriptions:
                socket.setsockopt(zmq.SUBSCRIBE, b"")
            else:
                for prefix in self._subscriptions:
                    socket.setsockopt(zmq.SUBSCRIBE, prefix.encode("utf-8"))
            socket.connect(self._endpoint)
            return socket
        except zmq.ZMQError as exc:
            logger.warning(
                "ZMQEventHandlerSource: failed to open SUB socket on %s: %s",
                self._endpoint,
                exc,
            )
            return None

    def _set_connected(self, connected: bool) -> None:
        if self._connected == connected:
            return
        self._connected = connected
        if self._on_connection_changed is not None:
            try:
                self._on_connection_changed(connected)
            except Exception:
                logger.exception("on_connection_changed callback raised")

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        backoff_min_ms = self._config.get_int(
            "event_handler:reconnect_backoff_ms_min",
            _DEFAULT_BACKOFF_MS_MIN,
            minimum=10,
        )
        backoff_max_ms = self._config.get_int(
            "event_handler:reconnect_backoff_ms_max",
            _DEFAULT_BACKOFF_MS_MAX,
            minimum=backoff_min_ms,
        )
        backoff_ms = backoff_min_ms

        while not self._stop.is_set():
            with self._socket_lock:
                if self._stop.is_set():
                    return
                self._socket = self._open_socket()
            if self._socket is None:
                self._set_connected(False)
                self._sleep_backoff(backoff_ms)
                backoff_ms = min(backoff_max_ms, backoff_ms * 2)
                continue

            try:
                healthy = self._recv_loop(self._socket)
                if healthy:
                    backoff_ms = backoff_min_ms
            finally:
                with self._socket_lock:
                    if self._socket is not None:
                        try:
                            self._socket.close(linger=0)
                        except Exception:
                            logger.exception(
                                "Error closing SUB socket during reconnect"
                            )
                        self._socket = None
                self._set_connected(False)

            if self._stop.is_set():
                return
            self._sleep_backoff(backoff_ms)
            backoff_ms = min(backoff_max_ms, backoff_ms * 2)

    def _recv_loop(self, socket: zmq.Socket) -> bool:
        """Drains messages from ``socket`` until it errors out.

        Returns ``True`` if at least one message was received
        successfully (so the caller can reset backoff), ``False``
        otherwise.
        """
        saw_message = False
        while not self._stop.is_set():
            try:
                events = socket.poll(timeout=_RECV_POLL_TIMEOUT_MS)
            except zmq.ZMQError as exc:
                logger.warning(
                    "ZMQEventHandlerSource: poll error on %s: %s",
                    self._endpoint,
                    exc,
                )
                return saw_message
            if not events:
                continue
            try:
                frames = socket.recv_multipart(flags=zmq.DONTWAIT)
            except zmq.Again:
                continue
            except zmq.ZMQError as exc:
                logger.warning(
                    "ZMQEventHandlerSource: recv error on %s: %s",
                    self._endpoint,
                    exc,
                )
                return saw_message
            saw_message = True
            self._set_connected(True)
            self._handle_frames(frames)
        return saw_message

    def _handle_frames(self, frames: List[bytes]) -> None:
        if len(frames) < 2:
            logger.warning(
                "ZMQEventHandlerSource: ignoring malformed multipart "
                "message with %d frame(s)",
                len(frames),
            )
            return
        try:
            envelope = EventEnvelope.from_json_bytes(frames[1])
        except ValueError as exc:
            logger.warning(
                "ZMQEventHandlerSource: invalid envelope on topic %r: %s",
                frames[0],
                exc,
            )
            return
        try:
            self._handler.dispatch(envelope)
        except Exception:
            logger.exception("ZMQEventHandlerSource: EventHandler.dispatch raised")

    def _sleep_backoff(self, ms: int) -> None:
        # Use stop.wait so shutdown interrupts the sleep promptly.
        self._stop.wait(timeout=max(0.0, ms / 1000.0))
