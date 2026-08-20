# Citation for Unit Tests: ZMQBasedEventRepository formatting and mock data constraints
# Date: 03/02/2026
# Adapted from Claude Code:
# Write unit tests for ZMQBasedEventRepository ensuring to cover all endpoints and edge cases
"""Tests for ZMQBasedEventRepository.

Uses mock ZMQ context/sockets — no real IPC connections.
"""
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import zmq
from datetime import datetime

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterRecentQueryFilter,
    ClusterStoreRequest,
    EPSClusterRecord,
    FitsClusterQueryFilter,
    FitsQueryFilter,
)
from le_beta_vis.common.ZMQBasedEventRepository import (
    ZMQBasedEventRepository
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _mock_context(recv_json_return=None):
    """Creates a mock zmq.Context whose socket returns *recv_json_return*.

    If *recv_json_return* is a list, the socket will cycle through the
    values on successive ``recv_json`` calls.  This is convenient when a
    single context is used for both cluster and fits requests in tests.
    """
    ctx = MagicMock(spec=zmq.Context)
    sock = MagicMock(spec=zmq.Socket)
    if recv_json_return is not None:
        if isinstance(recv_json_return, list):
            sock.recv_json.side_effect = recv_json_return
        else:
            sock.recv_json.return_value = recv_json_return
    ctx.socket.return_value = sock
    return ctx, sock


def _make_repo(ctx=None, config=None):
    config = config or MockConfigurationService()
    if ctx is None:
        ctx, _ = _mock_context({"result": "success", "clusters": []})
    return ZMQBasedEventRepository(config, context=ctx)


def _await_callback(done: threading.Event) -> None:
    assert done.wait(1.0), "Timed out waiting for async callback"


# -------------------------------------------------------------------
# fetch_events / query_clusters
# -------------------------------------------------------------------


class TestQueryClusters:

    def test_success_returns_clusters(self):
        raw_response = {
            "result": "success",
            "clusters": [
                {
                    "fits_id": 1,
                    "hdu_id": 0,
                    "cluster_id": 10,
                    "bounding_box": {"top": 10, "left": 20, "bottom": 30, "right": 40},
                    "data": [1.0, 2.0, 3.0, 4.0],
                    "total_energy": 500.0,
                    "sigmaX": 1.5,
                    "sigmaY": 2.0,
                    "classification": "tritium",
                    "total_pixels": 20,
                },
            ],
        }
        ctx, sock = _mock_context([raw_response, {  # first call = cluster, second = fits
            "result": "success",
            "fits": [{"fits_id": 1, "filename": "a.fits", "date": "", "min": 0, "max": 0, "exposure_time": 0}],
        }])
        repo = _make_repo(ctx)
        done = threading.Event()
        got = {"clusters": None, "error": None}

        def on_success(clusters):
            got["clusters"] = clusters
            done.set()

        def on_error(error):
            got["error"] = error
            done.set()

        # Mock extractClusterFromFile to avoid file I/O
        with patch('le_beta_vis.common.CCDCaptureModel.extractClusterFromFile',
                   return_value=np.array([[1, 2], [3, 4]])):
            repo.fetch_events(callback=on_success, on_error=on_error)

        _await_callback(done)

        assert got["error"] is None
        clusters = got["clusters"]
        assert clusters is not None

        assert len(clusters) == 1
        c = clusters[0]
        assert isinstance(c, Cluster)
        assert c.fitsId == 1
        assert c.clusterId == 10
        assert c.energy == 500.0
        assert c.sigmaX == 1.5
        assert c.sigmaY == 2.0
        assert c.pixelCount == 20
        # Classification defaults to 0.0 (EPS sends string)
        assert c.cnnClassification == 0.0

    def test_failure_returns_empty(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        done = threading.Event()
        got = {"clusters": None, "error": None}

        repo.fetch_events(
            callback=lambda clusters: (got.__setitem__("clusters", clusters), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)
        assert got["clusters"] is None
        assert isinstance(got["error"], str)

    def test_zmq_error_returns_empty(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("timeout")
        repo = _make_repo(ctx)
        done = threading.Event()
        got = {"clusters": None, "error": None}

        repo.fetch_events(
            callback=lambda clusters: (got.__setitem__("clusters", clusters), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)
        assert got["clusters"] is not None
        assert got["clusters"] == []
        assert got["error"] is None

    def test_filter_sent_to_socket(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        qf = ClusterQueryFilter(fits_id=42, min_total_energy=100.0)
        done = threading.Event()
        repo.query_clusters(
            qf,
            callback=lambda _: done.set(),
            on_error=lambda _: done.set(),
        )
        _await_callback(done)

        sent = sock.send_json.call_args[0][0]
        assert sent["Action"] == "Retrieval"
        assert sent["fits_id"] == 42
        assert sent["total_energy"] == 100.0

    def test_none_filter_sends_bare_retrieval(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        done = threading.Event()
        repo.query_clusters(
            None,
            callback=lambda _: done.set(),
            on_error=lambda _: done.set(),
        )
        _await_callback(done)

        sent = sock.send_json.call_args[0][0]
        assert sent == {"Action": "Retrieval"}

    def test_fetch_events_emits_deprecation_warning(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        done = threading.Event()

        with pytest.warns(DeprecationWarning):
            repo.fetch_events(
                callback=lambda _: done.set(),
                on_error=lambda _: done.set(),
            )
        _await_callback(done)


# -------------------------------------------------------------------
# fetch_clusters / fetch_clusters_sync (PagedRetrieval action, issue #147)
# -------------------------------------------------------------------


class TestFetchClusters:

    def test_success_returns_clusters(self):
        raw_response = {
            "result": "success",
            "clusters": [
                {
                    "fits_id": 1,
                    "hdu_id": 0,
                    "cluster_id": 10,
                    "bounding_box": {"top": 10, "left": 20, "bottom": 30, "right": 40},
                    "data": None,
                    "total_energy": 500.0,
                    "sigmaX": 1.5,
                    "sigmaY": 2.0,
                    "classification": "tritium",
                    "total_pixels": 20,
                    "filename": "a.fits",
                    "date": "2026-01-01",
                },
            ],
            "limit": 10,
            "offset": 0,
        }
        ctx, sock = _mock_context(raw_response)
        repo = _make_repo(ctx)

        clusters = repo.fetch_clusters_sync(limit=10, offset=0)

        assert len(clusters) == 1
        assert clusters[0].fitsId == 1
        assert clusters[0].clusterId == 10
        assert clusters[0].energy == 500.0

    def test_failure_raises(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)

        with pytest.raises(Exception):
            repo.fetch_clusters_sync(limit=10, offset=0)

    def test_zmq_error_returns_empty(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("timeout")
        repo = _make_repo(ctx)

        assert repo.fetch_clusters_sync(limit=10, offset=0) == []

    def test_default_limit_injected_from_config(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        config = MockConfigurationService()
        config._store["eps:retrieval_limit_default"] = 250
        repo = _make_repo(ctx, config=config)

        repo.fetch_clusters_sync()

        sent = sock.send_json.call_args[0][0]
        assert sent["Action"] == "PagedRetrieval"
        assert sent["limit"] == 250
        assert sent["offset"] == 0

    def test_explicit_limit_overrides_default(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        config = MockConfigurationService()
        config._store["eps:retrieval_limit_default"] = 250
        repo = _make_repo(ctx, config=config)

        repo.fetch_clusters_sync(limit=5, offset=15)

        sent = sock.send_json.call_args[0][0]
        assert sent["limit"] == 5
        assert sent["offset"] == 15

    def test_filter_merged_into_request(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        qf = ClusterQueryFilter(fits_id=42, classification="tritium")

        repo.fetch_clusters_sync(query_filter=qf, limit=10, offset=0)

        sent = sock.send_json.call_args[0][0]
        assert sent["Action"] == "PagedRetrieval"
        assert sent["fits_id"] == 42
        assert sent["classification"] == "tritium"

    def test_async_fetch_clusters_invokes_callback(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        done = threading.Event()
        got = {"clusters": None}

        repo.fetch_clusters(
            query_filter=None,
            limit=10,
            offset=0,
            callback=lambda clusters: (got.__setitem__("clusters", clusters), done.set()),
            on_error=lambda _: done.set(),
        )
        _await_callback(done)

        assert got["clusters"] == []


# -------------------------------------------------------------------
# query_recent_clusters (RecentRetrieval action)
# -------------------------------------------------------------------


class TestQueryRecentClusters:
    """Validates the new RecentRetrieval endpoint wire format and parsing."""

    def test_sends_recent_retrieval_with_limit_and_offset(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)

        repo.query_recent_clusters_sync(limit=25, offset=50)

        sent = sock.send_json.call_args[0][0]
        expected = ClusterRecentQueryFilter(limit=25, offset=50).to_eps_dict()
        assert sent == expected
        assert sent["Action"] == "RecentRetrieval"

    def test_default_offset_is_zero(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)

        repo.query_recent_clusters_sync(limit=10)

        sent = sock.send_json.call_args[0][0]
        assert sent["offset"] == 0

    def test_response_parsed_via_dataclass(self):
        """Clusters are built from EPSClusterRecord, not raw dicts."""
        raw = {
            "fits_id": 7,
            "hdu_id": 0,
            "cluster_id": 101,
            "bounding_box": {"top": 1, "left": 2, "bottom": 3, "right": 4},
            "data": [1.0, 2.0, 3.0, 4.0],
            "total_energy": 1234.0,
            "sigmaX": 1.1,
            "sigmaY": 2.2,
            "classification": "tritium",
            "total_pixels": 12,
            "filename": "newest.fits",
            "date": "2026-04-14",
        }
        record = EPSClusterRecord.from_eps_dict(raw)
        ctx, sock = _mock_context({"result": "success", "clusters": [raw]})
        repo = _make_repo(ctx)

        clusters = repo.query_recent_clusters_sync(limit=1)

        assert len(clusters) == 1
        c = clusters[0]
        assert c.clusterId == record.cluster_id == 101
        assert c.fitsId == record.fits_id == 7
        assert c.energy == record.total_energy == 1234.0
        assert c.fitsFilename == record.filename == "newest.fits"
        assert c.date == record.date == "2026-04-14"

    def test_failure_returns_empty(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        assert repo.query_recent_clusters_sync(limit=5) == []

    def test_zmq_error_returns_empty(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("timeout")
        repo = _make_repo(ctx)
        assert repo.query_recent_clusters_sync(limit=5) == []


# -------------------------------------------------------------------
# Date filter wiring (issue #146)
# -------------------------------------------------------------------


class TestDateFilterWiring:
    """End-to-end check that datetime objects survive ClusterQueryFilter
    construction, get serialized to MySQL DATETIME literal format, and
    arrive at the ZMQ socket as plain strings inside the JSON payload."""

    def test_date_filter_sent_as_strftime_strings(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        qf = ClusterQueryFilter(
            date_start=datetime(2025, 1, 1, 8, 0, 0),
            date_end=datetime(2025, 12, 31, 23, 59, 59),
        )
        done = threading.Event()
        repo.query_clusters(
            qf,
            callback=lambda _: done.set(),
            on_error=lambda _: done.set(),
        )
        _await_callback(done)

        sent = sock.send_json.call_args[0][0]
        assert sent["date"] == {
            "start": "2025-01-01 08:00:00",
            "end": "2025-12-31 23:59:59",
        }

    def test_no_date_filter_omits_date_key(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        done = threading.Event()
        repo.query_clusters(
            ClusterQueryFilter(fits_id=1),
            callback=lambda _: done.set(),
            on_error=lambda _: done.set(),
        )
        _await_callback(done)

        sent = sock.send_json.call_args[0][0]
        assert "date" not in sent


# -------------------------------------------------------------------
# store_cluster
# -------------------------------------------------------------------


class TestStoreCluster:

    def test_success_returns_id(self):
        ctx, sock = _mock_context({"result": "success", "cluster_id": 99})
        repo = _make_repo(ctx)
        req = ClusterStoreRequest(
            data=[1, 2],
            hdu_id=0,
            bounding_box={"top": 0, "left": 0, "bottom": 3, "right": 3},
            sigma_x=1.0,
            sigma_y=1.0,
            total_energy=50.0,
            total_pixels=4,
            fits_id=1,
        )
        result = repo.store_cluster(req)
        assert result == 99

    def test_failure_returns_none(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        req = ClusterStoreRequest(
            data=[],
            hdu_id=0,
            bounding_box={},
            sigma_x=0.0,
            sigma_y=0.0,
            total_energy=0.0,
            total_pixels=0,
            fits_id=0,
        )
        assert repo.store_cluster(req) is None


# -------------------------------------------------------------------
# update_classification
# -------------------------------------------------------------------


class TestUpdateClassification:

    def test_success_invokes_callback(self):
        ctx, sock = _mock_context({"result": "success"})
        repo = _make_repo(ctx)
        req = ClassificationUpdateRequest(cluster_id=1, classification="muon")
        done = threading.Event()
        got = {"updated": None, "error": None}

        repo.update_classification(
            req,
            callback=lambda updated: (got.__setitem__("updated", updated), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)
        assert got["updated"] is True
        assert got["error"] is None

    def test_failure_invokes_error(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        req = ClassificationUpdateRequest(cluster_id=1, classification="muon")
        done = threading.Event()
        got = {"updated": None, "error": None}

        repo.update_classification(
            req,
            callback=lambda updated: (got.__setitem__("updated", updated), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)
        assert got["updated"] is None
        assert isinstance(got["error"], str)

    def test_zmq_error_invokes_error(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("down")
        repo = _make_repo(ctx)
        req = ClassificationUpdateRequest(cluster_id=1, classification="muon")
        done = threading.Event()
        got = {"updated": None, "error": None}

        repo.update_classification(
            req,
            callback=lambda updated: (got.__setitem__("updated", updated), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)
        assert got["updated"] is None
        assert isinstance(got["error"], str)


# -------------------------------------------------------------------
# query_fits
# -------------------------------------------------------------------


class TestQueryFits:

    def test_success_returns_records(self):
        ctx, sock = _mock_context(
            {
                "result": "success",
                "fits": [
                    {
                        "fits_id": 5,
                        "filename": "a.fits",
                        "date": "2025-01-01",
                        "min": 0.0,
                        "max": 100.0,
                        "exposure_time": 60.0,
                    },
                ],
            }
        )
        repo = _make_repo(ctx)
        done = threading.Event()
        got = {"records": None, "error": None}

        repo.query_fits(
            FitsQueryFilter(fits_id=5),
            callback=lambda records: (got.__setitem__("records", records), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)

        assert got["error"] is None
        records = got["records"]
        assert records is not None
        assert len(records) == 1
        assert records[0].fits_id == 5
        assert records[0].filename == "a.fits"

    def test_failure_invokes_error(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        done = threading.Event()
        got = {"records": None, "error": None}

        repo.query_fits(
            None,
            callback=lambda records: (got.__setitem__("records", records), done.set()),
            on_error=lambda error: (got.__setitem__("error", error), done.set()),
        )
        _await_callback(done)
        assert got["records"] is None
        assert isinstance(got["error"], str)


# -------------------------------------------------------------------
# Domain mapping
# -------------------------------------------------------------------


class TestMapToCluster:

    def test_data_and_center_always_none(self):
        """_map_to_cluster never populates data or center — deferred to thumbnail loader."""
        record = EPSClusterRecord(
            fits_id=1, hdu_id=0, cluster_id=1,
            fits_list=None,
            bounding_box={"top": 1, "left": 2, "bottom": 4, "right": 5},
            data=[0, 0, 0, 0, 0, 99, 0, 0, 0],
            total_energy=99.0, sigma_x=1.5, sigma_y=2.0,
            classification="tritium",
            cnn_classification=0.0, nrg_classification=0.0, bdt_classification=0.0,
            total_pixels=9,
            filename="test.fits", date="2026-03-12",
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record, record.filename, record.date)
        assert cluster is not None
        assert cluster.data is None
        assert cluster.centerX is None
        assert cluster.centerY is None
        assert cluster.energy == 99.0
        assert cluster.sigmaX == 1.5
        assert cluster.sigmaY == 2.0
        assert cluster.pixelCount == 9
        assert cluster.fitsId == 1
        assert cluster.clusterId == 1
        assert cluster.fitsFilename == "test.fits"
        assert cluster.date == "2026-03-12"

    def test_bounding_box_from_shape(self):
        data = list(range(16))  # 4x4
        record = EPSClusterRecord(
            fits_id=1,
            fits_list=None,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 4, "right": 4},
            data=data,
            total_energy=120.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="",
            cnn_classification=0.0,
            nrg_classification=0.0,
            bdt_classification=0.0,
            total_pixels=16,
            filename="test.fits",
            date="2026-03-12",
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record, record.filename, record.date)
        assert cluster is not None
        bb = cluster.boundingBox
        assert bb.top == 0
        assert bb.left == 0
        assert bb.bottom == 4
        assert bb.right == 4

    def test_classification_scores_pass_through(self):
        """Regression test: real per-model scores stored in EPS must reach the domain
        Cluster, not be silently zeroed on retrieval."""
        record = EPSClusterRecord(
            fits_id=1,
            fits_list=None,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 2, "right": 2},
            data=[1.0, 4.0, 9.0, 16.0],
            total_energy=30.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="tritium",
            cnn_classification=0.83,
            nrg_classification=0.42,
            bdt_classification=0.91,
            total_pixels=4,
            filename="test.fits",
            date="2026-03-12",
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record, record.filename, record.date)
        assert cluster is not None
        assert cluster.cnnClassification == 0.83
        assert cluster.nrgClassification == 0.42
        assert cluster.bdtClassification == 0.91

    def test_classification_scores_none_coerced_to_zero(self):
        """Belt-and-suspenders: a record built with None scores (nullable DB columns)
        must still map to 0.0, never None, on the domain Cluster."""
        record = EPSClusterRecord(
            fits_id=1,
            fits_list=None,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 2, "right": 2},
            data=[1.0, 4.0, 9.0, 16.0],
            total_energy=30.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="tritium",
            cnn_classification=None,
            nrg_classification=None,
            bdt_classification=None,
            total_pixels=4,
            filename="test.fits",
            date="2026-03-12",
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record, record.filename, record.date)
        assert cluster is not None
        assert cluster.cnnClassification == 0.0
        assert cluster.nrgClassification == 0.0
        assert cluster.bdtClassification == 0.0

    def test_empty_bbox_returns_cluster(self):
        """Zero-area bounding box still produces a valid cluster."""
        record = EPSClusterRecord(
            fits_id=1, hdu_id=0, cluster_id=1,
            fits_list=None,
            bounding_box={"top": 0, "left": 0, "bottom": 0, "right": 0},
            data=[], total_energy=0.0, sigma_x=0.0, sigma_y=0.0,
            classification="",
            cnn_classification=0.0, nrg_classification=0.0, bdt_classification=0.0,
            total_pixels=0,
            filename="test.fits", date="2026-03-12",
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record, record.filename, record.date)
        assert cluster is not None
        assert cluster.data is None
        assert cluster.boundingBox.top == 0
        assert cluster.boundingBox.bottom == 0

    def test_record_data_type_ignored(self):
        """record.data is ignored regardless of type (bytes, list, etc.)."""
        arr = np.array([1.0, 4.0, 9.0, 16.0], dtype=np.float64)
        record = EPSClusterRecord(
            fits_id=1, hdu_id=0, cluster_id=1,
            fits_list=None,
            bounding_box={"top": 0, "left": 0, "bottom": 2, "right": 2},
            data=arr.tobytes(), total_energy=30.0,
            sigma_x=1.0, sigma_y=1.0,
            classification="",
            cnn_classification=0.0, nrg_classification=0.0, bdt_classification=0.0,
            total_pixels=4,
            filename="test.fits", date="2026-03-12",
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record, record.filename, record.date)
        assert cluster is not None
        assert cluster.data is None


# -------------------------------------------------------------------
# Socket lifecycle
# -------------------------------------------------------------------


class TestSocketLifecycle:

    def test_socket_closed_after_request(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        done = threading.Event()
        repo.fetch_events(callback=lambda _: done.set(), on_error=lambda _: done.set())
        _await_callback(done)
        sock.close.assert_called_once()

    def test_socket_closed_on_error(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("fail")
        repo = _make_repo(ctx)
        done = threading.Event()
        repo.fetch_events(callback=lambda _: done.set(), on_error=lambda _: done.set())
        _await_callback(done)
        sock.close.assert_called_once()

    def test_linger_set_to_zero(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        done = threading.Event()
        repo.fetch_events(callback=lambda _: done.set(), on_error=lambda _: done.set())
        _await_callback(done)
        sock.setsockopt.assert_any_call(zmq.LINGER, 0)

    def test_timeout_from_config(self):
        config = MockConfigurationService()
        config.set("eps:timeout_ms", 9999)
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = ZMQBasedEventRepository(config, context=ctx)
        done = threading.Event()
        repo.fetch_events(callback=lambda _: done.set(), on_error=lambda _: done.set())
        _await_callback(done)
        sock.setsockopt.assert_any_call(zmq.RCVTIMEO, 9999)
        sock.setsockopt.assert_any_call(zmq.SNDTIMEO, 9999)
