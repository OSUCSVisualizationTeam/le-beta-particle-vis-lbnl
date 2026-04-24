"""Tests for DirectPNGClusterExportService."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterExportService import (
    ClusterExportContext,
    ClusterExportMetadata,
    ClusterMetadataLabels,
)
from le_beta_vis.common.Colormap import Colormap
from le_beta_vis.common.DirectPNGClusterExportService import (
    DirectPNGClusterExportService,
    _colormap_lut,
)
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)

from mock_configuration_service import MockConfigurationService


def _make_cluster() -> Cluster:
    data = np.zeros((5, 5), dtype=np.float64)
    data[2, 2] = 1000.0
    return Cluster(
        boundingBox=BoundingBox(top=2030, left=2, bottom=2035, right=7),
        data=data,
        centerX=4,
        centerY=2033,
        sigmaX=0.8,
        sigmaY=0.9,
        energy=2500.0,
        pixelCount=15,
        clusterId=28,
    )


def _physics(factor: float = 1.0e-3) -> PhysicsConversionManagerImpl:
    cfg = MockConfigurationService()
    cfg.set("global:physics:kev_conversion", factor)
    cfg.set("global:physics:ped_width", 1400)
    return PhysicsConversionManagerImpl(cfg)


def _context(factor: float = 1.0e-3) -> ClusterExportContext:
    return ClusterExportContext(
        physics=_physics(factor),
        labels=ClusterMetadataLabels.default_english(),
        selection_summary="0 < energy < 999999",
    )


class TestDirectPNGClusterExportService:
    def test_export_writes_non_empty_png(self, tmp_path: Path) -> None:
        out = tmp_path / "cluster.png"
        svc = DirectPNGClusterExportService()
        svc.export(
            _make_cluster(), out, context=_context(), colormap=Colormap.VIRIDIS
        )
        assert out.exists()
        assert out.stat().st_size > 0
        with out.open("rb") as fh:
            assert fh.read(8) == b"\x89PNG\r\n\x1a\n"

    def test_export_rejects_unknown_colormap(self) -> None:
        # Colormap is an enum; constructing from a bad value raises ValueError
        # at call time, so the service never needs to defend against bogus
        # matplotlib cmap strings.
        with pytest.raises(ValueError):
            Colormap("__not_a_real_colormap__")

    def test_render_to_bytes_returns_valid_png_bytes(self) -> None:
        svc = DirectPNGClusterExportService()
        result = svc.render_to_bytes(
            _make_cluster(), context=_context(), colormap=Colormap.VIRIDIS
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_grayscale_colormap_resolves(self, tmp_path: Path) -> None:
        # The Colormap.GRAYSCALE enum value ("grayscale") is not a
        # matplotlib name; the renderer must alias it to "gray" so the
        # LUT lookup succeeds.
        out = tmp_path / "cluster_gray.png"
        svc = DirectPNGClusterExportService()
        svc.export(
            _make_cluster(),
            out,
            context=_context(),
            colormap=Colormap.GRAYSCALE,
        )
        assert out.exists() and out.stat().st_size > 0

    def test_output_dimensions_match_expected_canvas_size(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "cluster.png"
        svc = DirectPNGClusterExportService()
        svc.export(
            _make_cluster(), out, context=_context(), colormap=Colormap.VIRIDIS
        )
        with Image.open(out) as img:
            assert img.size == (1200, 600)


class TestColormapLUT:
    def test_lut_shape_for_all_colormaps(self) -> None:
        for cm in Colormap:
            lut = _colormap_lut(cm)
            assert lut.shape == (256, 3), f"{cm} produced shape {lut.shape}"
            assert lut.dtype == np.uint8, f"{cm} produced dtype {lut.dtype}"

    def test_grayscale_lut_is_monotonic(self) -> None:
        lut = _colormap_lut(Colormap.GRAYSCALE)
        # R = G = B for grayscale; all channels identical.
        assert np.array_equal(lut[:, 0], lut[:, 1])
        assert np.array_equal(lut[:, 1], lut[:, 2])
        # Strictly non-decreasing ramp from 0 → 255.
        diffs = np.diff(lut[:, 0].astype(np.int16))
        assert (diffs >= 0).all()
        assert int(lut[0, 0]) == 0
        assert int(lut[255, 0]) == 255


class TestBuildMetadata:
    def test_metadata_has_no_cluster_id_field(self) -> None:
        # Regression pin: cluster id lives in the figure title; the
        # metadata panel must not duplicate it.
        field_names = {f.name for f in fields(ClusterExportMetadata)}
        assert "cluster_id" not in field_names

    def test_energy_uses_physics_conversion(self) -> None:
        svc = DirectPNGClusterExportService()
        cluster = _make_cluster()
        ctx = _context(factor=2.0e-3)
        metadata = svc.build_metadata(cluster, ctx)
        assert metadata.total_energy_kev == pytest.approx(
            ctx.physics.adu_to_kev(float(cluster.energy))
        )
        assert metadata.pixel_count == 15
        assert metadata.full_width_x == 5
        assert metadata.full_width_y == 5
