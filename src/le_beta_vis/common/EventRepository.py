from abc import ABC, abstractmethod
from typing import List, Optional

from .Cluster import Cluster
from .EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    EPSFitsRecord,
)


class EventRepository(ABC):
    """Abstract interface for fetching persisted cluster events.

    Concrete implementations may use ZMQ, direct SQL, or
    hardcoded data (mock).  The frontend depends only on this
    interface, allowing the backend to evolve independently.
    """

    @abstractmethod
    def fetch_events(self) -> List[Cluster]:
        """Returns all available cluster events.

        Implementations should return a list of ``Cluster``
        objects with classification scores and pixel data
        populated.
        """
        raise NotImplementedError

    def query_clusters(
        self, query_filter: Optional[ClusterQueryFilter] = None
    ) -> List[Cluster]:
        """Filtered cluster query.

        Args:
            query_filter: Optional filter criteria.  ``None``
                means return all clusters (same as
                ``fetch_events``).

        Returns:
            Matching ``Cluster`` objects.
        """
        raise NotImplementedError

    def store_cluster(
        self, request: ClusterStoreRequest
    ) -> Optional[int]:
        """Persist a cluster to the backend.

        Returns:
            The new cluster ID on success, or ``None``.
        """
        raise NotImplementedError

    def update_classification(
        self, request: ClassificationUpdateRequest
    ) -> bool:
        """Update classification on an existing cluster.

        Returns:
            ``True`` on success.
        """
        raise NotImplementedError

    def query_fits(
        self, fits_id: Optional[int] = None
    ) -> List[EPSFitsRecord]:
        """Retrieve FITS metadata.

        Args:
            fits_id: Optional filter by FITS ID.

        Returns:
            Matching FITS records.
        """
        raise NotImplementedError
