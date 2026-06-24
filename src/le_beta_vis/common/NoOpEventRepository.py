"""No-op fallback repository used when the EPS backend is unavailable.

Every method returns an empty/default value and logs a warning.
"""

import logging
from typing import List, Optional

from .Cluster import Cluster
from .EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    FitsClusterQueryFilter,
)
from .EventRepository import EventRepository, onCluster, onError, onFits, onUpdate

logger = logging.getLogger(__name__)


class NoOpEventRepository(EventRepository):
    """Fallback EventRepository that returns empty results.

    All methods log a warning indicating the EPS is unavailable
    and return safe defaults.
    """

    def fetch_events(
            self,
            callback: onCluster,
            on_error: onError,
    ) -> None:
        """Invokes ``callback`` with an empty list — EPS is unavailable."""
        logger.warning("NoOpEventRepository: fetch_events called but EPS is unavailable")
        callback([])

    def fetch_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        limit: Optional[int],
        offset: int,
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Invokes ``callback`` with an empty list — EPS is unavailable."""
        logger.warning("NoOpEventRepository: fetch_clusters called but EPS is unavailable")
        callback([])

    def fetch_clusters_sync(
        self,
        query_filter: Optional[ClusterQueryFilter] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Cluster]:
        """Returns an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: fetch_clusters_sync called but EPS is unavailable"
        )
        return []

    def query_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Invokes ``callback`` with an empty list — EPS is unavailable."""
        logger.warning("NoOpEventRepository: query_clusters called but EPS is unavailable")
        callback([])

    def query_recent_clusters(
        self,
        limit: int,
        offset: int,
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Invokes ``callback`` with an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: query_recent_clusters called but "
            "EPS is unavailable"
        )
        callback([])

    def query_recent_clusters_sync(
        self, limit: int, offset: int = 0
    ) -> List[Cluster]:
        """Returns an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: query_recent_clusters_sync called but "
            "EPS is unavailable"
        )
        return []

    def store_cluster(self, request: ClusterStoreRequest) -> Optional[int]:
        """Returns None — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: store_cluster called but " "EPS is unavailable"
        )
        return None

    def update_classification(
        self,
        request: ClassificationUpdateRequest,
        callback: onUpdate,
        on_error: onError
    ) -> None:
        """Returns False — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: update_classification called "
            "but EPS is unavailable"
        )
        on_error("NoOpEventRepository: update_classification called "
                 "but EPS is unavailable")

    def query_fits(
            self,
            fits_id: Optional[int],
            callback: onFits,
            on_error: onError,
    ) -> None:
        """Invokes ``callback`` with an empty list — EPS is unavailable."""
        logger.warning("NoOpEventRepository: query_fits called but EPS is unavailable")
        callback([])

    def query_fits_clusters(
        self,
        query_filter: Optional[FitsClusterQueryFilter],
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Invokes ``callback`` with an empty list — EPS is unavailable."""
        logger.warning("NoOpEventRepository: query_fits_clusters called but EPS is unavailable")
        callback([])
