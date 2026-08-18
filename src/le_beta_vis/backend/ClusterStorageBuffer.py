"""Generic accumulate-then-flush buffer abstraction.

Not tied to Cluster/ClusterStoreRequest so it can be reused wherever a capacity-triggered batch
flush is useful (e.g. server-side buffering if EPS is later split into its own process serving
multiple distributed ingestion clients), by supplying a different item type and flush callback than
the client-side ingestion use case.
"""

from abc import ABC, abstractmethod
from typing import Callable, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")

FlushCallback = Callable[[List[T]], R]
"""Invoked with the buffered items on flush; its return value is opaque to the buffer."""


class ClusterStorageBuffer(ABC, Generic[T]):
    """Abstract capacity-bounded buffer that auto-flushes when full.

    Subclasses implement the storage mechanics (``add``, ``flush``, ``__len__``, ``__iter__``);
    construction, capacity, and context-manager support are shared here.
    """

    def __init__(self, capacity: int, flush_callback: FlushCallback) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._flush_callback = flush_callback

    @property
    def capacity(self) -> int:
        return self._capacity

    @abstractmethod
    def add(self, item: T) -> None:
        """Buffers item; auto-flushes once len(self) reaches capacity."""
        raise NotImplementedError

    @abstractmethod
    def flush(self) -> Optional[R]:
        """Drains buffered items through flush_callback.

        Returns None without invoking the callback when the buffer is empty; otherwise returns the
        callback's result.
        """
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def __iter__(self) -> Iterator[T]:
        """Non-destructive iteration over currently buffered items."""
        raise NotImplementedError

    def __enter__(self) -> "ClusterStorageBuffer[T]":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self.flush()
        return False
