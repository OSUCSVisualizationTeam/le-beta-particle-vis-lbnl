"""Abstract base for components that supply Cluster objects.

The Live Mode pipeline consumes clusters through this interface
so providers can be swapped or stubbed in tests without touching
queue logic.  Concrete implementations include
``FreshClusterProvider`` (live EventHandler events) and
``FallbackClusterProvider`` (EPS historical query).
"""

from abc import ABC, abstractmethod
from typing import List

from .Cluster import Cluster

ClusterBatch = List[Cluster]
"""Type alias for a list of clusters returned by a provider."""


class ClusterProvider(ABC):
    """Abstract source of Cluster objects.

    Subclasses implement :meth:`fetch` to return up to *count*
    clusters from their backing source (live event bus, database,
    mock data, etc.).
    """

    @abstractmethod
    def fetch(self, count: int) -> ClusterBatch:
        """Extract up to ``count`` clusters from this provider.

        Implementations must be thread-safe.  Returning fewer than
        ``count`` items is valid when the source does not have
        enough available.

        Args:
            count: Maximum number of clusters to return.

        Returns:
            A list of at most ``count`` ``Cluster`` objects.
            An empty list signals that no clusters are available.
        """
        raise NotImplementedError


class NoOpClusterProvider(ClusterProvider):
    """ClusterProvider that always returns an empty list.

    Use as a test double or when a provider dependency is not
    yet available.
    """

    def fetch(self, count: int) -> ClusterBatch:
        """Returns an empty list regardless of count."""
        return []
