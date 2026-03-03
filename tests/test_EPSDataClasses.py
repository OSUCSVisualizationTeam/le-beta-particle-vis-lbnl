"""Tests for EPSDataClasses request/response DTOs.

Pure data-mapping tests — no ZMQ dependency.
"""
from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    EPSClusterRecord,
    EPSFitsRecord,
    FitsQueryFilter,
)


# -------------------------------------------------------------------
# ClusterQueryFilter
# -------------------------------------------------------------------

class TestClusterQueryFilter:

    def test_empty_filter_to_eps_dict(self):
        """An all-None filter should produce only the Action key."""
        qf = ClusterQueryFilter()
        d = qf.to_eps_dict()
        assert d == {"Action": "Retrieval"}

    def test_single_field_maps_correctly(self):
        qf = ClusterQueryFilter(fits_id=42)
        d = qf.to_eps_dict()
        assert d["fits_id"] == 42
        assert d["Action"] == "Retrieval"
        assert "cluster_id" not in d

    def test_all_fields_map_correctly(self):
        qf = ClusterQueryFilter(
            cluster_id=1, fits_id=2, hdu_id=3,
            min_sigma_x=0.5, min_sigma_y=0.6,
            min_total_energy=100.0, min_total_pixels=10,
            classification="tritium",
        )
        d = qf.to_eps_dict()
        assert d["cluster_id"] == 1
        assert d["fits_id"] == 2
        assert d["hdu_id"] == 3
        assert d["sigmaX"] == 0.5
        assert d["sigmaY"] == 0.6
        assert d["total_energy"] == 100.0
        assert d["total_pixels"] == 10
        assert d["classification"] == "tritium"

    def test_frozen(self):
        """ClusterQueryFilter should be immutable."""
        qf = ClusterQueryFilter(fits_id=1)
        try:
            qf.fits_id = 99
            assert False, "Should have raised"
        except AttributeError:
            pass


# -------------------------------------------------------------------
# FitsQueryFilter
# -------------------------------------------------------------------

class TestFitsQueryFilter:

    def test_empty_filter(self):
        d = FitsQueryFilter().to_eps_dict()
        assert d == {"Action": "Retrieval"}

    def test_fits_id_maps(self):
        d = FitsQueryFilter(fits_id=7).to_eps_dict()
        assert d["fits_id"] == 7


# -------------------------------------------------------------------
# ClusterStoreRequest
# -------------------------------------------------------------------

class TestClusterStoreRequest:

    def test_to_eps_dict_action(self):
        req = ClusterStoreRequest(
            data=[1, 2, 3], hdu_id=0,
            bounding_box={"top": 0, "left": 0, "bottom": 5, "right": 5},
            sigma_x=1.0, sigma_y=1.0,
            total_energy=100.0, total_pixels=25,
            fits_id=1, classification="tritium",
        )
        d = req.to_eps_dict()
        assert d["Action"] == "Storage"
        assert d["data"] == [1, 2, 3]
        assert d["fits_id"] == 1
        assert d["sigmaX"] == 1.0
        assert d["classification"] == "tritium"

    def test_default_classification(self):
        req = ClusterStoreRequest(
            data=[], hdu_id=0,
            bounding_box={}, sigma_x=0.0, sigma_y=0.0,
            total_energy=0.0, total_pixels=0, fits_id=0,
        )
        assert req.classification == ""


# -------------------------------------------------------------------
# ClassificationUpdateRequest
# -------------------------------------------------------------------

class TestClassificationUpdateRequest:

    def test_to_eps_dict(self):
        req = ClassificationUpdateRequest(
            cluster_id=42, classification="muon"
        )
        d = req.to_eps_dict()
        assert d["Action"] == "UpdateClassification"
        assert d["cluster_id"] == 42
        assert d["classification"] == "muon"


# -------------------------------------------------------------------
# EPSClusterRecord
# -------------------------------------------------------------------

class TestEPSClusterRecord:

    def test_from_full_dict(self):
        raw = {
            "fits_id": 1, "hdu_id": 2, "cluster_id": 3,
            "data": [1.0, 2.0, 3.0, 4.0],
            "total_energy": 500.0,
            "sigmaX": 1.5, "sigmaY": 2.0,
            "classification": "tritium",
            "total_pixels": 20,
        }
        rec = EPSClusterRecord.from_eps_dict(raw)
        assert rec.fits_id == 1
        assert rec.hdu_id == 2
        assert rec.cluster_id == 3
        assert rec.data == [1.0, 2.0, 3.0, 4.0]
        assert rec.total_energy == 500.0
        assert rec.sigma_x == 1.5
        assert rec.sigma_y == 2.0
        assert rec.classification == "tritium"
        assert rec.total_pixels == 20

    def test_from_empty_dict_uses_defaults(self):
        rec = EPSClusterRecord.from_eps_dict({})
        assert rec.fits_id == 0
        assert rec.cluster_id == 0
        assert rec.total_energy == 0.0
        assert rec.classification == ""
        assert rec.data == []

    def test_from_partial_dict(self):
        raw = {"fits_id": 99, "total_energy": 42.0}
        rec = EPSClusterRecord.from_eps_dict(raw)
        assert rec.fits_id == 99
        assert rec.total_energy == 42.0
        assert rec.hdu_id == 0


# -------------------------------------------------------------------
# EPSFitsRecord
# -------------------------------------------------------------------

class TestEPSFitsRecord:

    def test_from_full_dict(self):
        raw = {
            "fits_id": 5, "filename": "capture.fits",
            "date": "2025-01-01", "min": 0.1,
            "max": 99.9, "exposure_time": 300.0,
        }
        rec = EPSFitsRecord.from_eps_dict(raw)
        assert rec.fits_id == 5
        assert rec.filename == "capture.fits"
        assert rec.date == "2025-01-01"
        assert rec.min_val == 0.1
        assert rec.max_val == 99.9
        assert rec.exposure_time == 300.0

    def test_from_empty_dict_uses_defaults(self):
        rec = EPSFitsRecord.from_eps_dict({})
        assert rec.fits_id == 0
        assert rec.filename == ""
        assert rec.exposure_time == 0.0
