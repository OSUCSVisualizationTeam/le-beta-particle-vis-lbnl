"""Concrete :class:`EventHandlerInterface` implementation.

Owns one :class:`CallbackRegistry` and a dict of per-event-type
:class:`EventDispatchQueue` instances, each with its own bounded
queue and worker daemon thread.  Configuration is read at
construction time via :class:`ConfigurationService` using the
``event_handler:*`` namespace.
"""

import logging
import threading
import time
from typing import Dict, Optional

from .CallbackRegistry import CallbackRegistry
from .ConfigurationService import ConfigurationService
from .EventDispatchQueue import EventDispatchQueue, OverflowPolicy
from .EventEnvelope import EventEnvelope
from .EventHandlerExceptions import EventHandlerShutdownError
from .EventHandlerInterface import (
    BatchEventCallback,
    EventCallback,
    EventHandlerInterface,
)


logger = logging.getLogger(__name__)


_DEFAULT_QUEUE_SIZE = 100
_DEFAULT_OVERFLOW_POLICY = "drop_oldest"
_DEFAULT_COALESCE_MS = 0
_DEFAULT_THROTTLE_MS = 0
_DEFAULT_WORKER_JOIN_TIMEOUT_MS = 2000


class EventHandler(EventHandlerInterface):
    """Per-event-type dispatcher running on daemon worker threads.

    See :class:`EventHandlerInterface` for the contract.  This
    implementation lazily creates one :class:`EventDispatchQueue`
    per unique event name the first time it sees that name —
    either via ``register_callback`` / ``register_batch_callback``
    or via ``dispatch``.  A dispatch of an unknown event name
    with no callbacks is logged at DEBUG and dropped.
    """

    def __init__(self, config: ConfigurationService) -> None:
        self._config = config
        self._registry = CallbackRegistry()
        self._queues: Dict[str, EventDispatchQueue] = {}
        self._queues_lock = threading.RLock()
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False

    # ------------------------------------------------------------------
    # EventHandlerInterface
    # ------------------------------------------------------------------

    def register_callback(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> str:
        self._ensure_not_shutdown()
        callback_id = self._registry.register(
            event_name, callback, is_batch=False
        )
        self._ensure_queue(event_name)
        return callback_id

    def register_batch_callback(
        self,
        event_name: str,
        callback: BatchEventCallback,
    ) -> str:
        self._ensure_not_shutdown()
        callback_id = self._registry.register(
            event_name, callback, is_batch=True
        )
        self._ensure_queue(event_name)
        return callback_id

    def unregister(self, callback_id: str) -> bool:
        return self._registry.unregister(callback_id)

    def unregister_all(self, event_name: str) -> int:
        return self._registry.unregister_all(event_name)

    def dispatch(self, envelope: EventEnvelope) -> None:
        self._ensure_not_shutdown()
        with self._queues_lock:
            dispatch_queue = self._queues.get(envelope.name)
        if dispatch_queue is None:
            logger.debug(
                "No handler registered for event '%s'; dropping envelope %s",
                envelope.name,
                envelope.id,
            )
            return
        dispatch_queue.enqueue(envelope)

    def shutdown(self, timeout_ms: int = _DEFAULT_WORKER_JOIN_TIMEOUT_MS) -> None:
        with self._shutdown_lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True

        with self._queues_lock:
            queues = list(self._queues.values())
            self._queues.clear()

        if not queues:
            self._registry.clear()
            return

        deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)
        for dispatch_queue in queues:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            dispatch_queue.shutdown(remaining_ms)

        self._registry.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_not_shutdown(self) -> None:
        if self._is_shutdown:
            raise EventHandlerShutdownError(
                "EventHandler has been shut down; cannot accept new work"
            )

    def _ensure_queue(self, event_name: str) -> None:
        with self._queues_lock:
            if event_name in self._queues:
                return
            self._queues[event_name] = EventDispatchQueue(
                event_name=event_name,
                snapshot_single=self._registry.snapshot_single,
                snapshot_batch=self._registry.snapshot_batch,
                max_size=self._resolve_queue_size(event_name),
                overflow_policy=self._resolve_overflow_policy(event_name),
                coalesce_ms=self._resolve_coalesce_ms(event_name),
                throttle_ms=self._resolve_throttle_ms(event_name),
            )

    # --- Config lookups with per-event override and sensible fallback ---

    def _resolve_queue_size(self, event_name: str) -> int:
        default = self._config.get_int(
            "event_handler:default_queue_size",
            _DEFAULT_QUEUE_SIZE,
            minimum=1,
        )
        return self._config.get_int(
            f"event_handler:{event_name}:queue_size",
            default,
            minimum=1,
        )

    def _resolve_overflow_policy(self, event_name: str) -> OverflowPolicy:
        default_raw = str(
            self._config.get(
                "event_handler:default_overflow_policy",
                _DEFAULT_OVERFLOW_POLICY,
            )
        )
        raw = str(
            self._config.get(
                f"event_handler:{event_name}:overflow_policy",
                default_raw,
            )
        )
        try:
            return OverflowPolicy(raw)
        except ValueError:
            logger.warning(
                "Unknown overflow policy '%s' for event '%s'; "
                "falling back to %s",
                raw,
                event_name,
                _DEFAULT_OVERFLOW_POLICY,
            )
            return OverflowPolicy(_DEFAULT_OVERFLOW_POLICY)

    def _resolve_coalesce_ms(self, event_name: str) -> int:
        default = self._config.get_int(
            "event_handler:default_coalesce_ms",
            _DEFAULT_COALESCE_MS,
            minimum=0,
        )
        return self._config.get_int(
            f"event_handler:{event_name}:coalesce_ms",
            default,
            minimum=0,
        )

    def _resolve_throttle_ms(self, event_name: str) -> int:
        default = self._config.get_int(
            "event_handler:default_throttle_ms",
            _DEFAULT_THROTTLE_MS,
            minimum=0,
        )
        return self._config.get_int(
            f"event_handler:{event_name}:throttle_ms",
            default,
            minimum=0,
        )

    # ------------------------------------------------------------------
    # Introspection (useful in tests and debugging)
    # ------------------------------------------------------------------

    def has_callbacks(self, event_name: str) -> bool:
        """Returns ``True`` if any callback is registered for
        ``event_name``."""
        return self._registry.count(event_name) > 0

    def queue_for(self, event_name: str) -> Optional[EventDispatchQueue]:
        """Returns the dispatch queue for ``event_name`` if one
        exists, otherwise ``None``.  Intended for tests only."""
        with self._queues_lock:
            return self._queues.get(event_name)
