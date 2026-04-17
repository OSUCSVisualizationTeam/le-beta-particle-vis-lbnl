"""UUID-indexed callback registry used by the EventHandler.

The registry is the single source of truth for which callbacks
are interested in which event names.  It is thread-safe for all
operations and exposes snapshot methods that the dispatch worker
threads use to iterate callbacks without holding the lock during
callback execution.
"""

import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class _CallbackEntry:
    """Internal record for a single registered callback."""

    callback_id: str
    event_name: str
    callback: Callable
    is_batch: bool


class CallbackRegistry:
    """Thread-safe map of event name → registered callbacks.

    All public methods acquire an internal ``RLock``.  Snapshot
    methods return plain lists so the dispatcher can iterate
    them without holding the lock during user-supplied callback
    execution (which might re-enter the registry).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_event: Dict[str, Dict[str, _CallbackEntry]] = {}
        self._by_id: Dict[str, str] = {}

    def register(
        self,
        event_name: str,
        callback: Callable,
        *,
        is_batch: bool = False,
    ) -> str:
        """Registers a new callback for ``event_name``.

        Args:
            event_name: The event name to subscribe to.
            callback: The callable to invoke on matching events.
            is_batch: If ``True``, the callback is treated as a
                batched-delivery callback and receives a list of
                envelopes instead of one at a time.

        Returns:
            A new UUID string that identifies this registration.
        """
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("event_name must be a non-empty string")
        if not callable(callback):
            raise TypeError("callback must be callable")

        callback_id = uuid.uuid4().hex
        entry = _CallbackEntry(
            callback_id=callback_id,
            event_name=event_name,
            callback=callback,
            is_batch=is_batch,
        )
        with self._lock:
            bucket = self._by_event.setdefault(event_name, {})
            bucket[callback_id] = entry
            self._by_id[callback_id] = event_name
        return callback_id

    def unregister(self, callback_id: str) -> bool:
        """Removes a callback by its UUID.

        Returns:
            ``True`` if a callback was removed, ``False`` if the
            UUID was unknown.
        """
        with self._lock:
            event_name = self._by_id.pop(callback_id, None)
            if event_name is None:
                return False
            bucket = self._by_event.get(event_name)
            if bucket is None:
                return False
            bucket.pop(callback_id, None)
            if not bucket:
                self._by_event.pop(event_name, None)
            return True

    def unregister_all(self, event_name: str) -> int:
        """Removes every callback registered for ``event_name``.

        Returns:
            The number of callbacks that were removed.
        """
        with self._lock:
            bucket = self._by_event.pop(event_name, None)
            if not bucket:
                return 0
            for callback_id in list(bucket.keys()):
                self._by_id.pop(callback_id, None)
            return len(bucket)

    def snapshot_single(self, event_name: str) -> List[Callable]:
        """Returns a snapshot list of single-delivery callbacks
        for ``event_name`` in registration order."""
        with self._lock:
            bucket = self._by_event.get(event_name)
            if not bucket:
                return []
            return [
                entry.callback
                for entry in bucket.values()
                if not entry.is_batch
            ]

    def snapshot_batch(self, event_name: str) -> List[Callable]:
        """Returns a snapshot list of batch-delivery callbacks
        for ``event_name`` in registration order."""
        with self._lock:
            bucket = self._by_event.get(event_name)
            if not bucket:
                return []
            return [
                entry.callback
                for entry in bucket.values()
                if entry.is_batch
            ]

    def event_names(self) -> List[str]:
        """Returns a snapshot list of event names with at least
        one registered callback."""
        with self._lock:
            return list(self._by_event.keys())

    def count(self, event_name: Optional[str] = None) -> int:
        """Returns the number of callbacks registered.

        Args:
            event_name: If given, counts only callbacks for that
                event name.  If ``None``, counts all callbacks.
        """
        with self._lock:
            if event_name is None:
                return len(self._by_id)
            bucket = self._by_event.get(event_name)
            return len(bucket) if bucket else 0

    def clear(self) -> None:
        """Removes every registered callback."""
        with self._lock:
            self._by_event.clear()
            self._by_id.clear()
