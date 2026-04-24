# Tests for ClusterCardRenderPipeline — parallel render + zip-writer pipeline.
# Uses MatplotlibPNGClusterExportService with small (2×2) clusters so subprocesses
# do real renders without needing a fake renderer (cross-process state sharing is
# not possible with ProcessPoolExecutor — see ADR-0005).

"""Tests for ClusterCardRenderPipeline."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import List, Optional

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterCardRenderPipeline import ClusterCardRenderPipeline
from le_beta_vis.common.ClusterExportService import (
    ClusterExportContext,
    ClusterMetadataLabels,
)
from le_beta_vis.common.Colormap import Colormap
from le_beta_vis.common.ExportStorageService import CancelToken
from le_beta_vis.common.MatplotlibPNGClusterExportService import (
    MatplotlibPNGClusterExportService,
)

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl


def _physics() -> PhysicsConversionManagerImpl:
    cfg = MockConfigurationService()
    cfg.set("global:physics:kev_conversion", 1.0e-5)
    cfg.set("global:physics:ped_width", 1400)
    return PhysicsConversionManagerImpl(cfg)


def _cluster(cid: int = 1) -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(0, 0, 2, 2),
        data=np.ones((2, 2), dtype=np.float64) * 2000.0,
        centerX=1,
        centerY=1,
        energy=8000.0,
        pixelCount=4,
        clusterId=cid,
    )


def _context() -> ClusterExportContext:
    return ClusterExportContext(
        physics=_physics(),
        labels=ClusterMetadataLabels.default_english(),
    )


def _pipeline(workers: int = 2) -> ClusterCardRenderPipeline:
    return ClusterCardRenderPipeline(
        png_renderer=MatplotlibPNGClusterExportService(),
        workers=workers,
    )


class TestClusterCardRenderPipeline:
    def test_happy_path_writes_all_cards(self, tmp_path: Path) -> None:
        clusters = [_cluster(1), _cluster(2), _cluster(3)]
        pipeline = _pipeline()
        zip_path = tmp_path / "out.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            pipeline.run(clusters, zf, _context(), Colormap.VIRIDIS, CancelToken(), None)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert "cluster_cards/1.png" in names
        assert "cluster_cards/2.png" in names
        assert "cluster_cards/3.png" in names

    def test_cancel_before_start_writes_no_cards(self, tmp_path: Path) -> None:
        clusters = [_cluster(1), _cluster(2)]
        pipeline = _pipeline()
        token = CancelToken()
        token.cancel()
        zip_path = tmp_path / "out.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            pipeline.run(clusters, zf, _context(), Colormap.VIRIDIS, token, None)

        with zipfile.ZipFile(zip_path, "r") as zf:
            assert zf.namelist() == []

    def test_render_failure_skips_cluster_but_continues(self, tmp_path: Path) -> None:
        # cluster.data = None causes np.asarray(None).shape → () which fails to
        # unpack as (rows, cols) in build_metadata → render error in subprocess.
        bad = _cluster(1)
        bad.data = None
        clusters = [bad, _cluster(2)]
        pipeline = _pipeline()
        zip_path = tmp_path / "out.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            pipeline.run(clusters, zf, _context(), Colormap.VIRIDIS, CancelToken(), None)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert "cluster_cards/1.png" not in names
        assert "cluster_cards/2.png" in names

    def test_progress_fires_once_per_card_added(self, tmp_path: Path) -> None:
        clusters = [_cluster(i) for i in range(1, 4)]  # 3 clusters
        pipeline = _pipeline()
        ticks: List[tuple] = []
        zip_path = tmp_path / "out.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            pipeline.run(
                clusters, zf, _context(), Colormap.VIRIDIS, CancelToken(),
                on_progress=lambda d, t, s: ticks.append((d, t, s)),
            )

        assert all(s == "png" for _, _, s in ticks)
        completed_values = [d for d, _, _ in ticks]
        assert completed_values == sorted(completed_values)
        assert completed_values[-1] == 3

    def test_workers_clamped_to_minimum_of_two(self) -> None:
        pipeline = ClusterCardRenderPipeline(
            png_renderer=MatplotlibPNGClusterExportService(), workers=1
        )
        assert pipeline._workers == 2

    def test_workers_clamped_to_maximum_of_sixteen(self) -> None:
        pipeline = ClusterCardRenderPipeline(
            png_renderer=MatplotlibPNGClusterExportService(), workers=99
        )
        assert pipeline._workers == 16

    def test_no_temp_files_left_after_export(self, tmp_path: Path) -> None:
        import tempfile as _tempfile

        clusters = [_cluster(1), _cluster(2)]
        pipeline = _pipeline()
        zip_path = tmp_path / "out.zip"
        tmp_dir = Path(_tempfile.gettempdir())
        before = set(tmp_dir.glob("*.png"))

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            pipeline.run(clusters, zf, _context(), Colormap.VIRIDIS, CancelToken(), None)

        after = set(tmp_dir.glob("*.png"))
        assert after == before, f"orphaned temp PNGs: {after - before}"
