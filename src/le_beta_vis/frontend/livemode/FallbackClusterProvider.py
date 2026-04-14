"""EPS-backed fallback cluster provider for the Live Mode screensaver.

Pulls clusters from the Event Persistence Service via
``EventRepository.query_recent_clusters()``, which returns
newest-first rows server-side (ORDER BY date DESC + LIMIT/OFFSET).
The provider maintains a walking cursor so successive ``fetch``
calls traverse the table without returning the same rows twice; on
exhaustion the cursor wraps to the top.

``fetch`` is synchronous and may block on a ZMQ round-trip — it
must only be called from a daemon background thread.
"""

import logging
import threading

from le_beta_vis.common.ClusterProvider import ClusterBatch, ClusterProvider
from le_beta_vis.common.EventRepository import EventRepository

logger = logging.getLogger(__name__)


class FallbackClusterProvider(ClusterProvider):
    """ClusterProvider that walks newest-first clusters from EPS.

    Each call to ``fetch(count)`` requests ``count`` clusters at
    the current offset. The offset advances by the number of rows
    received. When the backend returns fewer rows than requested
    the table has been exhausted: the cursor resets to 0 and an
    additional query tops up the remainder.

    Args:
        repository: The event repository to query.
    """

    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository
        self._offset = 0
        self._lock = threading.Lock()

    def fetch(self, count: int) -> ClusterBatch:
        """Fetch up to ``count`` newest clusters from EPS.

        Uses server-side ordering and a walking offset so repeated
        calls do not return the same rows. Wraps to offset 0 when
        the DB is exhausted.

        Args:
            count: Maximum number of clusters to return.

        Returns:
            A list of at most ``count`` clusters, newest first
            relative to the current cursor position.
        """
        if count <= 0:
            return []
        try:
            with self._lock:
                offset = self._offset
            first = self._repository.query_recent_clusters(
                limit=count, offset=offset
            )
            received = len(first)

            if received >= count:
                with self._lock:
                    self._offset = offset + received
                return first

            # Backend exhausted — wrap the cursor and top up.
            remaining = count - received
            with self._lock:
                self._offset = 0
            second = self._repository.query_recent_clusters(
                limit=remaining, offset=0
            )
            with self._lock:
                self._offset = len(second)
            return first + second
        except Exception:
            logger.exception("FallbackClusterProvider: fetch failed")
            return []
