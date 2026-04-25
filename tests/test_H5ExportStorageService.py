# Validate /clusters schema, /images/<id> shape, /export_info attrs, column-order lock, and cancel cleanup

"""Tests for H5ExportStorageService."""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.export.ExportStorageService import CancelToken, ExportProvenance
from le_beta_vis.export.H5ExportStorageService import (
    CLUSTER_COLUMNS,
    H5ExportStorageService,
)
from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)

from mock_configuration_service import MockConfigurationService


def _physics(factor: float) -> PhysicsConversionManagerImpl:
    cfg = MockConfigurationService()
    cfg.set("global:physics:kev_conversion", factor)
    cfg.set("global:physics:ped_width", 1400)
    return PhysicsConversionManagerImpl(cfg)


EXPECTED_COLUMN_ORDER = (
    "cluster_id",
    "fits_id",
    "fits_filename",
    "date",
    "hdu_id",
    "center_x",
    "center_y",
    "bbox_top",
    "bbox_left",
    "bbox_bottom",
    "bbox_right",
    "sigma_x",
    "sigma_y",
    "pixel_count",
    "energy_adu",
    "energy_kev",
    "score_cnn",
    "score_nrg",
    "score_bdt",
    "cnn_particle_type",
    "bdt_particle_type",
    "nrg_particle_type",
    "particle_type",
)


def _make_cluster(cluster_id: int = 42, energy: float = 1000.0) -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(top=100, left=200, bottom=110, right=215),
        data=np.arange(16, dtype=np.float64).reshape(4, 4),
        centerX=207,
        centerY=105,
        sigmaX=1.1,
        sigmaY=1.2,
        energy=energy,
        pixelCount=15,
        fitsId=7,
        clusterId=cluster_id,
        cnnClassification=0.1,
        nrgClassification=0.2,
        bdtClassification=0.3,
        fitsFilename="capture.fits",
        date="2026-04-21T10:00:00",
        classification=ParticleType.UNCLASSIFIED.name,
        hdu_id=1,
    )


def _provenance() -> ExportProvenance:
    return ExportProvenance(
        app_version="0.0.2",
        export_timestamp_utc="2026-04-21T12:00:00Z",
        filter_json='{"min_sigma_x": 0.5}',
        calibration_kev_conversion_factor=1.02857e-5,
        calibration_pedestal_width=1400,
        hostname="test-host",
        user="test-user",
        machine_id="aa:bb:cc:dd:ee:ff",
        fits_headers={"capture.fits": {"EXPTIME": "60.0"}},
    )


class TestColumnOrderIsLocked:
    """Guards the 'downstream analysis scripts pin to this order' invariant.

    If this test fails because a column was added, append to the END of
    the tuple in H5ExportStorageService AND add the new column here —
    never re-order.
    """

    def test_cluster_columns_tuple_matches_expected(self) -> None:
        assert CLUSTER_COLUMNS == EXPECTED_COLUMN_ORDER


class TestH5ExportStorageServiceWrite:
    def test_writes_clusters_images_and_export_info(self, tmp_path: Path) -> None:
        out = tmp_path / "out.h5"
        svc = H5ExportStorageService(_physics(1.0e-5))
        cluster = _make_cluster()

        svc.write(out, [cluster], _provenance(), CancelToken(), on_progress=None)

        assert out.exists()
        with h5py.File(out, "r") as f:
            assert "clusters" in f
            assert "images" in f
            assert "export_info" in f
            assert "42" in f["images"]  # clusterId
            assert f["images"]["42"].shape == (4, 4)

    def test_clusters_row_has_all_columns_in_order(self, tmp_path: Path) -> None:
        out = tmp_path / "out.h5"
        physics = _physics(2.0)
        svc = H5ExportStorageService(physics)
        svc.write(out, [_make_cluster(energy=5.0)], _provenance(), CancelToken())

        with h5py.File(out, "r") as f:
            ds = f["clusters"]
            assert tuple(ds.dtype.names) == EXPECTED_COLUMN_ORDER
            row = ds[0]
            assert row["cluster_id"] == 42
            assert row["energy_adu"] == pytest.approx(5.0)
            assert row["energy_kev"] == pytest.approx(physics.adu_to_kev(5.0))
            # Reserved per-model labels default to UNCLASSIFIED until #36.
            assert row["cnn_particle_type"].decode() == "UNCLASSIFIED"
            assert row["bdt_particle_type"].decode() == "UNCLASSIFIED"
            assert row["nrg_particle_type"].decode() == "UNCLASSIFIED"

    def test_export_info_attrs_populated(self, tmp_path: Path) -> None:
        out = tmp_path / "out.h5"
        H5ExportStorageService(_physics(1.0e-5)).write(
            out, [_make_cluster()], _provenance(), CancelToken()
        )
        with h5py.File(out, "r") as f:
            info = f["export_info"].attrs
            assert info["app_version"] == "0.0.2"
            assert info["filter_json"] == '{"min_sigma_x": 0.5}'
            assert info["calibration_pedestal_width"] == 1400
            assert info["hostname"] == "test-host"
            assert info["machine_id"] == "aa:bb:cc:dd:ee:ff"
            assert list(info["column_order"]) == list(EXPECTED_COLUMN_ORDER)

    def test_none_data_omits_image_and_does_not_crash(self, tmp_path: Path) -> None:
        out = tmp_path / "out.h5"
        cluster = _make_cluster()
        cluster.data = None
        svc = H5ExportStorageService(_physics(1.0e-5))

        svc.write(out, [cluster], _provenance(), CancelToken())

        assert out.exists()
        with h5py.File(out, "r") as f:
            assert "clusters" in f
            # Image skipped — key must not be present
            assert "42" not in f["images"]

    def test_cancel_midway_leaves_no_partial_file(self, tmp_path: Path) -> None:
        out = tmp_path / "out.h5"
        token = CancelToken()
        token.cancel()  # pre-cancel — first iteration bails
        svc = H5ExportStorageService(_physics(1.0e-5))

        with pytest.raises(Exception):
            svc.write(out, [_make_cluster()], _provenance(), token)

        assert not out.exists()
        assert not out.with_suffix(out.suffix + ".partial").exists()
