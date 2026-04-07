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
    EPSFitsRecord,
    FitsClusterQueryFilter,
)
from .EventRepository import EventRepository

logger = logging.getLogger(__name__)


class NoOpEventRepository(EventRepository):
    """Fallback EventRepository that returns empty results.

    All methods log a warning indicating the EPS is unavailable
    and return safe defaults.
    """

    def fetch_events(self) -> List[Cluster]:
        """Returns an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: fetch_events called but " "EPS is unavailable"
        )
        return []

    def query_clusters(
        self, query_filter: Optional[ClusterQueryFilter] = None
    ) -> List[Cluster]:
        """Returns an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: query_clusters called but " "EPS is unavailable"
        )
        return []

    def store_cluster(self, request: ClusterStoreRequest) -> Optional[int]:
        """Returns None — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: store_cluster called but " "EPS is unavailable"
        )
        return None

    def update_classification(self, request: ClassificationUpdateRequest) -> bool:
        """Returns False — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: update_classification called "
            "but EPS is unavailable"
        )
        return False

    def query_fits(self, fits_id: Optional[int] = None) -> List[EPSFitsRecord]:
        """Returns an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: query_fits called but " "EPS is unavailable"
        )
        return []

    def query_fits_clusters(
        self, query_filter: Optional[FitsClusterQueryFilter] = None
    ) -> List[Cluster]:
        """Returns an empty list — EPS is unavailable."""
        logger.warning(
            "NoOpEventRepository: query_fits_clusters called but "
            "EPS is unavailable"
        )
        return []
