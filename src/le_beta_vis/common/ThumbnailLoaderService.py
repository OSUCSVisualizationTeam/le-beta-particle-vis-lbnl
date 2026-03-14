from abc import ABC, abstractmethod
from typing import Callable, Optional, Set

import numpy as np

from .Cluster import Cluster


class ThumbnailLoaderService(ABC):
    """Abstract interface for asynchronous thumbnail loading.

    Implementations generate cluster thumbnails on background threads
    and deliver results via a per-request callback.
    """

    @abstractmethod
    def request_thumbnail(
        self,
        key: int,
        cluster: Cluster,
        on_ready: Callable[[int, np.ndarray], None],
    ) -> None:
        """Request asynchronous thumbnail generation for *cluster*.

        Args:
            key: Unique identifier (typically the grid row index).
            cluster: The cluster to render.
            on_ready: Callback invoked with ``(key, thumbnail_array)``
                when rendering completes.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Cancel pending work and clear the thumbnail cache."""
        ...

    @abstractmethod
    def evict(self, keep_keys: Set[int]) -> None:
        """Remove cached thumbnails whose keys are not in *keep_keys*.

        Args:
            keep_keys: Set of keys to retain in cache.
        """
        ...

    @abstractmethod
    def get_cached(self, key: int) -> Optional[np.ndarray]:
        """Return the cached thumbnail for *key*, or ``None``.

        Args:
            key: The thumbnail key to look up.
        """
        ...

    @abstractmethod
    def request_cluster_data(
        self,
        cluster: Cluster,
        on_ready: Callable[[Optional[np.ndarray]], None],
    ) -> None:
        """Extract raw pixel data for *cluster* asynchronously.

        Uses the FITS HDU cache for efficient extraction. The result
        is NOT cached — it is delivered once via *on_ready*.

        Args:
            cluster: The cluster whose pixel data to extract.
            on_ready: Callback invoked with the data array or None.
        """
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release all resources (threads, timers, cached data)."""
        ...
