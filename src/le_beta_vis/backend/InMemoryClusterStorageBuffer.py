"""In-memory ClusterStorageBuffer implementation."""

from typing import Generic, Iterator, List, Optional

from le_beta_vis.backend.ClusterStorageBuffer import (
    ClusterStorageBuffer,
    FlushCallback,
    R,
    T,
)


class InMemoryClusterStorageBuffer(ClusterStorageBuffer[T], Generic[T]):
    """Buffers items in a plain list; flushes via the injected callback.

    Not thread-safe by design: each caller (e.g. one FITS file's
    ``cluster_fits`` call on its own daemon thread) owns a fresh
    instance, so there is no shared mutable state to protect.
    """

    def __init__(self, capacity: int, flush_callback: FlushCallback) -> None:
        super().__init__(capacity, flush_callback)
        self._buffer: List[T] = []

    def add(self, item: T) -> None:
        self._buffer.append(item)
        if len(self._buffer) >= self._capacity:
            self.flush()

    def flush(self) -> Optional[R]:
        if not self._buffer:
            return None
        items, self._buffer = self._buffer, []
        return self._flush_callback(items)

    def __len__(self) -> int:
        return len(self._buffer)

    def __iter__(self) -> Iterator[T]:
        return iter(self._buffer)
