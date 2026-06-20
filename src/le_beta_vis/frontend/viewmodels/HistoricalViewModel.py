import logging
import threading
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, List, Optional, Set

import numpy as np

from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.frontend.fitsconverters.interface import Colormap


@dataclass
class _LoadedPage:
    """One fetched page of clusters, anchored to its global offset."""

    offset: int
    clusters: List[Cluster]

    @property
    def count(self) -> int:
        return len(self.clusters)


class HistoricalViewModel:
    """ViewModel for the Historical Event Analysis mode.

    Manages event data from an ``EventRepository`` and the currently
    selected event for the Detail Inspector. Loaded clusters are held
    in a bounded sliding window of pages: as the user scrolls, new
    pages are fetched and old ones evicted so memory stays bounded
    regardless of session length. Every "flat index" used across this
    class, ``EventGridWidget``, and ``ThumbnailLoaderService`` is a
    stable global cluster index (its position in the backend's full
    ordering), not a position in whatever page happens to be resident.

    Pure Python class — no Qt dependencies.
    """

    def __init__(
        self,
        configService: ConfigurationService,
        physicsManager: PhysicsConversionManager,
        repository: EventRepository,
        thumbnailService: ThumbnailLoaderService,
    ):
        self._config = configService
        self._physics = physicsManager
        self._repository = repository
        self._thumbnail_service = thumbnailService

        # Event state
        self._events: List[Cluster] = []
        self._selectedIndex: int = -1
        self._loading: bool = False
        self._query_filter: Optional[ClusterQueryFilter] = None

        # Paged retrieval / sliding window state
        self._page_limit: int = self._config.get_int(
            "eps:retrieval_limit_default",
            500,
        )
        self._loaded_pages: Deque[_LoadedPage] = deque()
        self._window_start: int = 0
        self._max_window_pages: int = 3
        self._has_more_forward: bool = True
        self._has_more_backward: bool = False
        self._forward_fetch_id: Optional[int] = None
        self._backward_fetch_id: Optional[int] = None
        self._next_forward_fetch_id: int = 1
        self._next_backward_fetch_id: int = 1

        # Thumbnail loader config
        self._eviction_distance: int = self._config.get_int(
            "gui:historical:eviction_distance",
            30,
        )
        self._scroll_prefetch_buffer: int = self._config.get_int(
            "gui:historical:scroll_prefetch_buffer",
            30,
        )

        # Threading
        self._load_thread: Optional[threading.Thread] = None
        self._logger = logging.getLogger(__name__)
        self._state_lock = threading.RLock()
        self._next_request_id: int = 1
        self._active_request_id: Optional[int] = None

        # Callbacks
        self._on_events_loaded_callbacks: List[Callable[[List[Cluster]], None]] = []
        self._on_error_callbacks: List[Callable[[str], None]] = []
        self._on_events_changed_callbacks: List[Callable[[], None]] = []
        self._on_events_appended_callbacks: List[Callable[[List[Cluster]], None]] = []
        self._on_events_prepended_callbacks: List[Callable[[List[Cluster]], None]] = []
        self._on_events_evicted_callbacks: List[Callable[[int, int], None]] = []
        self._on_selected_event_changed_callbacks: List[Callable[[], None]] = []
        self._on_loading_changed_callbacks: List[Callable[[bool], None]] = []
        self._on_load_error_callbacks: List[Callable[[str], None]] = []
        self._on_thumbnail_ready_callbacks: List[Callable[[int, np.ndarray], None]] = []
    # --- Properties ---

    @property
    def events(self) -> List[Cluster]:
        """List of currently-resident cluster events (the sliding window)."""
        return self._events

    @property
    def selectedIndex(self) -> int:
        """Global index of the selected event, or -1 if none."""
        return self._selectedIndex

    @property
    def selectedEvent(self) -> Optional[Cluster]:
        """The currently selected Cluster, or None.

        Returns None if the selected global index has scrolled
        outside the currently-resident window (evicted) — this
        deselects rather than raising.
        """
        local = self._selectedIndex - self._window_start
        if self._selectedIndex >= 0 and 0 <= local < len(self._events):
            return self._events[local]
        return None

    @property
    def isLoading(self) -> bool:
        """True while events are being fetched."""
        return self._loading

    @property
    def physicsManager(self) -> PhysicsConversionManager:
        """The physics conversion manager for ADU/keV display."""
        return self._physics

    @property
    def repository(self):
        """Exposes the underlying EventRepository.

        Used by HistoricalExportViewModel (#56) so the export pipeline
        can query clusters without re-plumbing the repository through
        another constructor.
        """
        return self._repository

    @property
    def thumbnail_service(self) -> ThumbnailLoaderService:
        """The thumbnail loader used to fetch raw cluster pixel data from FITS."""
        return self._thumbnail_service

    @property
    def classificationThreshold(self) -> float:
        """Classification confidence threshold from configuration."""
        return self._config.get_float(
            "gui:historical:classification_threshold",
            0.75,
        )

    @property
    def thumbnailColormap(self) -> Colormap:
        """Colormap used for cluster thumbnails and inspector images."""
        colormap_str = str(self._config.get(
            "gui:historical:thumbnail_colormap", "viridis"
        ))
        return Colormap(colormap_str)

    @property
    def displayEnergyInKev(self) -> bool:
        """Whether cluster energy should be displayed in keV."""
        return self._config.get_bool(
            "gui:raw_analysis:display_energy_in_kev",
            True,
        )

    # --- Commands ---

    def setQueryFilter(self, query_filter: Optional[ClusterQueryFilter]) -> None:
        """Sets filter criteria for the next ``loadEvents`` call.

        Args:
            query_filter: Filter to apply, or ``None`` to clear.
        """
        self._query_filter = query_filter

    def prefetch_thumbnails(self, count: int) -> None:
        """Pre-fetch the first *count* thumbnails without waiting for scroll."""
        last = min(count, len(self._events)) - 1
        if last >= 0:
            self.request_thumbnails_for_range(
                self._window_start, self._window_start + last,
            )

    def request_thumbnails_for_range(
        self,
        first: int,
        last: int,
    ) -> None:
        """Request thumbnails for visible global indices plus a look-ahead buffer.

        Args:
            first: First visible global index.
            last: Last visible global index.
        """
        buf = self._scroll_prefetch_buffer
        window_end = self._window_start + len(self._events)
        req_first = max(self._window_start, first - buf)
        req_last = min(window_end - 1, last + buf)
        for g in range(req_first, req_last + 1):
            local = g - self._window_start
            if 0 <= local < len(self._events):
                self._thumbnail_service.request_thumbnail(
                    g,
                    self._events[local],
                    self._on_thumbnail_loaded,
                )
        keep: Set[int] = set(
            range(
                max(self._window_start, first - self._eviction_distance),
                min(window_end, last + self._eviction_distance + 1),
            )
        )
        self._thumbnail_service.evict(keep)

    def request_next_page_if_needed(self, first: int, last: int) -> None:
        """Triggers a forward page fetch when scrolling nears the window's tail.

        Args:
            first: First visible global index.
            last: Last visible global index.
        """
        with self._state_lock:
            if not self._has_more_forward or self._forward_fetch_id is not None or self._loading:
                return
            window_end = self._window_start + len(self._events)
            if last < window_end - self._scroll_prefetch_buffer:
                return
            fetch_id = self._next_forward_fetch_id
            self._next_forward_fetch_id += 1
            self._forward_fetch_id = fetch_id
            query_filter = self._query_filter
            offset = window_end
            limit = self._page_limit

        self._repository.fetch_clusters(
            query_filter,
            limit=limit,
            offset=offset,
            callback=lambda events: self._on_forward_page_loaded(fetch_id, offset, events),
            on_error=lambda error: self._on_forward_page_error(fetch_id, error),
        )

    def request_previous_page_if_needed(self, first: int, last: int) -> None:
        """Triggers a backward page fetch when scrolling nears the window's head.

        Args:
            first: First visible global index.
            last: Last visible global index.
        """
        with self._state_lock:
            if not self._has_more_backward or self._backward_fetch_id is not None or self._loading:
                return
            if first > self._window_start + self._scroll_prefetch_buffer:
                return
            page_limit = self._page_limit
            offset = max(0, self._window_start - page_limit)
            limit = min(page_limit, self._window_start)
            if limit <= 0:
                self._has_more_backward = False
                return
            fetch_id = self._next_backward_fetch_id
            self._next_backward_fetch_id += 1
            self._backward_fetch_id = fetch_id
            query_filter = self._query_filter

        self._repository.fetch_clusters(
            query_filter,
            limit=limit,
            offset=offset,
            callback=lambda events: self._on_backward_page_loaded(fetch_id, offset, events),
            on_error=lambda error: self._on_backward_page_error(fetch_id, error),
        )

    def request_selected_cluster_data(
        self,
        on_ready: Callable[[Optional[np.ndarray]], None],
    ) -> None:
        """Request raw pixel data for the currently selected cluster."""
        cluster = self.selectedEvent
        if cluster is None:
            on_ready(None)
            return
        self._thumbnail_service.request_cluster_data(cluster, on_ready)

    def add_thumbnail_ready_callback(
        self,
        callback: Callable[[int, np.ndarray], None],
    ) -> None:
        """Registers a callback for when a thumbnail finishes loading."""
        self._on_thumbnail_ready_callbacks.append(callback)

    def _on_thumbnail_loaded(
        self,
        key: int,
        thumbnail: np.ndarray,
    ) -> None:
        """Internal callback passed to service; fans out to registered observers."""
        for cb in self._on_thumbnail_ready_callbacks:
            cb(key, thumbnail)

    def loadEvents(self) -> None:
        """Starts an asynchronous background fetch from the repository.

        No-op if a load is already in flight. Sets loading state
        synchronously on the calling thread, then spawns a daemon
        thread for the repository call. Observers are notified
        from the background thread — Views should marshal back to
        the main thread via ``Qt.AutoConnection``. Loads the first
        page only (bounded by ``eps:retrieval_limit_default``);
        further pages are fetched on demand as the user scrolls.
        """
        self._thumbnail_service.clear()
        with self._state_lock:
            if self._loading:
                return
            request_id = self._next_request_id
            self._next_request_id += 1
            self._active_request_id = request_id
            # Any in-flight page fetch is now stale — its eventual
            # completion will compare against a fetch_id that can
            # never match again.
            self._forward_fetch_id = None
            self._backward_fetch_id = None
            query_filter = self._query_filter
            loading_callbacks = list(self._on_loading_changed_callbacks)
            self._loading = True

        for callback in loading_callbacks:
            callback(True)

        self._repository.fetch_clusters(
            query_filter,
            limit=self._page_limit,
            offset=0,
            callback=lambda events: self._on_repository_loaded(request_id, events),
            on_error=lambda error: self._on_repository_error(request_id, error),
        )

    def selectEvent(self, index: int) -> None:
        """Selects an event by global index.

        Args:
            index: Global index into the backend's full cluster
                ordering, or -1 to clear the selection. An index
                outside the currently-resident window is treated as
                deselect.
        """
        if index != -1 and not (
            self._window_start <= index < self._window_start + len(self._events)
        ):
            index = -1
        if self._selectedIndex != index:
            self._selectedIndex = index
            self._notify_selected_event_changed()

    # --- Observer Pattern ---

    def add_event_loading_callback(
            self, callback: Callable[[List[Cluster]], None]
    ) -> None:
        """Registers a callback for when events are loaded."""
        self._on_events_loaded_callbacks.append(callback)

    def add_events_changed_callback(self, callback: Callable[[], None]) -> None:
        """Registers a callback for when the event list is fully reset."""
        self._on_events_changed_callbacks.append(callback)

    def add_events_appended_callback(
        self, callback: Callable[[List[Cluster]], None]
    ) -> None:
        """Registers a callback for events appended via forward paging.

        Unlike events-changed, this is not a full reset — observers
        should append the given chunk rather than rebuilding their
        view.
        """
        self._on_events_appended_callbacks.append(callback)

    def add_events_prepended_callback(
        self, callback: Callable[[List[Cluster]], None]
    ) -> None:
        """Registers a callback for events prepended via backward paging."""
        self._on_events_prepended_callbacks.append(callback)

    def add_events_evicted_callback(
        self, callback: Callable[[int, int], None]
    ) -> None:
        """Registers a callback for window eviction: (global_offset, count)."""
        self._on_events_evicted_callbacks.append(callback)

    def add_selected_event_changed_callback(self, callback: Callable[[], None]) -> None:
        """Registers a callback for selection changes."""
        self._on_selected_event_changed_callbacks.append(callback)

    def add_loading_changed_callback(self, callback: Callable[[bool], None]) -> None:
        """Registers a callback for loading state changes."""
        self._on_loading_changed_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[str], None]) -> None:
        """Registers a callback for error messages."""
        self._on_error_callbacks.append(callback)

    def add_load_error_callback(self, callback: Callable[[str], None]) -> None:
        """Registers a callback for errors during event loading."""
        self._on_load_error_callbacks.append(callback)

    # --- Private helpers ---

    def _safe_max_window_pages(self) -> int:
        """Returns the window's page cap, widened defensively if needed.

        Eviction is gated behind a successfully-completed full page
        fetch (page-sized granularity), not the scroll-trigger
        threshold (buffer-sized granularity) — at realistic configs
        these operate at very different scales, so jitter alone can't
        thrash fetch/evict. The latent risk is a misconfigured page
        size at or below twice the scroll buffer, which would let the
        two boundaries collide; widen the window rather than fail.
        """
        if self._page_limit <= 2 * self._scroll_prefetch_buffer:
            return max(self._max_window_pages, 5)
        return self._max_window_pages

    def _rebuild_events_cache(self) -> None:
        """Recomputes the flat events cache from resident pages.

        Must be called while holding ``self._state_lock``. Called only
        on page add/evict — infrequent (once per scroll-past-page-
        boundary event), not on every property read.
        """
        flat: List[Cluster] = []
        for page in self._loaded_pages:
            flat.extend(page.clusters)
        self._events = flat
        self._window_start = self._loaded_pages[0].offset if self._loaded_pages else 0

    def _on_repository_loaded(self, request_id: int, events: List[Cluster]) -> None:
        with self._state_lock:
            if self._active_request_id != request_id:
                return
            self._active_request_id = None
        self._notify_loaded(events)

    def _on_repository_error(self, request_id: int, error: str) -> None:
        with self._state_lock:
            if self._active_request_id != request_id:
                return
            self._active_request_id = None
        self._notify_error(error)

    def _on_forward_page_loaded(
        self, fetch_id: int, offset: int, events: List[Cluster],
    ) -> None:
        evicted: Optional[_LoadedPage] = None
        with self._state_lock:
            if self._forward_fetch_id != fetch_id:
                return
            self._forward_fetch_id = None
            self._has_more_forward = len(events) == self._page_limit
            if events:
                self._loaded_pages.append(_LoadedPage(offset=offset, clusters=events))
                if len(self._loaded_pages) > self._safe_max_window_pages():
                    evicted = self._loaded_pages.popleft()
                    self._has_more_backward = True
                self._rebuild_events_cache()
        if events:
            self._notify_events_appended(events)
            if evicted is not None:
                self._notify_events_evicted(evicted.offset, evicted.count)

    def _on_backward_page_loaded(
        self, fetch_id: int, offset: int, events: List[Cluster],
    ) -> None:
        evicted: Optional[_LoadedPage] = None
        with self._state_lock:
            if self._backward_fetch_id != fetch_id:
                return
            self._backward_fetch_id = None
            self._has_more_backward = offset > 0
            if events:
                self._loaded_pages.appendleft(_LoadedPage(offset=offset, clusters=events))
                if len(self._loaded_pages) > self._safe_max_window_pages():
                    evicted = self._loaded_pages.pop()
                    self._has_more_forward = True
                self._rebuild_events_cache()
        if events:
            self._notify_events_prepended(events)
            if evicted is not None:
                self._notify_events_evicted(evicted.offset, evicted.count)

    def _on_forward_page_error(self, fetch_id: int, error: str) -> None:
        with self._state_lock:
            if self._forward_fetch_id != fetch_id:
                return
            self._forward_fetch_id = None
        self._notify_page_error(error)

    def _on_backward_page_error(self, fetch_id: int, error: str) -> None:
        with self._state_lock:
            if self._backward_fetch_id != fetch_id:
                return
            self._backward_fetch_id = None
        self._notify_page_error(error)

    def _setLoading(self, loading: bool) -> None:
        with self._state_lock:
            if self._loading == loading:
                return
            self._loading = loading
        self._notify_loading_changed()

    def _notify_loaded(self, events: List[Cluster]) -> None:
        self._setLoading(False)
        with self._state_lock:
            self._loaded_pages = deque([_LoadedPage(offset=0, clusters=events)])
            self._rebuild_events_cache()
            self._has_more_forward = len(events) == self._page_limit
            self._has_more_backward = False
            if len(self._events) > 0:
                self._selectedIndex = 0
            else:
                self._selectedIndex = -1
            events_loaded_callbacks = list(self._on_events_loaded_callbacks)
        for callback in events_loaded_callbacks:
            callback(events)
        self._notify_events_changed()
        self._notify_selected_event_changed()

    def _notify_events_changed(self) -> None:
        with self._state_lock:
            callbacks = list(self._on_events_changed_callbacks)
        for callback in callbacks:
            callback()

    def _notify_events_appended(self, new_events: List[Cluster]) -> None:
        with self._state_lock:
            callbacks = list(self._on_events_appended_callbacks)
        for callback in callbacks:
            callback(new_events)

    def _notify_events_prepended(self, new_events: List[Cluster]) -> None:
        with self._state_lock:
            callbacks = list(self._on_events_prepended_callbacks)
        for callback in callbacks:
            callback(new_events)

    def _notify_events_evicted(self, offset: int, count: int) -> None:
        with self._state_lock:
            callbacks = list(self._on_events_evicted_callbacks)
        for callback in callbacks:
            callback(offset, count)

    def _notify_selected_event_changed(self) -> None:
        for callback in self._on_selected_event_changed_callbacks:
            callback()

    def _notify_loading_changed(self) -> None:
        with self._state_lock:
            callbacks = list(self._on_loading_changed_callbacks)
            loading = self._loading
        for callback in callbacks:
            callback(loading)

    def _notify_error(self, error: str) -> None:
        self._setLoading(False)
        self._notify_page_error(error)

    def _notify_page_error(self, error: str) -> None:
        """Surfaces an error without toggling ``isLoading``.

        Used by page-fetch failures: a failed forward/backward fetch
        leaves the grid populated and usable, so the global loading
        overlay must not flip. ``_notify_error`` (the full-reload
        failure path) calls this after clearing ``isLoading`` itself.
        """
        with self._state_lock:
            load_error_callbacks = list(self._on_load_error_callbacks)
            error_callbacks = list(self._on_error_callbacks)
        for callback in load_error_callbacks:
            callback(error)
        for callback in error_callbacks:
            callback(error)
