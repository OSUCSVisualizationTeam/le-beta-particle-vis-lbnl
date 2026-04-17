"""Unified bounded queue for the Live Mode cluster display pipeline.

Holds fresh clusters (from live events) and fallback clusters (from
EPS) as a single contiguous list, separated by a partition pointer.
The queue is designed to stay full: fresh clusters insert at the
pointer; fallback clusters fill the tail when fresh supply is
insufficient.

Structure at any point in time::

    [fresh_0, ..., fresh_n-1 | pointer | fallback_0, ..., fallback_m-1, None, ...]

The pointer is an integer index.  Slots ``0..pointer-1`` are fresh;
slots ``pointer..`` are fallback (may include ``None`` for empty
tail).  Capacity is fixed at construction (rows * cols).
"""

import threading
from typing import List, Optional

from le_beta_vis.common.Cluster import Cluster


class IncomingDataQueue:
    """Thread-safe bounded queue combining fresh and fallback clusters.

    The queue always has exactly ``capacity`` slots.  Slots not yet
    filled by either source hold ``None``.  The ``pointer`` separates
    the fresh section (front) from the fallback section (back).

    Thread safety:
        ``append_fallback`` may be called from a daemon thread.
        All other mutations happen on the main thread inside
        ``ViewModel.advance()``.  A single ``threading.Lock``
        guards the boundary between the two.

    Args:
        capacity: Total number of slots (rows * cols).
    """

    def __init__(self, capacity: int) -> None:
        self._capacity = max(1, capacity)
        self._slots: List[Optional[Cluster]] = [None] * self._capacity
        self._pointer: int = 0
        self._lock = threading.Lock()

    # --- Properties ---

    @property
    def capacity(self) -> int:
        """Total number of slots in the queue."""
        return self._capacity

    @property
    def pointer(self) -> int:
        """Index of the first fallback slot (number of fresh clusters)."""
        with self._lock:
            return self._pointer

    @property
    def fresh_count(self) -> int:
        """Number of fresh cluster slots (0..pointer-1)."""
        with self._lock:
            return self._pointer

    @property
    def is_full(self) -> bool:
        """True when all slots are occupied (no None entries)."""
        with self._lock:
            return all(s is not None for s in self._slots)

    # --- Main-thread operations ---

    def dequeue_front(self) -> Optional[Cluster]:
        """Remove and return the cluster at index 0.

        Shifts all remaining slots left by one position.  The tail
        slot becomes ``None``.  The pointer decrements by one if it
        was greater than zero (a fresh cluster was removed).

        Returns:
            The frontmost cluster, or ``None`` if the front slot
            was empty.
        """
        with self._lock:
            front = self._slots[0]
            self._slots = self._slots[1:] + [None]
            if self._pointer > 0:
                self._pointer -= 1
            return front

    def insert_fresh(self, clusters: List[Cluster]) -> None:
        """Insert fresh clusters at the pointer position.

        Inserts at the end of the fresh section, before fallback
        entries.  Existing fallback entries shift right; excess
        beyond capacity is truncated.  Must be called from the
        main thread.

        Args:
            clusters: Clusters to insert, in arrival order.
        """
        with self._lock:
            for cluster in clusters:
                self._slots.insert(self._pointer, cluster)
                self._pointer += 1
            self._slots = self._slots[: self._capacity]
            self._pointer = min(self._pointer, self._capacity)

    def append_fallback(self, clusters: List[Cluster]) -> None:
        """Fill ``None`` slots from the pointer position onward.

        Overwrites only ``None`` entries; existing non-None
        fallback clusters are left intact.  May be called from a
        daemon background thread.

        Args:
            clusters: Clusters to place in empty fallback slots.
        """
        with self._lock:
            it = iter(clusters)
            for i in range(self._pointer, self._capacity):
                if self._slots[i] is None:
                    try:
                        self._slots[i] = next(it)
                    except StopIteration:
                        break

    def slots_needed(self) -> int:
        """Returns the number of ``None`` slots.

        Used by the ViewModel to decide how many fallback clusters
        to request.
        """
        with self._lock:
            return self._slots.count(None)

    def snapshot(self) -> List[Optional[Cluster]]:
        """Returns a shallow copy of the current slot list.

        Safe to call from any thread; the caller owns the returned
        list.
        """
        with self._lock:
            return list(self._slots)

    def clear(self) -> None:
        """Reset all slots to ``None`` and the pointer to zero."""
        with self._lock:
            self._slots = [None] * self._capacity
            self._pointer = 0
