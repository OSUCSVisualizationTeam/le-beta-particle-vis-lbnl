"""Parallel cluster card renderer with streaming zip output.

## Threading model

With the matplotlib-based renderer replaced by
``DirectPNGClusterExportService`` (``numpy`` LUT + Pillow), the per-card
work is no longer dominated by GIL-bound Python. Agg/matplotlib figure
construction is gone; what's left is numpy array ops and libpng
encoding inside Pillow, both of which release the GIL. A
``ThreadPoolExecutor`` is therefore the right primitive: it avoids
subprocess spawn cost, pickling per task, and PyInstaller's
``freeze_support`` requirement, while still giving real concurrency
across cores for the C sections.

## Producer / consumer pipeline

  * A ``ThreadPoolExecutor`` submits one ``_render_card`` call per
    cluster. Each worker writes the PNG to a ``NamedTemporaryFile``
    and returns the path (or ``None`` on failure / cancel).
  * The main thread collects completed futures via ``as_completed`` and
    feeds ``(cid, Path | None)`` tuples into a ``queue.Queue``.
  * A dedicated ``ClusterCardZipWriter`` thread drains the queue,
    writes each entry under ``cluster_cards/<id>.png``, then deletes
    the temp file.
  * Progress fires once per card *added to the zip*, not per render.

``HistoricalExportService`` owns the ZipFile lifecycle (open, h5
entry, rename). This class is injected into the service and tested
independently.
"""

from __future__ import annotations

import concurrent.futures
import logging
import queue
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..common.Cluster import Cluster
from ..common.Colormap import Colormap
from .ClusterExportService import ClusterExportContext, ClusterExportService
from .ExportStorageService import CancelToken

ProgressCallback = Callable[[int, int, str], None]
"""``(completed, total, stage)`` — stage is always ``'png'`` from this class."""

logger = logging.getLogger(__name__)


def _pct_step(total: int) -> int:
    """Return the stride that yields at most ~100 progress ticks for ``total`` items.

    Firing on every card floods the main-thread event queue on large exports
    and can starve the GNOME heartbeat. Capping at 1 % granularity keeps the
    UI smooth without sacrificing visible progress.
    """
    return max(1, total // 100)


@dataclass
class _RenderJob:
    """In-process descriptor of one cluster card render."""

    cid: str
    cluster: Cluster
    context: ClusterExportContext
    colormap: Colormap


class ClusterCardRenderPipeline:
    """Renders cluster cards in parallel and streams them into an open ZipFile."""

    def __init__(
        self,
        png_renderer: ClusterExportService,
        workers: int = 4,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        """``workers`` is clamped to [2, 16] — lower bound keeps the zip-writer
        thread fed; upper bound caps thread pressure during large exports."""
        self._png = png_renderer
        self._workers = max(2, min(16, workers))
        self._logger = logger_ or logger

    def run(
        self,
        clusters: List[Cluster],
        zf: zipfile.ZipFile,
        context: ClusterExportContext,
        colormap: Colormap,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        """Render all cluster cards in parallel and write them into ``zf``.

        Blocks until all workers finish and the zip-writer thread has
        drained the queue. The caller must not close ``zf`` until this
        method returns. Cancellation is cooperative: workers check the
        token before doing work, so late cancels discard cheaply.
        """
        total = len(clusters)
        step = _pct_step(total)
        result_queue: "queue.Queue" = queue.Queue()

        zip_thread = self._start_zip_writer_thread(
            result_queue, zf, total, step, on_progress
        )

        jobs = self._build_jobs(clusters, context, colormap)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._workers,
            thread_name_prefix="ClusterCardRenderer",
        ) as pool:
            futures = self._submit_renders(pool, jobs, cancel_token, result_queue)
            self._collect_results(futures, cancel_token, result_queue)

        self._stop_zip_writer_thread(result_queue, zip_thread)

    @staticmethod
    def _build_jobs(
        clusters: List[Cluster],
        context: ClusterExportContext,
        colormap: Colormap,
    ) -> List[_RenderJob]:
        """Build one ``_RenderJob`` per cluster. Falls back to the list index as the card ID when ``cluster.clusterId`` is ``None``."""
        return [
            _RenderJob(
                cid=str(
                    cluster.clusterId if cluster.clusterId is not None else idx
                ),
                cluster=cluster,
                context=context,
                colormap=colormap,
            )
            for idx, cluster in enumerate(clusters)
        ]

    def _submit_renders(
        self,
        pool: concurrent.futures.ThreadPoolExecutor,
        jobs: List[_RenderJob],
        cancel_token: CancelToken,
        result_queue: "queue.Queue",
    ) -> Dict[concurrent.futures.Future, str]:
        """Submit one render future per job. Cancelled jobs are not submitted but are still placed on the queue as ``(cid, None)`` so the zip-writer thread receives exactly ``len(jobs)`` items and can exit cleanly."""
        futures: Dict[concurrent.futures.Future, str] = {}
        for job in jobs:
            if cancel_token.is_cancelled:
                result_queue.put((job.cid, None))
                continue
            future = pool.submit(self._render_card, job, cancel_token)
            futures[future] = job.cid
        return futures

    def _collect_results(
        self,
        futures: Dict[concurrent.futures.Future, str],
        cancel_token: CancelToken,
        result_queue: "queue.Queue",
    ) -> None:
        """Drain completed futures into the result queue. Deletes the temp file for any card whose future resolved after cancellation to avoid leaking disk space."""
        for future in concurrent.futures.as_completed(futures):
            cid = futures[future]
            try:
                _, tmp_path_str = future.result()
            except Exception:
                self._logger.exception(
                    "Cluster card render failed for %s", cid
                )
                result_queue.put((cid, None))
                continue

            if cancel_token.is_cancelled:
                if tmp_path_str:
                    Path(tmp_path_str).unlink(missing_ok=True)
                result_queue.put((cid, None))
                continue

            result_queue.put(
                (cid, Path(tmp_path_str) if tmp_path_str else None)
            )

    def _start_zip_writer_thread(
        self,
        result_queue: "queue.Queue",
        zf: zipfile.ZipFile,
        total: int,
        step: int,
        on_progress: Optional[ProgressCallback],
    ) -> threading.Thread:
        thread = threading.Thread(
            target=self._run_zip_writer,
            args=(result_queue, zf, total, step, on_progress),
            daemon=True,
            name="ClusterCardZipWriter",
        )
        thread.start()
        return thread

    @staticmethod
    def _stop_zip_writer_thread(
        result_queue: "queue.Queue", zip_thread: threading.Thread
    ) -> None:
        """Put a ``None`` sentinel to signal the consumer loop to exit, then join the thread."""
        result_queue.put(None)
        zip_thread.join()

    def _render_card(
        self, job: _RenderJob, cancel_token: CancelToken
    ) -> Tuple[str, Optional[str]]:
        """Render one cluster card into a temp PNG.

        Returns ``(cid, tmp_path_str)`` on success, or ``(cid, None)`` on
        cancel / failure. The caller is responsible for deleting the
        temp file after zipping.
        """
        if cancel_token.is_cancelled:
            return job.cid, None
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            self._png.export(
                job.cluster,
                tmp_path,
                context=job.context,
                colormap=job.colormap,
            )
            return job.cid, str(tmp_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            return job.cid, None

    def _run_zip_writer(
        self,
        result_queue: "queue.Queue",
        zf: zipfile.ZipFile,
        total: int,
        step: int,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        """Consumer thread: drains queue, adds PNGs to zip, fires progress."""
        completed = 0
        while True:
            item = result_queue.get()
            if item is None:
                break
            cid, tmp_path = item
            if tmp_path is not None:
                try:
                    zf.write(tmp_path, arcname=f"cluster_cards/{cid}.png")
                except Exception:
                    self._logger.exception(
                        "Failed to add cluster card %s to zip", cid
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)
            completed += 1
            if completed % step == 0 or completed == total:
                if on_progress is not None:
                    on_progress(completed, total, "png")
