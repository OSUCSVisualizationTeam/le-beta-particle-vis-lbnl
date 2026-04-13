"""Pure-Python ViewModel for the Live Mode screensaver.

No Qt imports — safe for headless CI testing.  Manages a bounded
cluster queue fed by EventHandler subscriptions, exposes grid state
for the View, and handles fallback loading from the database.
"""

import collections
import logging
import threading
import time
from typing import Callable, Deque, List, Optional, Tuple

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.frontend.fitsconverters.interface import Colormap

logger = logging.getLogger(__name__)

_EVENT_NAME = "cluster.classified"
_MIN_GRID_COUNT = 20
_MAX_GRID_COUNT = 2000


class LiveModeViewModel:
    """ViewModel for the Live Mode screensaver feature.

    Subscribes to ``EventHandler`` for ``cluster.classified`` events,
    maintains a bounded deque of incoming ``Cluster`` objects, and
    exposes a data model for the snake-grid.  Pure Python — no Qt.

    Args:
        config: Application configuration service.
        eventHandler: The pub/sub event handler to subscribe to.
        repository: Event repository for fallback data loading.
        physics: Physics conversion manager for ADU-to-keV.
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
        self._event_handler = eventHandler
        self._repository = repository
        self._physics = physics
        self._thumbnail_service = thumbnailService
        self._lock = threading.Lock()

        rows, cols = self._validated_grid_shape()
        self._rows = rows
        self._cols = cols
        self._capacity = rows * cols

        self._incoming: Deque[Cluster] = collections.deque(
            maxlen=self._capacity * 2,
        )
        self._grid: List[Optional[Cluster]] = [None] * self._capacity
        self._featured: Optional[Cluster] = None
        self._featured_set_at: float = 0.0

        self._on_grid_changed: List[Callable[[], None]] = []
        self._on_featured_changed: List[Callable[[Optional[Cluster]], None]] = []

        self._callback_id: Optional[str] = None
        self._active = False

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
    def featured_size(self) -> int:
        """Featured cluster image size in pixels."""
        return self._config.get_int(
            "gui:livemode:featured_size_px",
            320,
            minimum=64,
        )

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
            400,
            minimum=50,
            maximum=1000,
        )

    @property
    def fallback_timeout_s(self) -> int:
        """Seconds before triggering fallback data load."""
        return self._config.get_int(
            "gui:livemode:fallback_timeout_s",
            60,
            minimum=5,
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
        with self._lock:
            return list(self._grid)

    @property
    def featured(self) -> Optional[Cluster]:
        """The currently featured (zoomed) cluster."""
        return self._featured

    @property
    def physics(self) -> PhysicsConversionManager:
        """The physics conversion manager."""
        return self._physics

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
    def featured_hold_s(self) -> int:
        """Minimum seconds the featured cluster is held before replacement."""
        return self._config.get_int(
            "gui:livemode:featured_hold_s",
            5,
            minimum=3,
            maximum=10,
        )

    # --- Lifecycle ---

    def activate(self) -> None:
        """Subscribe to EventHandler and start accepting events.

        Safe to call multiple times — no-op if already active.
        """
        if self._active:
            return
        self._active = True
        self._callback_id = self._event_handler.register_callback(
            _EVENT_NAME,
            self._on_cluster_event,
        )
        logger.info("LiveModeViewModel activated, subscribed to %s", _EVENT_NAME)

    def deactivate(self) -> None:
        """Unsubscribe from EventHandler and stop accepting events.

        Safe to call when not active.
        """
        if not self._active:
            return
        self._active = False
        if self._callback_id is not None:
            self._event_handler.unregister(self._callback_id)
            self._callback_id = None
        logger.info("LiveModeViewModel deactivated")

    # --- Grid advancement ---

    def advance(self) -> int:
        """Advance the grid by draining all available incoming clusters.

        Pops up to ``_capacity`` items from the incoming deque and
        shifts the grid by that many positions.  When no items are
        queued but the grid still has content, shifts by one with a
        ``None`` sentinel so the grid slowly empties during idle
        periods.

        Returns:
            Number of positions shifted (0 means nothing changed).
        """
        with self._lock:
            batch = self._drain_incoming()
            if not batch:
                if all(c is None for c in self._grid):
                    return 0
                self._grid = self._grid[1:] + [None]
                shift_count = 1
            else:
                shift_count = len(batch)
                self._grid = self._grid[shift_count:] + batch
        self._notify_grid_changed()
        return shift_count

    def _drain_incoming(self) -> List[Optional[Cluster]]:
        """Drain all available clusters from the incoming deque.

        Must be called under ``self._lock``.

        Returns:
            List of clusters drained (may be empty).
        """
        batch: List[Optional[Cluster]] = []
        while self._incoming and len(batch) < self._capacity:
            batch.append(self._incoming.popleft())
        return batch

    # --- Fallback ---

    def trigger_fallback(self) -> None:
        """Loads clusters from the database in a background thread.

        Called by the View's idle timer when no live events arrive
        within ``fallback_timeout_s``.
        """
        thread = threading.Thread(
            target=self._fallback_worker,
            daemon=True,
        )
        thread.start()

    def _fallback_worker(self) -> None:
        """Background fetch from EventRepository for fallback data.

        Fills the grid from index 0 forward so the screensaver
        populates from the top-left corner.  Clusters beyond grid
        capacity are queued in ``_incoming`` for normal advance flow.
        """
        try:
            clusters = self._repository.fetch_events()
            if not clusters:
                return
            with self._lock:
                filled = self._fill_grid_from_front(clusters)
                for c in clusters[filled:]:
                    self._incoming.append(c)
                self._featured = clusters[0]
                self._featured_set_at = time.monotonic()
            self._notify_featured_changed(clusters[0])
            self._notify_grid_changed()
            logger.info("Fallback loaded %d clusters", len(clusters))
        except Exception:
            logger.exception("Fallback data load failed")

    def _fill_grid_from_front(self, clusters: List[Cluster]) -> int:
        """Fill None slots in ``_grid`` from index 0.

        Must be called under ``self._lock``.

        Returns:
            Number of clusters consumed from the list.
        """
        used = 0
        for i in range(self._capacity):
            if used >= len(clusters):
                break
            if self._grid[i] is None:
                self._grid[i] = clusters[used]
                used += 1
        return used

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

    # --- EventHandler callback (bg thread) ---

    def _on_cluster_event(self, envelope: EventEnvelope) -> None:
        """Receives cluster.classified from EventHandler worker.

        If the hold period for the current featured cluster has elapsed,
        the new cluster becomes featured and is NOT queued for the grid.
        Otherwise the cluster is queued normally and the featured panel
        stays unchanged.
        """
        try:
            cluster = self._cluster_from_payload(envelope.payload)
            now = time.monotonic()
            with self._lock:
                elapsed = now - self._featured_set_at
                if elapsed >= self.featured_hold_s:
                    self._featured = cluster
                    self._featured_set_at = now
                    notify_featured = True
                else:
                    self._incoming.append(cluster)
                    notify_featured = False
            if notify_featured:
                self._notify_featured_changed(cluster)
            self._notify_grid_changed()
        except Exception:
            logger.exception("Error processing cluster.classified event")

    def _cluster_from_payload(self, payload: dict) -> Cluster:
        """Reconstructs a Cluster from an EventEnvelope payload.

        Synthesises a Gaussian blob from sigmaX/sigmaY since the
        payload does not carry raw ndarray data.
        """
        sx = float(payload.get("sigmaX", 1.5))
        sy = float(payload.get("sigmaY", 1.5))
        w = max(6, int(sx * 4 + 2))
        h = max(6, int(sy * 4 + 2))
        cx, cy = w // 2, h // 2
        energy = float(payload.get("total_energy", 1000.0))
        blob = self._gaussian_blob(w, h, cx, cy, sx, sy, energy)

        return Cluster(
            boundingBox=BoundingBox(top=0, left=0, bottom=h, right=w),
            data=blob,
            centerX=cx,
            centerY=cy,
            sigmaX=sx,
            sigmaY=sy,
            energy=energy,
            pixelCount=max(1, w * h // 4),
            fitsId=payload.get("fits_id"),
            clusterId=payload.get("cluster_id"),
            cnnClassification=float(
                payload.get("cnn_classification", 0.0),
            ),
            nrgClassification=float(
                payload.get("nrg_classification", 0.0),
            ),
            bdtClassification=float(
                payload.get("bdt_classification", 0.0),
            ),
            classification=str(
                payload.get("classification", "UNCLASSIFIED"),
            ),
        )

    # --- Private helpers ---

    @staticmethod
    def _gaussian_blob(
        w: int,
        h: int,
        cx: int,
        cy: int,
        sx: float,
        sy: float,
        energy: float,
    ) -> np.ndarray:
        """Generates a 2D Gaussian blob for thumbnail rendering."""
        y = np.arange(h)
        x = np.arange(w)
        xx, yy = np.meshgrid(x, y)
        pixel_count = max(1, w * h // 4)
        amplitude = energy / pixel_count
        blob = amplitude * np.exp(
            -(
                ((xx - cx) ** 2) / (2 * max(sx, 0.5) ** 2)
                + ((yy - cy) ** 2) / (2 * max(sy, 0.5) ** 2)
            )
        )
        return blob.astype(np.float32)

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

    def _notify_grid_changed(self) -> None:
        for cb in self._on_grid_changed:
            cb()

    def _notify_featured_changed(
        self,
        cluster: Optional[Cluster],
    ) -> None:
        for cb in self._on_featured_changed:
            cb(cluster)
