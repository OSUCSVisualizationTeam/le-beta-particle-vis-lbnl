"""Per-event-type bounded queue and worker thread.

Each instance owns one ``queue.Queue``, one daemon worker thread,
and the backpressure / coalesce / throttle configuration for a
single event name.  The :class:`EventHandler` creates one of
these lazily the first time it sees an event name.

Concurrency guarantees provided here:

- Envelopes for one event name are delivered to single callbacks
  in FIFO order.
- Handlers for **different** event names run in parallel because
  each has its own ``EventDispatchQueue`` and worker thread.
- A handler that raises does not stop the worker — the exception
  is logged with ``exc_info=True`` and the next envelope is
  processed.
"""

import logging
import queue
import threading
import time
from enum import Enum
from typing import Callable, List, Optional

from .EventEnvelope import EventEnvelope


logger = logging.getLogger(__name__)


_DROP_LOG_MIN_INTERVAL_S = 1.0
"""Minimum number of seconds between successive drop-warning log
lines for the same event type, to prevent log floods."""


class OverflowPolicy(str, Enum):
    """What to do when the bounded dispatch queue is full."""

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    BLOCK = "block"


_SENTINEL = object()
"""Sentinel value pushed into the queue by ``shutdown()`` to wake
the worker thread and let it exit cleanly."""


CallbackProvider = Callable[[str], List[Callable]]
"""Signature of the snapshot function the queue uses to fetch
current callbacks.  ``EventHandler`` passes
``CallbackRegistry.snapshot_single`` / ``snapshot_batch``."""


class EventDispatchQueue:
    """Bounded dispatch queue for a single event name.

    Spawns its worker daemon thread at construction so the first
    :meth:`enqueue` is ready to deliver immediately.  Callers must
    call :meth:`shutdown` to join the worker cleanly.
    """

    def __init__(
        self,
        event_name: str,
        snapshot_single: CallbackProvider,
        snapshot_batch: CallbackProvider,
        *,
        max_size: int = 100,
        overflow_policy: OverflowPolicy = OverflowPolicy.DROP_OLDEST,
        coalesce_ms: int = 0,
        throttle_ms: int = 0,
        block_timeout_ms: int = 100,
    ) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be > 0")
        self._event_name = event_name
        self._snapshot_single = snapshot_single
        self._snapshot_batch = snapshot_batch
        self._policy = overflow_policy
        self._coalesce_ms = max(0, int(coalesce_ms))
        self._throttle_ms = max(0, int(throttle_ms))
        self._block_timeout_ms = max(0, int(block_timeout_ms))

        self._queue: "queue.Queue[object]" = queue.Queue(maxsize=max_size)
        self._stop = threading.Event()
        self._enqueue_lock = threading.Lock()
        self._dropped_total = 0
        self._last_drop_log_time = 0.0
        self._last_dispatch_time = 0.0

        self._thread = threading.Thread(
            target=self._run,
            name=f"EventDispatch-{event_name}",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def event_name(self) -> str:
        return self._event_name

    @property
    def dropped_total(self) -> int:
        """Total envelopes dropped due to overflow since construction."""
        return self._dropped_total

    def enqueue(self, envelope: EventEnvelope) -> None:
        """Puts an envelope onto the queue per the overflow policy.

        Non-blocking for ``DROP_OLDEST`` and ``DROP_NEWEST``.
        May block up to ``block_timeout_ms`` for ``BLOCK``; if the
        timeout elapses, the envelope is dropped and counted.
        """
        if self._stop.is_set():
            return
        if self._policy is OverflowPolicy.DROP_OLDEST:
            self._enqueue_drop_oldest(envelope)
        elif self._policy is OverflowPolicy.DROP_NEWEST:
            self._enqueue_drop_newest(envelope)
        else:  # BLOCK
            self._enqueue_blocking(envelope)
        self._maybe_log_drops()

    def shutdown(self, timeout_ms: int) -> None:
        """Signals the worker to stop and joins it with a timeout."""
        self._stop.set()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            # Make room: drop one and re-try.
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(_SENTINEL)
            except queue.Full:
                pass
        timeout_s = max(0.0, timeout_ms / 1000.0)
        self._thread.join(timeout=timeout_s)

    # ------------------------------------------------------------------
    # Enqueue strategies
    # ------------------------------------------------------------------

    def _enqueue_drop_oldest(self, envelope: EventEnvelope) -> None:
        with self._enqueue_lock:
            while self._queue.full():
                try:
                    dropped = self._queue.get_nowait()
                    if dropped is _SENTINEL:
                        # Put it back and give up trying to enqueue.
                        try:
                            self._queue.put_nowait(_SENTINEL)
                        except queue.Full:
                            pass
                        return
                    self._dropped_total += 1
                except queue.Empty:
                    break
            try:
                self._queue.put_nowait(envelope)
            except queue.Full:
                self._dropped_total += 1

    def _enqueue_drop_newest(self, envelope: EventEnvelope) -> None:
        try:
            self._queue.put_nowait(envelope)
        except queue.Full:
            self._dropped_total += 1

    def _enqueue_blocking(self, envelope: EventEnvelope) -> None:
        try:
            self._queue.put(envelope, timeout=self._block_timeout_ms / 1000.0)
        except queue.Full:
            self._dropped_total += 1

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is _SENTINEL:
                return
            envelope: EventEnvelope = item  # type: ignore[assignment]

            if self._should_throttle():
                # Trailing-edge throttle: drop this envelope silently,
                # it arrived too soon after the previous dispatch.
                continue

            batch = self._maybe_coalesce(envelope)
            if batch is None:
                return  # sentinel seen during coalesce window
            self._deliver(batch)
            self._last_dispatch_time = time.monotonic()

    def _should_throttle(self) -> bool:
        if self._throttle_ms <= 0:
            return False
        elapsed_ms = (time.monotonic() - self._last_dispatch_time) * 1000.0
        return elapsed_ms < self._throttle_ms

    def _maybe_coalesce(
        self, first: EventEnvelope
    ) -> Optional[List[EventEnvelope]]:
        """Collects envelopes arriving within the coalesce window.

        Returns the collected batch, or ``None`` if a shutdown
        sentinel was drained mid-window.
        """
        batch: List[EventEnvelope] = [first]
        if self._coalesce_ms <= 0:
            return batch
        deadline = time.monotonic() + (self._coalesce_ms / 1000.0)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return batch
            try:
                item = self._queue.get(timeout=remaining)
            except queue.Empty:
                return batch
            if item is _SENTINEL:
                try:
                    self._queue.put_nowait(_SENTINEL)
                except queue.Full:
                    pass
                return None
            batch.append(item)  # type: ignore[arg-type]

    def _deliver(self, batch: List[EventEnvelope]) -> None:
        singles = self._snapshot_single(self._event_name)
        batches = self._snapshot_batch(self._event_name)

        if singles:
            for envelope in batch:
                for cb in singles:
                    try:
                        cb(envelope)
                    except Exception:
                        logger.exception(
                            "Callback for event '%s' raised",
                            self._event_name,
                        )
        if batches:
            for cb in batches:
                try:
                    cb(list(batch))
                except Exception:
                    logger.exception(
                        "Batch callback for event '%s' raised",
                        self._event_name,
                    )

    # ------------------------------------------------------------------
    # Drop logging
    # ------------------------------------------------------------------

    def _maybe_log_drops(self) -> None:
        if self._dropped_total == 0:
            return
        now = time.monotonic()
        if now - self._last_drop_log_time < _DROP_LOG_MIN_INTERVAL_S:
            return
        self._last_drop_log_time = now
        logger.warning(
            "EventDispatchQueue[%s] dropped %d envelopes (policy=%s)",
            self._event_name,
            self._dropped_total,
            self._policy.value,
        )
