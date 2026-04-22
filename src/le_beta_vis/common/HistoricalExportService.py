"""Threaded orchestrator for Historical result exports (issue #56).

Pulls clusters via ``EventRepository.query_clusters``, hands them to
an ``ExportStorageService`` for the main `.h5`, and iterates them
through a ``ClusterExportService`` for the PNG sidecar folder.

Runs on a ``threading.Thread(daemon=True)`` — the UI layer must not
block on it. Progress is reported via a callback; cancel is cooperative
via the shared ``CancelToken``.
"""
from __future__ import annotations

import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from .Cluster import Cluster
from .ClusterExportService import (
    ClusterExportContext,
    ClusterExportService,
    ClusterMetadataLabels,
)
from .Colormap import Colormap
from .EPSDataClasses import ClusterQueryFilter
from .EventRepository import EventRepository
from .ExportStorageService import (
    CancelToken,
    ExportProvenance,
    ExportStorageService,
)
from .PhysicsConversionManager import PhysicsConversionManager
from .ThumbnailLoaderService import ThumbnailLoaderService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]
"""``(completed, total, stage)`` — stage is 'query', 'h5', or 'png'."""

CompletionCallback = Callable[[Path], None]
ErrorCallback = Callable[[str], None]


def _pct_step(total: int) -> int:
    """Return the stride that yields at most ~100 progress ticks for ``total`` items.

    For large exports (e.g. 15 000 clusters) firing a progress signal on
    every iteration floods the main-thread event queue (~45 000 events
    across three stages) and starves the GNOME heartbeat, causing the
    "Not Responding" dialog. Firing at most once per 1 % keeps the UI
    smooth without sacrificing visible granularity.
    """
    return max(1, total // 100)


@dataclass
class ExportRequest:
    out_path: Path
    query_filter: Optional[ClusterQueryFilter]
    provenance: ExportProvenance
    colormap: Colormap
    labels: ClusterMetadataLabels
    selection_summary: Optional[str] = None


class HistoricalExportService:
    def __init__(
        self,
        repository: EventRepository,
        storage: ExportStorageService,
        png_renderer: ClusterExportService,
        physics: PhysicsConversionManager,
        thumbnail_service: ThumbnailLoaderService,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._png = png_renderer
        self._physics = physics
        self._thumbnails = thumbnail_service
        self._logger = logger_ or logger

    def run_async(
        self,
        request: ExportRequest,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback] = None,
        on_complete: Optional[CompletionCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> threading.Thread:
        thread = threading.Thread(
            target=self._run,
            args=(request, cancel_token, on_progress, on_complete, on_error),
            daemon=True,
            name="HistoricalExportService",
        )
        thread.start()
        return thread

    def _run(
        self,
        request: ExportRequest,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
        on_complete: Optional[CompletionCallback],
        on_error: Optional[ErrorCallback],
    ) -> None:
        images_dir = request.out_path.parent / f"{request.out_path.stem}_images"
        try:
            if on_progress is not None:
                on_progress(0, 0, "query")
            clusters = self._collect_clusters(request.query_filter)
            self._logger.info("query complete: %d clusters", len(clusters))
            if cancel_token.is_cancelled:
                self._cleanup(request.out_path, images_dir)
                return
            self._forward(on_progress, 0, len(clusters), "fits")
            self._hydrate_pixel_data(clusters, cancel_token, on_progress)
            if cancel_token.is_cancelled:
                self._cleanup(request.out_path, images_dir)
                return
            h5_step = _pct_step(len(clusters))
            self._storage.write(
                request.out_path,
                clusters,
                request.provenance,
                cancel_token,
                on_progress=lambda done, t: (
                    self._forward(on_progress, done, t, "h5")
                    if done % h5_step == 0 or done == t
                    else None
                ),
            )
            self._logger.info("h5 complete: %s", request.out_path)
            if cancel_token.is_cancelled:
                self._cleanup(request.out_path, images_dir)
                return
            self._render_png_sidecar(
                clusters, images_dir, request, cancel_token, on_progress
            )
            self._logger.info("png sidecar complete: %s", images_dir)
            if cancel_token.is_cancelled:
                self._cleanup(request.out_path, images_dir)
                return
            if on_complete is not None:
                on_complete(request.out_path)
        except Exception as exc:
            self._logger.exception("Historical export failed")
            self._cleanup(request.out_path, images_dir)
            if on_error is not None:
                on_error(str(exc))

    def _hydrate_pixel_data(
        self,
        clusters: List[Cluster],
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        total = len(clusters)
        self._logger.info("fits hydration start: %d clusters", total)
        missing = 0
        step = _pct_step(total)
        for idx, cluster in enumerate(clusters):
            if cancel_token.is_cancelled:
                return
            done = threading.Event()
            result: list = []

            def on_ready(arr, _done=done, _result=result) -> None:
                _result.append(arr)
                _done.set()

            self._thumbnails.request_cluster_data(cluster, on_ready)
            done.wait()
            cluster.data = result[0] if result else None
            if cluster.data is None:
                missing += 1
                self._logger.warning(
                    "fits hydration: no pixel data for cluster %s", cluster.clusterId
                )
            if (idx + 1) % step == 0 or (idx + 1) == total:
                self._forward(on_progress, idx + 1, total, "fits")
        self._logger.info(
            "fits hydration complete: %d/%d clusters missing data", missing, total
        )

    def _collect_clusters(
        self, query_filter: Optional[ClusterQueryFilter]
    ) -> List[Cluster]:
        # query_clusters is callback-based; bridge to a synchronous list
        # via an Event. The repository is expected to fire exactly one
        # terminal callback (either success or error) per call.
        result: List[Cluster] = []
        error_msg: List[str] = []
        done = threading.Event()

        def on_success(clusters: List[Cluster]) -> None:
            result.extend(clusters)
            done.set()

        def on_error(msg: str) -> None:
            error_msg.append(msg)
            done.set()

        self._repo.query_clusters(query_filter, on_success, on_error)
        done.wait()
        if error_msg:
            raise RuntimeError(f"query_clusters failed: {error_msg[0]}")
        return result

    def _render_png_sidecar(
        self,
        clusters: List[Cluster],
        images_dir: Path,
        request: ExportRequest,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        images_dir.mkdir(parents=True, exist_ok=True)
        context = ClusterExportContext(
            physics=self._physics,
            labels=request.labels,
            selection_summary=request.selection_summary,
        )
        total = len(clusters)
        step = _pct_step(total)
        for idx, cluster in enumerate(clusters):
            if cancel_token.is_cancelled:
                return
            cid = cluster.clusterId if cluster.clusterId is not None else idx
            png_path = images_dir / f"{cid}.png"
            self._png.export(
                cluster, png_path, context=context, colormap=request.colormap
            )
            if (idx + 1) % step == 0 or (idx + 1) == total:
                self._forward(on_progress, idx + 1, total, "png")

    @staticmethod
    def _forward(
        cb: Optional[ProgressCallback], done: int, total: int, stage: str
    ) -> None:
        if cb is not None:
            cb(done, total, stage)

    def _cleanup(self, h5_path: Path, images_dir: Path) -> None:
        try:
            h5_path.unlink(missing_ok=True)
        except OSError:
            self._logger.warning("Failed to remove partial h5 at %s", h5_path)
        try:
            if images_dir.exists():
                shutil.rmtree(images_dir, ignore_errors=True)
        except OSError:
            self._logger.warning("Failed to remove image dir at %s", images_dir)
