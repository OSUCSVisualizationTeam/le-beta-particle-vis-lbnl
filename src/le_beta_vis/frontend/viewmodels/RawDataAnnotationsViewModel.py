"""ViewModel for persistent, EPS-backed cluster annotations.

Pure Python — no Qt dependencies.
"""
import logging
import threading
from typing import Callable, List, Optional

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ParticleType import ParticleType, classify_particle

logger = logging.getLogger(__name__)


class RawDataAnnotationsViewModel:
    """Owns persistent classification annotations for the loaded FITS file/HDU.

    Constructed by RawDataViewModel and exposed as
    ``raw_data_vm.annotationsViewModel``. EPS access is injected via
    handler setters so this VM stays free of repository/networking
    knowledge — RawDataView wires the handlers when a repository is
    available.
    """

    def __init__(
        self,
        show_low_confidence_provider: Callable[[], bool],
        threshold_provider: Callable[[], float],
    ) -> None:
        self._show_low_confidence_provider = show_low_confidence_provider
        self._threshold_provider = threshold_provider
        self._fits_lookup_handler: Optional[
            Callable[[str], Optional[int]]
        ] = None
        self._cluster_fetch_handler: Optional[
            Callable[[int, int], List[Cluster]]
        ] = None
        self._annotations: List[Cluster] = []
        self._on_annotations_changed: List[Callable[[], None]] = []
        self._refresh_token: int = 0
        self._lock = threading.Lock()

    # --- Handler injection ---

    def setFitsLookupHandler(
        self, handler: Optional[Callable[[str], Optional[int]]]
    ) -> None:
        """Injects the callback that resolves a FITS path to an EPS fits_id.

        Receives the full FITS file path and returns the EPS fits_id, or
        None if the file has not been through the ingestion pipeline.
        Kept as an injection seam so this pure-Python VM stays free of
        direct EventRepository knowledge.
        """
        self._fits_lookup_handler = handler

    def setClusterFetchHandler(
        self, handler: Optional[Callable[[int, int], List[Cluster]]]
    ) -> None:
        """Injects the callback that fetches hydrated clusters for a FITS/HDU.

        Receives ``(fits_id, hdu_index)`` and returns clusters with pixel
        data already populated. Kept as an injection seam for the same
        reason as ``setFitsLookupHandler``.
        """
        self._cluster_fetch_handler = handler

    # --- Commands ---

    def refresh(self, fits_path: Optional[str], hdu_index: int) -> None:
        """Asynchronously (re)loads annotations for *fits_path*/*hdu_index*.

        Clears any existing annotations immediately so stale boxes from a
        previous file never linger during the fetch, then repopulates them
        on a background thread once the EPS round-trip completes. No-ops
        (beyond the clear) when no FITS path is given or the EPS handlers
        have not been wired. Safe to call repeatedly — only the most
        recent call's result is applied.
        """
        with self._lock:
            self._refresh_token += 1
            token = self._refresh_token
            self._annotations = []
        self._notify_annotations_changed()
        if (
            fits_path is None
            or self._fits_lookup_handler is None
            or self._cluster_fetch_handler is None
        ):
            return
        threading.Thread(
            target=self._refresh_worker,
            args=(token, fits_path, hdu_index),
            daemon=True,
        ).start()

    def clear(self) -> None:
        """Clears all annotations and notifies observers."""
        with self._lock:
            self._refresh_token += 1
            self._annotations = []
        self._notify_annotations_changed()

    # --- Queries ---

    @property
    def annotations(self) -> List[Cluster]:
        """All fetched annotations for the current FITS file/HDU, unfiltered."""
        return list(self._annotations)

    @property
    def visibleAnnotations(self) -> List[Cluster]:
        """Annotations after applying the low-confidence visibility filter."""
        if self._show_low_confidence_provider():
            return list(self._annotations)
        threshold = self._threshold_provider()
        return [
            c
            for c in self._annotations
            if classify_particle(c, threshold)[0] != ParticleType.UNCLASSIFIED
        ]

    def hitTest(self, row: int, col: int) -> Optional[Cluster]:
        """Returns the first visible annotation whose bbox contains (row, col).

        Uses half-open bounds on the row/col span, matching the convention
        already used for ROI hit-testing in
        ``_CenterImageAreaView._onBoxSelectClicked``. EPS-sourced clusters
        store ``top``/``bottom`` with the axis flipped relative to
        locally-extracted ones (see ``ClusterLocationMapWidget._draw_bbox``),
        so bounds are normalized with min/max rather than assumed ordered.
        """
        for cluster in self.visibleAnnotations:
            bb = cluster.boundingBox
            row_lo, row_hi = min(bb.top, bb.bottom), max(bb.top, bb.bottom)
            col_lo, col_hi = min(bb.left, bb.right), max(bb.left, bb.right)
            if row_lo <= row < row_hi and col_lo <= col < col_hi:
                return cluster
        return None

    # --- Worker ---

    def _refresh_worker(
        self, token: int, fits_path: str, hdu_index: int
    ) -> None:
        try:
            fits_id = self._fits_lookup_handler(fits_path)
            if fits_id is None:
                return
            clusters = self._cluster_fetch_handler(fits_id, hdu_index)
        except Exception:
            logger.exception(
                "Failed to fetch annotations for %s (HDU %d)",
                fits_path,
                hdu_index,
            )
            return
        self._apply_annotations(token, clusters)

    def _apply_annotations(self, token: int, clusters: List[Cluster]) -> None:
        with self._lock:
            if token != self._refresh_token:
                return
            self._annotations = clusters
        self._notify_annotations_changed()

    # --- Observer pattern ---

    def add_annotations_changed_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Registers a callback fired whenever the annotation list changes."""
        self._on_annotations_changed.append(callback)

    def _notify_annotations_changed(self) -> None:
        for callback in self._on_annotations_changed:
            callback()
