from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from .Cluster import Cluster
from .EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    EPSFitsRecord,
    FitsClusterQueryFilter,
    FitsQueryFilter,
    FitsStoreRequest,
)

onCluster = Callable[[List[Cluster]], None]
onFits = Callable[[List[EPSFitsRecord]], None]
onUpdate = Callable[[bool], None]
onError = Callable[[str], None]
Dispatcher = Callable[[Callable[[], None]], None]


class EventRepository(ABC):
    """Abstract interface for fetching persisted cluster events.

    Concrete implementations may use ZMQ, direct SQL, or hardcoded data (mock).  The frontend depends only on this interface,
    allowing the backend to evolve independently.
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

        .. deprecated::
            Implementations are not required to bound this request, which
            can return an entire table in one reply. Prefer
            :meth:`fetch_clusters`, which is bounded by
            ``eps:retrieval_limit_default``/``eps:retrieval_limit_max``.
        """
        raise NotImplementedError

    def fetch_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        limit: Optional[int],
        offset: int,
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Bounded, paginated cluster retrieval.

        Args:
            query_filter: Optional filter criteria. ``None`` means no
                filtering beyond pagination.
            limit: Maximum number of clusters to return. ``None`` means
                the implementation should apply its configured default
                (e.g. ``eps:retrieval_limit_default``).
            offset: Number of rows to skip.
        """
        raise NotImplementedError

    def fetch_clusters_sync(
        self,
        limit: Optional[int],
        offset: int,
        query_filter: Optional[ClusterQueryFilter] = None,
    ) -> List[Cluster]:
        """Synchronous counterpart to :meth:`fetch_clusters`.

        ``limit`` and ``offset`` are required (no default) so every caller states its paging intent explicitly rather than
        silently inheriting a page size — an omitted ``limit`` previously masked a truncated result set at one call site. Pass
        ``limit=None`` explicitly to opt into the implementation's configured default.

        Callers already running on a background thread may call this directly to avoid an async callback round-trip.
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
        self,
        limit: int,
        offset: int,
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Return newest-first clusters, bounded by limit/offset.

        Ordered server-side by FITS date descending.  Used by the
        Live Mode fallback provider to page through historical
        clusters without client-side sorting.

        Args:
            limit: Maximum number of clusters to return.
            offset: Number of rows to skip from the newest.
        """
        raise NotImplementedError

    def query_recent_clusters_sync(
        self, limit: int, offset: int = 0
    ) -> List[Cluster]:
        """Synchronous newest-first retrieval for worker-thread callers.

        Callers already running on a background thread (e.g. the Live Mode ``FallbackClusterProvider``) may call this directly
        to avoid bouncing through an async callback.
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
        callback: onCluster,
        on_error: onError,
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

    def query_fits_sync(
        self,
        query_filter: Optional[FitsQueryFilter] = None,
    ) -> List[EPSFitsRecord]:
        """Returns FITS records matching *query_filter*, or all records if None.

        Callers already on a background thread may call this directly to avoid an async callback round-trip.
        """
        raise NotImplementedError

    def store_fits_sync(self, request: FitsStoreRequest) -> Optional[int]:
        """Registers a FITS file in EPS; returns its database ID or None on failure."""
        raise NotImplementedError


def fetch_all_hdu_clusters_sync(
    repository: EventRepository,
    fits_id: int,
    hdu_id: int,
    page_limit: int,
) -> List[Cluster]:
    """Fetches every cluster stored for one FITS file's HDU, looping paged requests.

    Scoped to a single ``(fits_id, hdu_id)`` pair so it cannot be used to pull an unbounded, unfiltered slice of the
    ``clusters`` table — callers needing a broader or custom query should page :meth:`EventRepository.fetch_clusters_sync`
    themselves. A page shorter than ``page_limit`` signals the result set is exhausted.
    """
    query_filter = ClusterQueryFilter(fits_id=fits_id, hdu_id=hdu_id)
    result: List[Cluster] = []
    offset = 0
    while True:
        page = repository.fetch_clusters_sync(page_limit, offset, query_filter)
        result.extend(page)
        if len(page) < page_limit:
            break
        offset += len(page)
    return result
