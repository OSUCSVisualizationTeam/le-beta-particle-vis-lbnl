"""Threaded orchestrator for Historical result exports (issue #56).

Pulls clusters via ``EventRepository.query_clusters``, hands them to
an ``ExportStorageService`` for the `.h5` file. When the user opts in
via ``ExportRequest.include_pngs``, a ZIP archive is produced instead:
it contains the HDF5 file and a ``cluster_cards/`` directory of PNGs.

Runs on a ``threading.Thread(daemon=True)`` — the UI layer must not
block on it. Progress is reported via a callback; cancel is cooperative
via the shared ``CancelToken``.
"""

from __future__ import annotations

import logging
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from ..common.Cluster import Cluster
from ..common.Colormap import Colormap
from ..common.EPSDataClasses import ClusterQueryFilter
from ..common.EventRepository import EventRepository
from ..common.PhysicsConversionManager import PhysicsConversionManager
from ..common.ThumbnailLoaderService import ThumbnailLoaderService
from .ClusterCardRenderPipeline import ClusterCardRenderPipeline
from .ClusterExportService import (
    ClusterExportContext,
    ClusterExportService,
    ClusterMetadataLabels,
)
from .ExportStorageService import (
    CancelToken,
    ExportProvenance,
    ExportStorageService,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]
"""``(completed, total, stage)`` — stage is 'query', 'h5', or 'png'."""

CompletionCallback = Callable[[Path], None]
"""``(out_path)`` — fired on the worker thread when the export finishes."""

ErrorCallback = Callable[[str], None]
"""``(message)`` — fired on the worker thread when an exception aborts the export."""

CancelledCallback = Callable[[], None]
"""``()`` — fired on the worker thread when the cancel token was set."""


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
    """Parameters for a single historical export run."""

    out_path: Path
    query_filter: Optional[ClusterQueryFilter]
    provenance: ExportProvenance
    colormap: Colormap
    labels: ClusterMetadataLabels
    selection_summary: Optional[str] = None
    include_pngs: bool = False


class HistoricalExportService:
    """Orchestrates the export pipeline: query → FITS hydration → HDF5 → optional cluster-cards ZIP."""

    def __init__(
        self,
        repository: EventRepository,
        storage: ExportStorageService,
        png_renderer: ClusterExportService,
        physics: PhysicsConversionManager,
        thumbnail_service: ThumbnailLoaderService,
        png_render_workers: int = 4,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        """Wire up repositories and services; ``png_render_workers`` controls the
        ThreadPoolExecutor width used during the cluster card render phase."""
        self._repo = repository
        self._storage = storage
        self._physics = physics
        self._thumbnails = thumbnail_service
        self._logger = logger_ or logger
        self._card_pipeline = ClusterCardRenderPipeline(
            png_renderer=png_renderer,
            workers=png_render_workers,
            logger_=self._logger,
        )

    def run_async(
        self,
        request: ExportRequest,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback] = None,
        on_complete: Optional[CompletionCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        on_cancelled: Optional[CancelledCallback] = None,
    ) -> threading.Thread:
        """Start the export pipeline on a daemon thread and return the thread.

        All callbacks fire on the worker thread — callers that touch Qt must
        marshal to the main thread (e.g. via ``QMetaObject.invokeMethod``).
        """
        thread = threading.Thread(
            target=self._run,
            args=(
                request,
                cancel_token,
                on_progress,
                on_complete,
                on_error,
                on_cancelled,
            ),
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
        on_cancelled: Optional[CancelledCallback] = None,
    ) -> None:
        """Worker-thread entry point. Runs the four pipeline steps in order; any step that returns
        ``False`` (cancel or error) halts the pipeline immediately. The h5_path is a sibling
        ``.h5`` file when bundling a ZIP so the final artifact can be assembled before replacing
        ``out_path``.
        """
        # When bundling a ZIP, the H5 is written to a sibling path first.
        h5_path = (
            request.out_path.with_suffix(".h5")
            if request.include_pngs
            else request.out_path
        )
        try:
            ok, clusters = self._step_gather_clusters(
                request, cancel_token, on_progress, h5_path, on_cancelled
            )
            if not ok:
                return
            if not self._step_hydrate(
                clusters,
                cancel_token,
                on_progress,
                request.out_path,
                h5_path,
                on_cancelled,
            ):
                return
            if not self._step_write_h5(
                clusters,
                request,
                h5_path,
                cancel_token,
                on_progress,
                on_cancelled,
            ):
                return
            if request.include_pngs:
                if not self._step_render_and_zip(
                    clusters,
                    request,
                    h5_path,
                    cancel_token,
                    on_progress,
                    on_cancelled,
                ):
                    return
            if on_complete is not None:
                on_complete(request.out_path)
        except Exception as exc:
            self._logger.exception("Historical export failed")
            self._cleanup(request.out_path, h5_path)
            if on_error is not None:
                on_error(str(exc))

    def _step_gather_clusters(
        self,
        request: ExportRequest,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
        h5_path: Path,
        on_cancelled: Optional[CancelledCallback],
    ) -> Tuple[bool, List[Cluster]]:
        """Query the repository, log the result count, and return ``(True, clusters)`` on success.

        Fires a 0/0 progress tick before the query and a 0/N tick after so the UI shows the
        cluster count before the FITS hydration stage begins.
        """
        self._forward(on_progress, 0, 0, "query")
        clusters = self._collect_clusters(request.query_filter)
        self._logger.info("query complete: %d clusters", len(clusters))
        if cancel_token.is_cancelled:
            self._cleanup(request.out_path, h5_path)
            self._call_cancelled(on_cancelled)
            return False, []
        self._forward(on_progress, 0, len(clusters), "fits")
        return True, clusters

    def _step_hydrate(
        self,
        clusters: List[Cluster],
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
        out_path: Path,
        h5_path: Path,
        on_cancelled: Optional[CancelledCallback],
    ) -> bool:
        """Hydrate FITS pixel data into all clusters. Returns ``False`` and fires ``on_cancelled`` if the cancel token is set when hydration finishes."""
        self._hydrate_pixel_data(clusters, cancel_token, on_progress)
        if cancel_token.is_cancelled:
            self._cleanup(out_path, h5_path)
            self._call_cancelled(on_cancelled)
            return False
        return True

    def _step_write_h5(
        self,
        clusters: List[Cluster],
        request: ExportRequest,
        h5_path: Path,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
        on_cancelled: Optional[CancelledCallback],
    ) -> bool:
        """Write the HDF5 file via the injected storage service. Wraps the per-row progress with a throttled lambda (fires at most every ``_pct_step`` rows) to avoid flooding the main-thread event queue."""
        h5_step = _pct_step(len(clusters))
        self._storage.write(
            h5_path,
            clusters,
            request.provenance,
            cancel_token,
            on_progress=lambda done, t: (
                self._forward(on_progress, done, t, "h5")
                if done % h5_step == 0 or done == t
                else None
            ),
        )
        self._logger.info("h5 complete: %s", h5_path)
        if cancel_token.is_cancelled:
            self._cleanup(request.out_path, h5_path)
            self._call_cancelled(on_cancelled)
            return False
        return True

    def _step_render_and_zip(
        self,
        clusters: List[Cluster],
        request: ExportRequest,
        h5_path: Path,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
        on_cancelled: Optional[CancelledCallback],
    ) -> bool:
        """Render all cluster cards and bundle them with the HDF5 into a ZIP.

        Writes to a ``.zip.partial`` sibling first; on success renames it over
        ``out_path`` and removes the intermediate HDF5 file. On any failure the
        partial file is deleted before re-raising.
        """
        context = ClusterExportContext(
            physics=self._physics,
            labels=request.labels,
            selection_summary=request.selection_summary,
        )
        tmp_zip = request.out_path.with_suffix(".zip.partial")
        stem = request.out_path.stem
        try:
            with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.write(h5_path, arcname=f"{stem}.h5")
                self._card_pipeline.run(
                    clusters, zf, context, request.colormap, cancel_token, on_progress
                )
        except BaseException:
            tmp_zip.unlink(missing_ok=True)
            raise
        if cancel_token.is_cancelled:
            tmp_zip.unlink(missing_ok=True)
            self._cleanup(request.out_path, h5_path)
            self._call_cancelled(on_cancelled)
            return False
        tmp_zip.replace(request.out_path)
        h5_path.unlink(missing_ok=True)
        self._logger.info("zip complete: %s", request.out_path)
        return True

    def _hydrate_pixel_data(
        self,
        clusters: List[Cluster],
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        """Fan-out all FITS data requests before waiting on any result, so the thumbnail
        service's internal workers stay saturated. Results are collected in submission order;
        clusters with no pixel data are logged and left with ``data = None``.
        """
        total = len(clusters)
        self._logger.info("fits hydration start: %d clusters", total)
        step = _pct_step(total)

        # Issue all requests before waiting for any result so the thumbnail
        # service's internal workers stay saturated throughout hydration.
        pending: List[Tuple[threading.Event, list]] = []
        for cluster in clusters:
            done = threading.Event()
            result: list = []

            def on_ready(arr, _done=done, _result=result) -> None:
                _result.append(arr)
                _done.set()

            self._thumbnails.request_cluster_data(cluster, on_ready)
            pending.append((done, result))

        missing = 0
        for idx, (cluster, (done, result)) in enumerate(zip(clusters, pending)):
            if cancel_token.is_cancelled:
                return
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
        """Bridge the callback-based ``EventRepository.query_clusters`` API to a blocking
        return value using a ``threading.Event`` latch. Raises ``RuntimeError`` if the
        repository reports an error.
        """
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

    @staticmethod
    def _forward(
        cb: Optional[ProgressCallback], done: int, total: int, stage: str
    ) -> None:
        if cb is not None:
            cb(done, total, stage)

    @staticmethod
    def _call_cancelled(cb: Optional[CancelledCallback]) -> None:
        if cb is not None:
            cb()

    def _cleanup(self, out_path: Path, h5_path: Optional[Path] = None) -> None:
        for p in (p for p in [out_path, h5_path] if p is not None):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                self._logger.warning("Failed to remove %s", p)
