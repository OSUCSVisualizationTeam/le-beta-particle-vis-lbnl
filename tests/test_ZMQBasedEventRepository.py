# Citation for Unit Tests: ZMQBasedEventRepository formatting and mock data constraints
# Date: 03/02/2026
# Adapted from Claude Code:
# Write unit tests for ZMQBasedEventRepository ensuring to cover all endpoints and edge cases
"""Tests for ZMQBasedEventRepository.

Uses mock ZMQ context/sockets — no real IPC connections.
"""
import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import zmq

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    EPSClusterRecord,
    FitsQueryFilter,
)
from le_beta_vis.common.ZMQBasedEventRepository import (
    ZMQBasedEventRepository
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _mock_context(recv_json_return=None):
    """Creates a mock zmq.Context whose socket returns *recv_json_return*."""
    ctx = MagicMock(spec=zmq.Context)
    sock = MagicMock(spec=zmq.Socket)
    if recv_json_return is not None:
        sock.recv_json.return_value = recv_json_return
    ctx.socket.return_value = sock
    return ctx, sock


def _make_repo(ctx=None, config=None):
    config = config or MockConfigurationService()
    if ctx is None:
        ctx, _ = _mock_context({"result": "success", "clusters": []})
    return ZMQBasedEventRepository(config, context=ctx)


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
        ctx, sock = _mock_context(raw_response)
        repo = _make_repo(ctx)

        clusters = repo.fetch_events()

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
        assert repo.fetch_events() == []

    def test_zmq_error_returns_empty(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("timeout")
        repo = _make_repo(ctx)
        assert repo.fetch_events() == []

    def test_filter_sent_to_socket(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        qf = ClusterQueryFilter(fits_id=42, min_total_energy=100.0)
        repo.query_clusters(qf)

        sent = sock.send_json.call_args[0][0]
        assert sent["Action"] == "Retrieval"
        assert sent["fits_id"] == 42
        assert sent["total_energy"] == 100.0

    def test_none_filter_sends_bare_retrieval(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        repo.query_clusters(None)

        sent = sock.send_json.call_args[0][0]
        assert sent == {"Action": "Retrieval"}


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

    def test_success_returns_true(self):
        ctx, sock = _mock_context({"result": "success"})
        repo = _make_repo(ctx)
        req = ClassificationUpdateRequest(cluster_id=1, classification="muon")
        assert repo.update_classification(req) is True

    def test_failure_returns_false(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        req = ClassificationUpdateRequest(cluster_id=1, classification="muon")
        assert repo.update_classification(req) is False

    def test_zmq_error_returns_false(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("down")
        repo = _make_repo(ctx)
        req = ClassificationUpdateRequest(cluster_id=1, classification="muon")
        assert repo.update_classification(req) is False


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
        records = repo.query_fits(FitsQueryFilter(fits_id=5))
        assert len(records) == 1
        assert records[0].fits_id == 5
        assert records[0].filename == "a.fits"

    def test_failure_returns_empty(self):
        ctx, sock = _mock_context({"result": "failure"})
        repo = _make_repo(ctx)
        assert repo.query_fits() == []


# -------------------------------------------------------------------
# Domain mapping
# -------------------------------------------------------------------


class TestMapToCluster:

    def test_square_data_reshape(self):
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 2, "right": 2},
            data=[1.0, 2.0, 3.0, 4.0],
            total_energy=10.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="",
            total_pixels=4,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        assert cluster.data.shape == (2, 2)

    def test_non_square_data_becomes_1_row(self):
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 1, "right": 3},
            data=[1.0, 2.0, 3.0],
            total_energy=6.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="",
            total_pixels=3,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        assert cluster.data.shape == (1, 3)

    def test_center_is_brightest_pixel(self):
        # 3x3 grid, brightest at position (1, 2)
        data = [0, 0, 0, 0, 0, 99, 0, 0, 0]
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 1, "left": 2, "bottom": 2, "right": 3},
            data=data,
            total_energy=99.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="",
            total_pixels=9,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        assert cluster.centerX == 2
        assert cluster.centerY == 1

    def test_bounding_box_from_shape(self):
        data = list(range(16))  # 4x4
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 4, "right": 4},
            data=data,
            total_energy=120.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="",
            total_pixels=16,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        bb = cluster.boundingBox
        assert bb.top == 0
        assert bb.left == 0
        assert bb.bottom == 4
        assert bb.right == 4

    def test_classification_scores_default_to_zero(self):
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 2, "right": 2},
            data=[1.0, 4.0, 9.0, 16.0],
            total_energy=30.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="tritium",
            total_pixels=4,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        assert cluster.cnnClassification == 0.0
        assert cluster.nrgClassification == 0.0
        assert cluster.bdtClassification == 0.0

    def test_empty_data_returns_cluster(self):
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 0, "right": 0},
            data=[],
            total_energy=0.0,
            sigma_x=0.0,
            sigma_y=0.0,
            classification="",
            total_pixels=0,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        assert cluster.data.shape == (0, 0)

    def test_bytes_data_parsed(self):
        arr = np.array([1.0, 4.0, 9.0, 16.0], dtype=np.float64)
        raw_bytes = arr.tobytes()
        record = EPSClusterRecord(
            fits_id=1,
            hdu_id=0,
            cluster_id=1,
            bounding_box={"top": 0, "left": 0, "bottom": 2, "right": 2},
            data=raw_bytes,
            total_energy=30.0,
            sigma_x=1.0,
            sigma_y=1.0,
            classification="",
            total_pixels=4,
        )
        cluster = ZMQBasedEventRepository._map_to_cluster(record)
        assert cluster is not None
        assert cluster.data.shape == (2, 2)
        np.testing.assert_array_almost_equal(cluster.data, arr.reshape(2, 2))



# -------------------------------------------------------------------
# Socket lifecycle
# -------------------------------------------------------------------


class TestSocketLifecycle:

    def test_socket_closed_after_request(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        repo.fetch_events()
        sock.close.assert_called_once()

    def test_socket_closed_on_error(self):
        ctx, sock = _mock_context()
        sock.send_json.side_effect = zmq.ZMQError("fail")
        repo = _make_repo(ctx)
        repo.fetch_events()
        sock.close.assert_called_once()

    def test_linger_set_to_zero(self):
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = _make_repo(ctx)
        repo.fetch_events()
        sock.setsockopt.assert_any_call(zmq.LINGER, 0)

    def test_timeout_from_config(self):
        config = MockConfigurationService()
        config.set("eps:timeout_ms", 9999)
        ctx, sock = _mock_context({"result": "success", "clusters": []})
        repo = ZMQBasedEventRepository(config, context=ctx)
        repo.fetch_events()
        sock.setsockopt.assert_any_call(zmq.RCVTIMEO, 9999)
        sock.setsockopt.assert_any_call(zmq.SNDTIMEO, 9999)
