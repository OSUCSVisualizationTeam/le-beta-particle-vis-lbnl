from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from .Cluster import Cluster
from .EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    EPSFitsRecord,
    FitsClusterQueryFilter,
)

onCluster = Callable[[List[Cluster]], None]
onFits = Callable[[List[EPSFitsRecord]], None]
onUpdate = Callable[[bool], None]
onError = Callable[[str], None]

class EventRepository(ABC):
    """Abstract interface for fetching persisted cluster events.

    Concrete implementations may use ZMQ, direct SQL, or
    hardcoded data (mock).  The frontend depends only on this
    interface, allowing the backend to evolve independently.
    """

    @abstractmethod
    def fetch_events(
        self,
        callback: onCluster,
        on_error: onError,
        ) -> None:
        """Returns all available cluster events from callback.

        Implementations should return a list of ``Cluster``
        objects with classification scores and pixel data
        populated.
        """
        raise NotImplementedError

    def query_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        callback: onCluster,
        on_error: onError,
        ) -> None:
        """Filtered cluster query.

        Args:
            query_filter: Optional filter criteria.  ``None``
                means return all clusters (same as
                ``fetch_events``).

        Returns:
            Matching ``Cluster`` objects.
        """
        raise NotImplementedError

    def query_recent_clusters(
        self, limit: int, offset: int = 0
    ) -> List[Cluster]:
        """Return newest-first clusters, bounded by limit/offset.

        Ordered server-side by FITS date descending.  Used by the
        Live Mode fallback provider to page through historical
        clusters without client-side sorting.

        Args:
            limit: Maximum number of clusters to return.
            offset: Number of rows to skip from the newest.

        Returns:
            Matching ``Cluster`` objects, newest first.
        """
        raise NotImplementedError

    def store_cluster(
        self,
        request: ClusterStoreRequest
    ) -> Optional[int]:
        """Persist a cluster to the backend.

        Returns:
            The new cluster ID on success, or ``None``.
        """
        raise NotImplementedError

    def update_classification(
        self,
        request: ClassificationUpdateRequest,
        callback: onUpdate,
        on_error: onError,
    ) -> None:
        """Update classification on an existing cluster.

        Returns:
            ``True`` on success.
        """
        raise NotImplementedError

    def query_fits(
        self,
        fits_id: Optional[int],
        callback: onFits,
        on_error: onError,
    ) -> None:
        """Retrieve FITS metadata.

        Args:
            fits_id: Optional filter by FITS ID.

        Returns:
            Matching FITS records.
        """
        raise NotImplementedError

    def query_fits_clusters(
        self,
        query_filter: Optional[FitsClusterQueryFilter],
        callback: Callable,
        on_error: Callable
    ) -> None:
        """Retrieve clusters filtered by FITS metadata.

        Args:
            query_filter: Optional filter criteria.  ``None``
                means return clusters for all FITS files.

        Returns:
            Matching ``Cluster`` objects, enriched with FITS
            filename and date from the backend response.
        """
        raise NotImplementedError
