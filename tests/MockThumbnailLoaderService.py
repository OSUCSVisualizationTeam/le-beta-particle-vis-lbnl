from typing import Callable, Dict, Optional, Set

import numpy as np

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService


class MockThumbnailLoaderService(ThumbnailLoaderService):
    """No-op thumbnail loader for tests that don't need thumbnails."""

    def __init__(self) -> None:
        self._cache: Dict[int, np.ndarray] = {}
        self.clear_called: int = 0
        self.evict_calls: list = []

    def request_thumbnail(
        self,
        key: int,
        cluster: Cluster,
        on_ready: Callable[[int, np.ndarray], None],
    ) -> None:
        pass

    def clear(self) -> None:
        self.clear_called += 1
        self._cache.clear()

    def evict(self, keep_keys: Set[int]) -> None:
        self.evict_calls.append(keep_keys)

    def get_cached(self, key: int) -> Optional[np.ndarray]:
        return self._cache.get(key)

    def request_cluster_data(
        self,
        cluster: Cluster,
        on_ready: Callable[[Optional[np.ndarray]], None],
    ) -> None:
        on_ready(cluster.data)

    def shutdown(self) -> None:
        pass
