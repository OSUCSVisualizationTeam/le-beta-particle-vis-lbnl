"""EPS-backed fallback cluster provider for the Live Mode screensaver.

Fetches recent historical clusters from the Event Persistence
Service via ``EventRepository.query_clusters()``.  Since
``ClusterQueryFilter`` has no sort parameter, sorting is done
client-side on ``cluster.date`` descending so the most recent
events fill the screensaver first.
"""

import logging
from typing import Optional

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterProvider import ClusterBatch, ClusterProvider
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.EventRepository import EventRepository

logger = logging.getLogger(__name__)


def _date_sort_key(cluster: Cluster) -> str:
    """Sort key for descending date order.

    Clusters with ``None`` dates sort to the end.
    """
    return cluster.date or ""


class FallbackClusterProvider(ClusterProvider):
    """ClusterProvider that fetches historical clusters from EPS.

    Called by the ViewModel when the display queue is below
    capacity.  The ``fetch`` method is synchronous and may block
    on a ZMQ round-trip — it must only be called from a daemon
    background thread.

    Args:
        repository: The event repository to query.
        query_filter: Optional filter for the EPS query.  When
            ``None``, all available clusters are fetched.
    """

    def __init__(
        self,
        repository: EventRepository,
        query_filter: Optional[ClusterQueryFilter] = None,
    ) -> None:
        self._repository = repository
        self._query_filter = query_filter

    def fetch(self, count: int) -> ClusterBatch:
        """Fetch up to ``count`` most-recent clusters from EPS.

        Queries the repository, sorts results by date descending
        (client-side), and returns at most ``count`` items.

        This method is synchronous and may block on a ZMQ
        round-trip.  It must only be called from a daemon
        background thread.

        Args:
            count: Maximum number of clusters to return.

        Returns:
            A list of at most ``count`` clusters, newest first.
        """
        try:
            clusters = self._repository.query_clusters(
                self._query_filter,
            )
            clusters.sort(key=_date_sort_key, reverse=True)
            return clusters[:count]
        except Exception:
            logger.exception("FallbackClusterProvider: fetch failed")
            return []
