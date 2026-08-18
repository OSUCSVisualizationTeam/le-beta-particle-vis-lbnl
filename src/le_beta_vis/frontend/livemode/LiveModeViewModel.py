"""Pure-Python ViewModel for the Live Mode screensaver.

No Qt imports — safe for headless CI testing.  Manages a unified
``IncomingDataQueue`` fed by a ``FreshClusterProvider`` (live
events) and a ``FallbackClusterProvider`` (EPS historical query).
Exposes grid state for the View and handles featured cluster
rotation via a deterministic one-per-tick dequeue.
"""

import logging
import threading
from functools import partial
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.frontend.fitsconverters.interface import Colormap

from .FallbackClusterProvider import FallbackClusterProvider
from .FreshClusterProvider import FreshClusterProvider
from .IncomingDataQueue import IncomingDataQueue

logger = logging.getLogger(__name__)

_MIN_GRID_COUNT = 20
_MAX_GRID_COUNT = 2000


class LiveModeViewModel:
    """ViewModel for the Live Mode screensaver feature.

    Maintains a unified ``IncomingDataQueue`` that always tries to
    stay full.  On each advance tick the front cluster is dequeued
    for the featured panel, fresh live-event clusters are inserted
    at the partition pointer, and any remaining empty slots are
    backfilled from the EPS in a background thread.

    Args:
        config: Application configuration service.
        eventHandler: The pub/sub event handler to subscribe to.
        repository: Event repository for fallback data loading.
        physics: Physics conversion manager for ADU-to-keV.
        thumbnailService: Optional service for FITS pixel data
            extraction.
    """

    def __init__(
        self,
        config: ConfigurationService,
        eventHandler: EventHandlerInterface,
        repository: EventRepository,
        physics: PhysicsConversionManager,
        thumbnailService: Optional[ThumbnailLoaderService] = None,
    ) -> None:
        self._config = config
        self._physics = physics
        self._thumbnail_service = thumbnailService

        rows, cols = self._validated_grid_shape()
        self._rows = rows
        self._cols = cols
        self._capacity = rows * cols

        self._queue = IncomingDataQueue(self._capacity)
        self._fresh_provider = FreshClusterProvider(eventHandler)
        self._fallback_provider = FallbackClusterProvider(repository)

        self._refill_in_progress = False
        self._refill_lock = threading.Lock()

        self._on_grid_changed: List[Callable[[], None]] = []
        self._on_featured_changed: List[
            Callable[[Optional[Cluster]], None]
        ] = []
        self._hdu_frame_callbacks: List[
            Callable[[Optional[np.ndarray], Optional[BoundingBox]], None]
        ] = []
        self._hdu_cache: Optional[Tuple[str, int, np.ndarray]] = None

        self._paused: bool = False
        self._pinned_cluster: Optional[Cluster] = None
        self._on_paused_changed: List[Callable[[bool], None]] = []
        self._on_pinned_changed: List[Callable[[Optional[Cluster]], None]] = []

        self.pending_cluster_for_historical: Optional[Cluster] = None
        self.pending_save_cluster: Optional[Cluster] = None
        self.pending_save_path: Optional[Path] = None

        self._active = False
        self._generation = 0

    # --- Properties (config-driven) ---

    @property
    def colormap(self) -> Colormap:
        """Colormap for all screensaver thumbnails."""
        val = str(self._config.get("gui:livemode:colormap", "inferno"))
        try:
            return Colormap(val)
        except ValueError:
            return Colormap.INFERNO

    @property
    def advance_interval_ms(self) -> int:
        """Milliseconds between grid advance steps."""
        return self._config.get_int(
            "gui:livemode:advance_interval_ms",
            3000,
            minimum=500,
        )

    @property
    def animation_duration_ms(self) -> int:
        """Displacement animation duration, capped at 1000 ms."""
        return self._config.get_int(
            "gui:livemode:animation_duration_ms",
            250,
            minimum=50,
            maximum=1000,
        )

    @property
    def grid_spacing(self) -> int:
        """Pixel spacing between grid cells. Minimum 6 pixels."""
        return self._config.get_int(
            "gui:livemode:grid_spacing_px",
            6,
            minimum=6,
        )

    @property
    def grid_shape(self) -> Tuple[int, int]:
        """(rows, cols) of the thumbnail grid."""
        return (self._rows, self._cols)

    @property
    def grid(self) -> List[Optional[Cluster]]:
        """Snapshot of current grid state (length = rows * cols)."""
        return self._queue.snapshot()

    @property
    def physics(self) -> PhysicsConversionManager:
        """The physics conversion manager."""
        return self._physics

    @property
    def badges_classifiers_enabled(self) -> bool:
        """Gate for the symbol + confidence badges on the grid."""
        return self._config.get_bool(
            "gui:livemode:badges:classifiers_enabled", True,
        )

    @property
    def badges_min_cell_size_px(self) -> int:
        """Minimum rendered cell side at which badges are drawn."""
        return self._config.get_int(
            "gui:livemode:badges:min_cell_size_px", 48, minimum=1,
        )

    @property
    def left_panel_width_pct(self) -> float:
        """Left panel width as fraction of screen width."""
        return self._config.get_float(
            "gui:livemode:left_panel_width_pct",
            0.25,
            minimum=0.1,
            maximum=0.5,
        )

    @property
    def histogram_min_height_pct(self) -> float:
        """Histogram minimum height as fraction of screen height."""
        return self._config.get_float(
            "gui:livemode:histogram_min_height_pct",
            0.10,
            minimum=0.05,
            maximum=0.5,
        )

    @property
    def controls_enabled(self) -> bool:
        """Whether the control strip overlay is shown."""
        return self._config.get_bool("gui:livemode:controls:enabled", True)

    @property
    def controls_autohide_ms(self) -> int:
        """Milliseconds of inactivity before control strip auto-hides."""
        return self._config.get_int("gui:livemode:controls:autohide_ms", 3000, minimum=500)

    @property
    def controls_background_opacity(self) -> float:
        """Alpha (0.0–1.0) for the control strip background."""
        return self._config.get_float(
            "gui:livemode:controls:background_opacity", 0.80, minimum=0.0, maximum=1.0,
        )

    @property
    def controls_icon_size_pct(self) -> float:
        """Control strip icon size as a percentage of screen height."""
        return self._config.get_float(
            "gui:livemode:controls:icon_size_pct", 3.0, minimum=0.1,
        )

    # --- Pause / pin state ---

    @property
    def paused(self) -> bool:
        """True when the advance timer and animations are frozen."""
        return self._paused

    @property
    def pinned_cluster(self) -> Optional[Cluster]:
        """The currently pinned cluster, or None if not pinned."""
        return self._pinned_cluster

    def toggle_paused(self) -> None:
        """Toggle the paused state.

        When unpausing, pin is also cleared so the featured rotation
        resumes on a clean slate.
        """
        self._paused = not self._paused
        if not self._paused and self._pinned_cluster is not None:
            self._pinned_cluster = None
            self._notify_pinned_changed()
        self._notify_paused_changed()

    def pin_cluster(self, cluster: Cluster) -> None:
        """Pin *cluster* as the locked featured cluster.

        Args:
            cluster: The cluster to hold in the featured position.
        """
        self._pinned_cluster = cluster
        self._notify_pinned_changed()

    def unpin(self) -> None:
        """Release the pinned cluster and return to free rotation."""
        if self._pinned_cluster is not None:
            self._pinned_cluster = None
            self._notify_pinned_changed()

    def request_open_in_historical(self, cluster: Cluster) -> None:
        """Store intent to navigate to *cluster* in the Historical view.

        The caller (View) must dismiss Live Mode immediately after this
        call.  MainWindow reads ``pending_cluster_for_historical`` after
        ``dialog.exec()`` returns.

        Args:
            cluster: The cluster to inspect in the Historical view.
        """
        self.pending_cluster_for_historical = cluster
        self._pinned_cluster = None
        self._notify_pinned_changed()

    def request_save_frame(self, cluster: Cluster, path: Path) -> None:
        """Store intent to export the current frame after Live Mode closes.

        The caller (View) must dismiss Live Mode immediately after this
        call.  MainWindow reads ``pending_save_cluster`` and
        ``pending_save_path`` after ``dialog.exec()`` returns.

        Args:
            cluster: Representative cluster identifying the FITS frame.
            path: Destination file path chosen by the user.
        """
        self.pending_save_cluster = cluster
        self.pending_save_path = path

    def add_paused_changed_callback(self, cb: Callable[[bool], None]) -> None:
        """Register callback fired when paused state changes."""
        self._on_paused_changed.append(cb)

    def add_pinned_changed_callback(
        self, cb: Callable[[Optional[Cluster]], None],
    ) -> None:
        """Register callback fired when pinned cluster changes."""
        self._on_pinned_changed.append(cb)

    # --- Lifecycle ---

    def activate(self) -> None:
        """Subscribe to EventHandler and schedule initial queue fill.

        Safe to call multiple times — no-op if already active.
        """
        if self._active:
            return
        self._active = True
        self._fresh_provider.activate()
        self._schedule_refill(self._capacity)
        logger.info("LiveModeViewModel activated")

    def deactivate(self) -> None:
        """Unsubscribe from EventHandler and stop accepting events.

        Invalidates any outstanding background work so its completion
        cannot notify the View after Live Mode has been left: bumps
        ``_generation`` (silences a late ``_refill_worker`` completion) and
        clears the shared ``ThumbnailLoaderService`` (silences late
        ``request_cluster_data``/``request_hdu_frame`` deliveries via its
        own generation gate).

        Safe to call when not active.
        """
        if not self._active:
            return
        self._active = False
        self._generation += 1
        self._fresh_provider.deactivate()
        if self._thumbnail_service is not None:
            self._thumbnail_service.clear()
        logger.info("LiveModeViewModel deactivated")

    # --- Grid advancement ---

    def advance(self) -> int:
        """Dequeue front cluster as featured, refill, and shift grid.

        On each tick:
          1. Dequeue the front of the queue as the new featured.
          2. If nothing was dequeued and queue is completely empty,
             return 0.
          3. Fire the featured-changed callback.
          4. Drain all available fresh clusters from the live
             provider and insert them at the partition pointer.
          5. Trigger async pixel-data loading for fresh clusters.
          6. If empty slots remain, schedule a background refill
             from the fallback provider.

        Returns:
            1 if the grid advanced (a cluster became featured),
            0 if paused or the queue was entirely empty.
        """
        if self._paused:
            return 0

        featured = self._queue.dequeue_front()

        if featured is None and self._queue.slots_needed() == self._capacity:
            return 0

        if featured is not None:
            self._notify_featured_changed(featured)

        self._insert_fresh_clusters()
        self._request_data_for_pending()
        self._maybe_schedule_refill()

        return 1 if featured is not None else 0

    # --- Cluster data extraction ---

    def request_cluster_data(
        self,
        cluster: Cluster,
        on_ready: Callable[[Optional[np.ndarray]], None],
    ) -> None:
        """Load raw pixel data for a cluster asynchronously.

        Delegates to the injected ``ThumbnailLoaderService`` which
        handles FITS extraction with HDU caching.  Falls back to
        ``on_ready(None)`` when no service is available.

        Args:
            cluster: The cluster whose pixel data is needed.
            on_ready: Callback invoked with the data array or None.
        """
        if self._thumbnail_service is not None:
            self._thumbnail_service.request_cluster_data(cluster, on_ready)
        else:
            on_ready(None)

    # --- Observer registration ---

    def add_grid_changed_callback(
        self,
        cb: Callable[[], None],
    ) -> None:
        """Register callback fired whenever grid state changes."""
        self._on_grid_changed.append(cb)

    def add_featured_changed_callback(
        self,
        cb: Callable[[Optional[Cluster]], None],
    ) -> None:
        """Register callback fired when featured cluster changes."""
        self._on_featured_changed.append(cb)

    def add_hdu_frame_ready_callback(
        self,
        cb: Callable[[Optional[np.ndarray], Optional[BoundingBox]], None],
    ) -> None:
        """Register callback fired when an HDU frame finishes loading.

        The callback fires from the ThumbnailLoaderService worker thread.
        Views must use the Signal.emit pattern to marshal onto the main
        thread.

        Args:
            cb: Receives (frame_array, bounding_box) or (None, None).
        """
        self._hdu_frame_callbacks.append(cb)

    def remove_hdu_frame_ready_callback(
        self,
        cb: Callable[[Optional[np.ndarray], Optional[BoundingBox]], None],
    ) -> None:
        """Unregister a previously registered HDU frame callback.

        Args:
            cb: The callback to remove.
        """
        try:
            self._hdu_frame_callbacks.remove(cb)
        except ValueError:
            pass

    def load_hdu_for_cluster(self, cluster: Cluster) -> None:
        """Load the parent HDU frame for *cluster* asynchronously.

        Checks a single-entry cache keyed on (fitsFilename, hdu_id).
        A cache hit fires callbacks immediately on the calling thread.
        A cache miss delegates to ThumbnailLoaderService and fires
        callbacks from its worker thread.

        Args:
            cluster: The cluster whose parent HDU frame is needed.
        """
        if cluster.fitsFilename is None or cluster.hdu_id is None:
            self._notify_hdu_frame_ready(None, None)
            return

        filename = cluster.fitsFilename
        hdu_id = cluster.hdu_id
        bbox = cluster.boundingBox

        if (
            self._hdu_cache is not None
            and self._hdu_cache[0] == filename
            and self._hdu_cache[1] == hdu_id
        ):
            self._notify_hdu_frame_ready(self._hdu_cache[2], bbox)
            return

        if self._thumbnail_service is None:
            self._notify_hdu_frame_ready(None, None)
            return

        def _on_frame_loaded(frame: Optional[np.ndarray]) -> None:
            if frame is not None:
                self._hdu_cache = (filename, hdu_id, frame)
            self._notify_hdu_frame_ready(frame, bbox)

        self._thumbnail_service.request_hdu_frame(filename, hdu_id, _on_frame_loaded)

    # --- Private: advance helpers ---

    def _insert_fresh_clusters(self) -> None:
        """Drain all available fresh clusters into the queue."""
        fresh = self._fresh_provider.fetch(self._capacity)
        if fresh:
            self._queue.insert_fresh(fresh)

    def _request_data_for_pending(self) -> None:
        """Trigger async FITS data loading for queued clusters.

        Iterates the current queue snapshot and requests pixel data
        for any cluster with ``data is None`` that has not yet been
        requested.
        """
        if self._thumbnail_service is None:
            return
        for cluster in self._queue.snapshot():
            if cluster is not None and cluster.data is None:
                self._thumbnail_service.request_cluster_data(
                    cluster,
                    partial(self._on_cluster_data_loaded, cluster),
                )

    def _on_cluster_data_loaded(
        self,
        cluster: Cluster,
        data: Optional[np.ndarray],
    ) -> None:
        """Callback from ThumbnailLoaderService (background thread).

        Sets the cluster's pixel data and notifies the View so it
        can re-render the affected grid cell.
        """
        if data is not None:
            cluster.data = data
            self._notify_grid_changed()

    def _maybe_schedule_refill(self) -> None:
        """Schedule a background refill if the queue has empty slots."""
        needed = self._queue.slots_needed()
        if needed > 0:
            self._schedule_refill(needed)

    # --- Private: fallback refill ---

    def _schedule_refill(self, needed: int) -> None:
        """Spawn a daemon thread to backfill empty queue slots.

        Only one refill can be in flight at a time.  The ``+1``
        on the fetch count absorbs the race where
        ``dequeue_front()`` runs on the main thread between the
        ``slots_needed()`` call and the daemon's
        ``append_fallback()``.

        Args:
            needed: Number of empty slots at the time of the call.
        """
        with self._refill_lock:
            if self._refill_in_progress:
                return
            self._refill_in_progress = True

        thread = threading.Thread(
            target=self._refill_worker,
            args=(needed + 1, self._generation),
            daemon=True,
        )
        thread.start()

    def _refill_worker(
        self, count: int, generation: Optional[int] = None,
    ) -> None:
        """Background thread: fetch fallback clusters and append.

        Fetches ``count`` clusters from the fallback provider and
        writes them into the queue's fallback section.

        Args:
            count: Number of clusters to request from the fallback
                provider.
            generation: The ``_generation`` value at schedule time.
                ``deactivate()`` bumps ``_generation``, so a mismatch here
                means Live Mode was left while this fetch was in flight —
                the result is discarded and the View is not notified.
                ``None`` (the default, used when called directly rather
                than via ``_schedule_refill``) always passes the check.
        """
        try:
            clusters = self._fallback_provider.fetch(count)
            if clusters and (
                generation is None or generation == self._generation
            ):
                self._queue.append_fallback(clusters)
                self._notify_grid_changed()
                logger.info(
                    "Refill loaded %d fallback clusters",
                    len(clusters),
                )
        except Exception:
            logger.exception("LiveModeViewModel: refill worker failed")
        finally:
            with self._refill_lock:
                self._refill_in_progress = False

    # --- Private: configuration ---

    def _validated_grid_shape(self) -> Tuple[int, int]:
        """Reads and validates grid rows/cols from configuration."""
        rows = self._config.get_int(
            "gui:livemode:grid_rows",
            25,
            minimum=1,
        )
        cols = self._config.get_int(
            "gui:livemode:grid_columns",
            40,
            minimum=1,
        )
        total = rows * cols
        if total < _MIN_GRID_COUNT:
            cols = max(cols, _MIN_GRID_COUNT // max(rows, 1))
            rows = max(rows, _MIN_GRID_COUNT // max(cols, 1))
            logger.warning(
                "Grid count %d < %d, adjusted to %dx%d",
                total,
                _MIN_GRID_COUNT,
                rows,
                cols,
            )
        elif total > _MAX_GRID_COUNT:
            cols = min(cols, _MAX_GRID_COUNT // max(rows, 1))
            logger.warning(
                "Grid count %d > %d, adjusted to %dx%d",
                total,
                _MAX_GRID_COUNT,
                rows,
                cols,
            )
        return (rows, cols)

    # --- Private: notification ---

    def _notify_grid_changed(self) -> None:
        for cb in self._on_grid_changed:
            cb()

    def _notify_featured_changed(
        self,
        cluster: Optional[Cluster],
    ) -> None:
        for cb in self._on_featured_changed:
            cb(cluster)

    def _notify_hdu_frame_ready(
        self,
        frame: Optional[np.ndarray],
        bbox: Optional[BoundingBox],
    ) -> None:
        for cb in self._hdu_frame_callbacks:
            cb(frame, bbox)

    def _notify_paused_changed(self) -> None:
        for cb in self._on_paused_changed:
            cb(self._paused)

    def _notify_pinned_changed(self) -> None:
        for cb in self._on_pinned_changed:
            cb(self._pinned_cluster)
