"""Headless unit tests for backend file ingestion pipeline functions."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import zmq

from le_beta_vis.backend.FileProcessing import (
    cluster_fits,
    process_file,
    store_cluster,
    store_fits,
)
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from mock_configuration_service import MockConfigurationService


def _make_capture_info(min_val, max_val, date="2026-01-01", exposure="1.0"):
    info = MagicMock()
    info.min = min_val
    info.max = max_val
    info.captureDate.return_value = date
    info.exposureDuration.return_value = exposure
    return info


def _make_hdu(raw_data, info):
    hdu = MagicMock()
    hdu.rawData.return_value = raw_data
    hdu.info.return_value = info
    return hdu


def _make_config():
    config = MockConfigurationService()
    config.set("global:physics:kev_conversion", 1.0)
    config.set("global:physics:ped_width", 1.0)
    config.set("eps:fits_ipc", "ipc:///tmp/test-fits.ipc")
    config.set("eps:cluster_ipc", "ipc:///tmp/test-cluster.ipc")
    return config


class TestProcessFile:
    @patch("le_beta_vis.backend.FileProcessing.cluster_fits")
    @patch("le_beta_vis.backend.FileProcessing.store_fits")
    @patch("le_beta_vis.backend.FileProcessing.CCDCaptureModel.load")
    @patch("le_beta_vis.backend.FileProcessing.zmq.Context")
    def test_process_file_passes_context_between_functions(
        self,
        mock_context_class,
        mock_load,
        mock_store_fits,
        mock_cluster_fits,
    ):
        config = _make_config()
        capture = [MagicMock()]
        zmq_context = MagicMock(spec=["term"])

        mock_context_class.return_value = zmq_context
        mock_load.return_value = capture
        mock_store_fits.return_value = 42

        process_file(config_service=config, file="test.fits")

        mock_load.assert_called_once_with("test.fits")
        mock_store_fits.assert_called_once_with(
            zmq_context,
            config,
            "test.fits",
            capture,
            None,
            1.0,
            1.0,
        )
        mock_cluster_fits.assert_called_once_with(
            zmq_context,
            config,
            capture,
            42,
            1.0,
            1.0,
        )
        zmq_context.term.assert_called_once()

    @patch("le_beta_vis.backend.FileProcessing.store_fits", side_effect=RuntimeError("boom"))
    @patch("le_beta_vis.backend.FileProcessing.CCDCaptureModel.load", return_value=[])
    @patch("le_beta_vis.backend.FileProcessing.zmq.Context")
    def test_process_file_terminates_context_on_error(
        self,
        mock_context_class,
        _mock_load,
        _mock_store_fits,
    ):
        config = _make_config()
        zmq_context = MagicMock(spec=["term"])
        mock_context_class.return_value = zmq_context
        with pytest.raises(RuntimeError):
            process_file(config_service=config, file="bad.fits")

        zmq_context.term.assert_called_once()


class TestStoreFits:
    def test_store_fits_success_sends_expected_payload(self):
        config = _make_config()

        capture = [
            _make_hdu(np.zeros((2, 2)), _make_capture_info(10.0, 30.0)),
            _make_hdu(np.zeros((2, 2)), _make_capture_info(20.0, 25.0)),
            _make_hdu(np.zeros((2, 2)), _make_capture_info(15.0, 40.0)),
            _make_hdu(np.zeros((2, 2)), _make_capture_info(12.0, 35.0)),
        ]

        socket = MagicMock(spec=zmq.Socket)
        socket.recv_json.return_value = {"result": "success", "fits_id": 99}

        context = MagicMock(spec=zmq.Context)
        context.socket.return_value = socket

        fits_id = store_fits(
            process_context=context,
            config=config,
            fits_name="capture.fits",
            capture=capture,
            fits_id=None,
            kev=1.0,
            ped_width=1.0,
        )

        assert fits_id == 99
        socket.connect.assert_called_once_with("ipc:///tmp/test-fits.ipc")
        sent_payload = socket.send_json.call_args.args[0]
        assert sent_payload["Action"] == "Storage"
        assert sent_payload["filename"] == "capture.fits"
        assert sent_payload["minimum"] == 10.0
        assert sent_payload["maximum"] == 40.0
        socket.close.assert_called_once()

    def test_store_fits_failure_returns_none(self):
        config = _make_config()
        capture = [_make_hdu(np.zeros((2, 2)), _make_capture_info(1.0, 2.0))] * 4

        socket = MagicMock(spec=zmq.Socket)
        socket.recv_json.return_value = {"result": "failure", "error": "db down"}

        context = MagicMock(spec=zmq.Context)
        context.socket.return_value = socket

        assert (
            store_fits(
                process_context=context,
                config=config,
                fits_name="capture.fits",
                capture=capture,
                fits_id=None,
                kev=1.0,
                ped_width=1.0,
            )
            is None
        )
        socket.close.assert_called_once()

    def test_store_fits_zmq_exception_is_handled(self):
        config = _make_config()
        capture = [_make_hdu(np.zeros((2, 2)), _make_capture_info(1.0, 2.0))] * 4

        socket = MagicMock(spec=zmq.Socket)
        socket.send_json.side_effect = zmq.ZMQError("timeout")

        context = MagicMock(spec=zmq.Context)
        context.socket.return_value = socket

        assert (
            store_fits(
                process_context=context,
                config=config,
                fits_name="capture.fits",
                capture=capture,
                fits_id=None,
                kev=1.0,
                ped_width=1.0,
            )
            is None
        )
        socket.close.assert_called_once()


class TestClusterFits:
    @patch("le_beta_vis.backend.FileProcessing.store_cluster")
    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(6, 6))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_creates_common_cluster_and_stores(
        self,
        mock_label,
        _mock_maximum_position,
        _mock_sigmas,
        mock_store_cluster,
    ):
        config = _make_config()
        data = np.zeros((12, 12), dtype=float)
        data[6, 6] = 2.0

        labeled = np.zeros((12, 12), dtype=int)
        labeled[6, 6] = 1
        mock_label.return_value = (labeled, 1)

        hdu = _make_hdu(data, _make_capture_info(0.0, 2.0))

        cluster_fits(
            process_context=MagicMock(spec=zmq.Context),
            config=config,
            capture=[hdu],
            fits_id=7,
            kev=1.0,
            ped_width=1.0,
        )

        assert mock_store_cluster.call_count == 1
        sent_cluster = mock_store_cluster.call_args.args[2]
        assert isinstance(sent_cluster, Cluster)
        assert sent_cluster.fitsId == 7
        assert sent_cluster.hdu_id == 0
        assert sent_cluster.energy == pytest.approx(2.0)
        assert sent_cluster.pixelCount == 1

    @patch("le_beta_vis.backend.FileProcessing.store_cluster")
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(2, 2))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_skips_low_energy_clusters(
        self,
        mock_label,
        _mock_maximum_position,
        mock_store_cluster,
    ):
        config = _make_config()
        data = np.zeros((6, 6), dtype=float)
        data[2, 2] = 0.1

        labeled = np.zeros((6, 6), dtype=int)
        labeled[2, 2] = 1
        mock_label.return_value = (labeled, 1)

        hdu = _make_hdu(data, _make_capture_info(0.0, 1.0))

        cluster_fits(
            process_context=MagicMock(spec=zmq.Context),
            config=config,
            capture=[hdu],
            fits_id=7,
            kev=1.0,
            ped_width=1.0,
        )

        mock_store_cluster.assert_not_called()

    @patch("le_beta_vis.backend.FileProcessing.store_cluster")
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", side_effect=Exception("bad max"))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_skips_cluster_when_maximum_position_fails(
        self,
        mock_label,
        _mock_maximum_position,
        mock_store_cluster,
    ):
        config = _make_config()
        data = np.zeros((6, 6), dtype=float)
        data[2, 2] = 2.0

        labeled = np.zeros((6, 6), dtype=int)
        labeled[2, 2] = 1
        mock_label.return_value = (labeled, 1)

        hdu = _make_hdu(data, _make_capture_info(0.0, 2.0))

        cluster_fits(
            process_context=MagicMock(spec=zmq.Context),
            config=config,
            capture=[hdu],
            fits_id=7,
            kev=1.0,
            ped_width=1.0,
        )

        mock_store_cluster.assert_not_called()


class TestStoreCluster:
    def test_store_cluster_success_sets_cluster_id_and_payload(self):
        config = _make_config()

        cluster = Cluster(
            boundingBox=BoundingBox(10, 20, 30, 40),
            data=np.array([[1.0, 2.0], [0.0, 3.0]]),
            centerX=1,
            centerY=1,
            sigmaX=1.0,
            sigmaY=2.0,
            energy=6.0,
            pixelCount=3,
            fitsId=11,
            hdu_id=2,
            classification="UNCLASSIFIED",
        )

        socket = MagicMock(spec=zmq.Socket)
        socket.recv_json.return_value = {"result": "success", "cluster_id": 55}

        context = MagicMock(spec=zmq.Context)
        context.socket.return_value = socket

        store_cluster(config=config, process_context=context, cluster=cluster)

        sent_payload = socket.send_json.call_args.args[0]
        assert sent_payload["Action"] == "Storage"
        assert sent_payload["hdu_id"] == 2
        assert sent_payload["fits_id"] == 11
        assert sent_payload["total_energy"] == 6.0
        assert sent_payload["total_pixels"] == 3
        assert sent_payload["bounding_box"] == {
            "top": 10,
            "left": 20,
            "bottom": 30,
            "right": 40,
        }
        assert cluster.clusterId == 55
        socket.close.assert_called_once()

    def test_store_cluster_failure_does_not_set_cluster_id(self):
        config = _make_config()

        cluster = Cluster(
            boundingBox=BoundingBox(1, 2, 3, 4),
            data=np.array([[1.0]]),
            centerX=0,
            centerY=0,
            fitsId=99,
            hdu_id=0,
        )

        socket = MagicMock(spec=zmq.Socket)
        socket.recv_json.return_value = {"result": "failure", "error": "db down"}

        context = MagicMock(spec=zmq.Context)
        context.socket.return_value = socket

        store_cluster(config=config, process_context=context, cluster=cluster)

        assert cluster.clusterId is None
        socket.close.assert_called_once()
