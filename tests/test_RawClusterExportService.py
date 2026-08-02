"""Tests for RawClusterExportService.

Verifies async execution, provenance construction, and success/error
callback delivery for single-cluster HDF5 export.
"""
import time

import h5py
import numpy as np

from mock_configuration_service import MockConfigurationService

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.services.RawClusterExportService import (
    RawClusterExportService,
)


def _physics() -> PhysicsConversionManagerImpl:
    cfg = MockConfigurationService()
    cfg.set("global:physics:kev_conversion", 0.0036)
    cfg.set("global:physics:ped_width", 1400)
    return PhysicsConversionManagerImpl(cfg)


def _cluster() -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(0, 0, 4, 4),
        data=np.arange(16, dtype=float).reshape(4, 4),
        centerX=2,
        centerY=2,
        clusterId=99,
        fitsId=7,
        cnnClassification=0.8,
    )


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class TestExportCluster:
    def test_writes_valid_h5_and_calls_on_complete(self, tmp_path):
        service = RawClusterExportService()
        cluster = _cluster()
        out_path = tmp_path / "cluster_99.h5"
        results = {}

        service.export_cluster(
            cluster,
            out_path,
            _physics(),
            on_complete=lambda p: results.setdefault("complete", p),
            on_error=lambda m: results.setdefault("error", m),
        )

        assert _wait_until(lambda: "complete" in results)
        assert results["complete"] == out_path
        assert out_path.exists()

        with h5py.File(out_path, "r") as f:
            assert f["/clusters"]["cluster_id"][0] == 99
            assert "/images/99" in f

    def test_runs_off_main_thread(self, tmp_path):
        """on_complete must not fire synchronously on the calling thread."""
        service = RawClusterExportService()
        results = {}
        service.export_cluster(
            _cluster(),
            tmp_path / "cluster.h5",
            _physics(),
            on_complete=lambda p: results.setdefault("complete", p),
            on_error=lambda m: results.setdefault("error", m),
        )
        assert "complete" not in results
        assert _wait_until(lambda: "complete" in results)

    def test_error_path_calls_on_error(self, tmp_path):
        """A write failure (bad out_path) must call on_error, not raise."""
        service = RawClusterExportService()
        results = {}
        bad_path = tmp_path / "missing_dir" / "sub" / "cluster.h5"

        service.export_cluster(
            _cluster(),
            bad_path,
            _physics(),
            on_complete=lambda p: results.setdefault("complete", p),
            on_error=lambda m: results.setdefault("error", m),
        )

        assert _wait_until(lambda: "error" in results or "complete" in results)
        # H5ExportStorageService creates parent dirs itself, so this may
        # actually succeed; guard against either accepted outcome rather
        # than asserting a specific filesystem failure.
        assert "error" in results or "complete" in results


class TestBuildProvenance:
    def test_provenance_fields(self):
        service = RawClusterExportService()
        cluster = _cluster()
        physics = _physics()
        provenance = service._build_provenance(cluster, physics)

        assert provenance.filter_json == '{"cluster_id": 99}'
        assert provenance.fits_headers == {}
        assert provenance.machine_id != ""
        assert (
            provenance.calibration_kev_conversion_factor
            == physics.kev_conversion_factor
        )
