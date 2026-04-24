"""Parallel cluster card renderer with streaming zip output (issue #56).

## Threading model

Python's Global Interpreter Lock (GIL) prevents threads from executing Python
bytecode truly in parallel.  ``ThreadPoolExecutor`` workers serialise for
all CPU-bound Python work — including the matplotlib figure layout and axes
setup that dominate each cluster card render.  Only C-extension sections
(libpng compression, Agg rasteriser inner loop) release the GIL, but they
account for a minority of the total render time.

``ProcessPoolExecutor`` bypasses the GIL entirely: each worker process has its
own interpreter and memory space, so N workers truly run N renders in parallel
on N CPU cores.  See ADR-0005 in the project wiki.

## Producer / consumer pipeline

  * A ``ProcessPoolExecutor`` (``spawn`` context, safe with Qt) submits one
    ``_render_card_in_process`` call per cluster.  Each worker writes the card
    to a ``NamedTemporaryFile`` and returns the path.
  * The main thread collects completed futures via ``as_completed`` and feeds
    ``(cid, Path | None)`` tuples into a ``queue.Queue``.
  * A dedicated ``ClusterCardZipWriter`` thread drains the queue, writes each
    entry under ``cluster_cards/<id>.png``, then deletes the temp file.
  * Progress fires once per card *added to the zip*, not per render.

## Physics in subprocesses

``PhysicsConversionManagerImpl`` defines ``__reduce__`` to pickle itself as a
``_PhysicsConversionSnapshot`` (defined in ``PhysicsConversionManager.py``).
The snapshot carries only the two conversion constants and satisfies the full
``PhysicsConversionManager`` ABC.  Every ADU→keV conversion in a worker
therefore still goes through ``context.physics.adu_to_kev()`` — the
CLAUDE.md invariant is preserved.

``HistoricalExportService`` owns the ZipFile lifecycle (open, h5 entry,
rename).  This class is injected into the service and tested independently.

## PyInstaller note (Windows / macOS packaged build)

``multiprocessing.freeze_support()`` must be called in the application entry
point *before* any ``ProcessPoolExecutor`` is created.  The packaged launcher
(``src/le_beta_vis/__main__.py`` or equivalent) should include:

    if __name__ == "__main__":
        multiprocessing.freeze_support()
        ...
"""

from __future__ import annotations

import concurrent.futures
import logging
import multiprocessing
import queue
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .Cluster import Cluster
from .ClusterExportService import ClusterExportContext, ClusterExportService
from .Colormap import Colormap
from .ExportStorageService import CancelToken
from .PhysicsConversionManager import PhysicsConversionManager

# Use the ``spawn`` start method so child processes begin with a clean
# interpreter.  ``fork`` is unsafe here: the parent has an active Qt event
# loop and background threads; forking in that state can deadlock the child.
_MP_CONTEXT = multiprocessing.get_context("spawn")

ProgressCallback = Callable[[int, int, str], None]
"""``(completed, total, stage)`` — stage is always ``'png'`` from this class."""

logger = logging.getLogger(__name__)


def _pct_step(total: int) -> int:
    return max(1, total // 100)


@dataclass
class _CardRenderTask:
    """Picklable snapshot of everything a worker process needs to render one cluster card.

    ``ProcessPoolExecutor`` serialises arguments via pickle, so no Qt objects,
    threading locks, or open file handles may appear here.
    ``PhysicsConversionManagerImpl`` serialises itself to a
    ``_PhysicsConversionSnapshot`` via ``__reduce__``, so ``physics`` is safe
    to include here while still routing all ADU→keV conversions through
    ``PhysicsConversionManager.adu_to_kev()``.
    ``ClusterExportService`` must be picklable — ``MatplotlibPNGClusterExportService``
    qualifies (its only instance attribute is a named ``logging.Logger``).
    """

    cid: str
    cluster: Cluster
    renderer: ClusterExportService
    physics: PhysicsConversionManager
    colormap: Colormap
    labels: object          # ClusterMetadataLabels — frozen dataclass, picklable
    selection_summary: Optional[str]


def _render_card_in_process(task: _CardRenderTask) -> Tuple[str, Optional[str]]:
    """Top-level worker executed in a subprocess by ``ProcessPoolExecutor``.

    Must be a module-level function — ``ProcessPoolExecutor`` requires all
    submitted callables to be picklable; class methods and lambdas are not.

    Returns ``(cid, tmp_path_str)`` on success, or ``(cid, None)`` on failure.
    The caller is responsible for deleting the temp file after zipping.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        context = ClusterExportContext(
            physics=task.physics,
            labels=task.labels,  # type: ignore[arg-type]
            selection_summary=task.selection_summary,
        )
        task.renderer.export(task.cluster, tmp_path, context=context, colormap=task.colormap)
        return task.cid, str(tmp_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        return task.cid, None


class ClusterCardRenderPipeline:
    """Renders cluster cards in parallel and streams them into an open ZipFile.

    Uses ``ProcessPoolExecutor`` (spawn context) to achieve true CPU parallelism
    across cluster card renders — ``ThreadPoolExecutor`` is insufficient because
    Python's GIL serialises the CPU-bound matplotlib work.  See ADR-0005.
    """

    def __init__(
        self,
        png_renderer: ClusterExportService,
        workers: int = 4,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
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

        Blocks until all workers finish and the zip-writer thread has drained
        the queue.  The caller must not close ``zf`` until this method returns.
        Cancellation is cooperative: workers that have already started will
        complete their current render; their output is discarded and temp files
        are deleted before the result enters the zip.
        """
        total = len(clusters)
        step = _pct_step(total)
        result_queue: queue.Queue = queue.Queue()

        zip_thread = threading.Thread(
            target=self._run_zip_writer,
            args=(result_queue, zf, total, step, on_progress),
            daemon=True,
            name="ClusterCardZipWriter",
        )
        zip_thread.start()

        tasks = [
            _CardRenderTask(
                cid=str(cluster.clusterId if cluster.clusterId is not None else idx),
                cluster=cluster,
                renderer=self._png,
                physics=context.physics,
                colormap=colormap,
                labels=context.labels,
                selection_summary=context.selection_summary,
            )
            for idx, cluster in enumerate(clusters)
        ]

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=self._workers, mp_context=_MP_CONTEXT
        ) as pool:
            futures: dict = {}
            for task in tasks:
                if cancel_token.is_cancelled:
                    result_queue.put((task.cid, None))
                    continue
                futures[pool.submit(_render_card_in_process, task)] = task.cid

            _cancel_propagated = False
            for future in concurrent.futures.as_completed(futures):
                cid = futures[future]
                try:
                    _, tmp_path_str = future.result()
                    if cancel_token.is_cancelled:
                        if tmp_path_str:
                            Path(tmp_path_str).unlink(missing_ok=True)
                        result_queue.put((cid, None))
                        if not _cancel_propagated:
                            _cancel_propagated = True
                            for f in futures:
                                f.cancel()
                    else:
                        result_queue.put(
                            (cid, Path(tmp_path_str) if tmp_path_str else None)
                        )
                except concurrent.futures.CancelledError:
                    result_queue.put((cid, None))
                except Exception:
                    self._logger.exception("Cluster card render failed for %s", cid)
                    result_queue.put((cid, None))

        result_queue.put(None)
        zip_thread.join()

    def _run_zip_writer(
        self,
        result_queue: queue.Queue,
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
