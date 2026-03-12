import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import numpy as np

from .CCDCaptureModel import CCDCaptureModel
from .Cluster import Cluster
from .ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.frontend.fitsconverters.cluster_thumbnail import (
    generate_cluster_thumbnail,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap

logger = logging.getLogger(__name__)


class LazyThumbnailLoadingService(ThumbnailLoaderService):
    """Generates cluster thumbnails on background threads.

    Caches rendered thumbnails and the loaded FITS HDU arrays to
    amortise repeated file I/O across clusters that share a FITS
    file.  An idle timer releases the HDU cache after a configurable
    period of inactivity.
    """

    def __init__(
        self,
        max_workers: int = 2,
        colormap: Optional[Colormap] = None,
        fits_cache_idle_seconds: int = 60,
    ) -> None:
        self._max_workers = max(2, max_workers)
        self._colormap = colormap
        self._fits_cache_idle_seconds = max(60, fits_cache_idle_seconds)

        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._lock = threading.Lock()

        # Thumbnail cache
        self._cache: Dict[int, np.ndarray] = {}
        self._in_flight: Set[int] = set()
        self._futures: Dict[int, Future] = {}
        self._generation: int = 0

        # FITS HDU cache
        self._cached_fits_filename: Optional[str] = None
        self._cached_hdus: Optional[List[CCDCaptureModel]] = None
        self._idle_timer: Optional[threading.Timer] = None

    # ------------------------------------------------------------------
    # ThumbnailLoaderService interface
    # ------------------------------------------------------------------

    def request_thumbnail(
        self,
        key: int,
        cluster: Cluster,
        on_ready: Callable[[int, np.ndarray], None],
    ) -> None:
        """Request asynchronous thumbnail generation for *cluster*."""
        with self._lock:
            if key in self._cache:
                cached = self._cache[key]
                on_ready(key, cached)
                return
            if key in self._in_flight:
                return
            self._in_flight.add(key)
            generation = self._generation

        future = self._executor.submit(
            self._load_worker, key, cluster, generation, on_ready,
        )
        with self._lock:
            self._futures[key] = future

    def clear(self) -> None:
        """Cancel pending work and clear the thumbnail cache."""
        with self._lock:
            self._generation += 1
            self._cache.clear()
            self._in_flight.clear()
            self._futures.clear()

    def evict(self, keep_keys: Set[int]) -> None:
        """Remove cached thumbnails and cancel queued work outside *keep_keys*."""
        with self._lock:
            to_remove = [k for k in self._cache if k not in keep_keys]
            for k in to_remove:
                del self._cache[k]

            to_cancel = [k for k in self._in_flight if k not in keep_keys]
            for k in to_cancel:
                future = self._futures.pop(k, None)
                if future is not None:
                    future.cancel()
                self._in_flight.discard(k)

    def get_cached(self, key: int) -> Optional[np.ndarray]:
        """Return the cached thumbnail for *key*, or ``None``."""
        with self._lock:
            return self._cache.get(key)

    def request_cluster_data(
        self,
        cluster: Cluster,
        on_ready: Callable[[Optional[np.ndarray]], None],
    ) -> None:
        """Extract raw pixel data for *cluster* asynchronously."""
        if cluster.data is not None:
            on_ready(cluster.data)
            return
        self._executor.submit(self._extract_data_worker, cluster, on_ready)

    def _extract_data_worker(
        self,
        cluster: Cluster,
        on_ready: Callable[[Optional[np.ndarray]], None],
    ) -> None:
        """Background worker for one-shot cluster data extraction."""
        try:
            data = self._extract_data(cluster)
            on_ready(data)
        except Exception:
            logger.warning("Cluster data extraction failed", exc_info=True)
            on_ready(None)

    def shutdown(self) -> None:
        """Release all resources (threads, timers, cached data)."""
        with self._lock:
            if self._idle_timer is not None:
                self._idle_timer.cancel()
                self._idle_timer = None
            self._cached_hdus = None
            self._cached_fits_filename = None
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------
    # FITS HDU cache helpers
    # ------------------------------------------------------------------

    def _get_or_load_hdus(
        self, fits_filename: str,
    ) -> List[CCDCaptureModel]:
        """Return cached HDUs for *fits_filename*, loading if needed.

        Must be called under ``self._lock``.
        """
        if self._cached_fits_filename == fits_filename:
            self._reset_idle_timer()
            return self._cached_hdus

        self._cached_hdus = None
        self._cached_fits_filename = None

        hdus = CCDCaptureModel.load(Path(fits_filename))
        self._cached_hdus = hdus
        self._cached_fits_filename = fits_filename
        self._reset_idle_timer()
        return hdus

    def _evict_fits_cache(self) -> None:
        """Release the FITS HDU cache (called by the idle timer)."""
        with self._lock:
            self._cached_fits_filename = None
            self._cached_hdus = None

    def _reset_idle_timer(self) -> None:
        """Restart the idle timer that evicts the FITS cache.

        Must be called under ``self._lock``.
        """
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(
            self._fits_cache_idle_seconds, self._evict_fits_cache,
        )
        self._idle_timer.daemon = True
        self._idle_timer.start()

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _load_worker(
        self,
        key: int,
        cluster: Cluster,
        generation: int,
        on_ready: Callable[[int, np.ndarray], None],
    ) -> None:
        """Background worker that generates a single thumbnail."""
        try:
            with self._lock:
                if generation != self._generation:
                    self._in_flight.discard(key)
                    self._futures.pop(key, None)
                    return

            data = self._extract_data(cluster)

            if (
                data is not None
                and data.ndim >= 2
                and data.size > 0
                and cluster.centerX is None
            ):
                flat_idx = np.argmax(data)
                cy, cx = np.unravel_index(flat_idx, data.shape)
                cluster.centerX = int(cx)
                cluster.centerY = int(cy)

            thumbnail = generate_cluster_thumbnail(
                data, colormap=self._colormap,
            )

            with self._lock:
                if generation != self._generation:
                    self._in_flight.discard(key)
                    self._futures.pop(key, None)
                    return
                self._cache[key] = thumbnail
                self._in_flight.discard(key)
                self._futures.pop(key, None)

            on_ready(key, thumbnail)

        except Exception:
            logger.warning(
                "Thumbnail generation failed for key %d", key,
                exc_info=True,
            )
            with self._lock:
                self._in_flight.discard(key)
                self._futures.pop(key, None)

    def _extract_data(self, cluster: Cluster) -> Optional[np.ndarray]:
        """Extract cluster pixel data from the best available source."""
        if cluster.data is not None:
            return cluster.data

        if cluster.fitsFilename and cluster.hdu_id is not None:
            with self._lock:
                hdus = self._get_or_load_hdus(cluster.fitsFilename)
            if 0 <= cluster.hdu_id < len(hdus):
                return hdus[cluster.hdu_id].clusterFromBoundingBox(
                    cluster.boundingBox,
                )

        return None
