"""Headless unit tests for backend file ingestion pipeline functions."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import zmq

from le_beta_vis.backend.FileProcessing import (
    cluster_fits,
    process_file,
    store_fits,
)
from le_beta_vis.backend.InMemoryClusterStorageBuffer import InMemoryClusterStorageBuffer
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


def _make_config(buffer_size=None):
    config = MockConfigurationService()
    config.set("global:physics:kev_conversion", 1.0)
    config.set("global:physics:ped_width", 1.0)
    config.set("eps:fits_ipc", "ipc:///tmp/test-fits.ipc")
    config.set("eps:cluster_ipc", "ipc:///tmp/test-cluster.ipc")
    if buffer_size is not None:
        config.set("eps:cluster_storage_buffer_size", buffer_size)
    return config


def _make_context_and_socket():
    socket = MagicMock(spec=zmq.Socket)
    context = MagicMock(spec=zmq.Context)
    context.socket.return_value = socket
    return context, socket


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

        process_file(
            config_service=config,
            file="test.fits",
            cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
        )

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
            InMemoryClusterStorageBuffer,
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
            process_file(
                config_service=config,
                file="bad.fits",
                cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
            )

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
        assert sent_payload["min"] == 10.0
        assert sent_payload["max"] == 40.0
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


def _make_single_cluster_hdu():
    data = np.zeros((12, 12), dtype=float)
    data[6, 6] = 2.0
    labeled = np.zeros((12, 12), dtype=int)
    labeled[6, 6] = 1
    hdu = _make_hdu(data, _make_capture_info(0.0, 2.0))
    return hdu, labeled


def _make_two_cluster_hdu():
    data = np.zeros((14, 14), dtype=float)
    data[6, 6] = 2.0
    data[6, 7] = 2.0
    labeled = np.zeros((14, 14), dtype=int)
    labeled[6, 6] = 1
    labeled[6, 7] = 2
    hdu = _make_hdu(data, _make_capture_info(0.0, 2.0))
    return hdu, labeled


class TestClusterFits:
    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(6, 6))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_creates_cluster_and_flushes_one_bulk_request(
        self,
        mock_label,
        _mock_maximum_position,
        _mock_sigmas,
    ):
        config = _make_config()
        hdu, labeled = _make_single_cluster_hdu()
        mock_label.return_value = (labeled, 1)

        context, socket = _make_context_and_socket()
        socket.recv_json.return_value = {"result": "success", "cluster_ids": [55]}

        created = []

        def _capture(**kwargs):
            c = Cluster(**kwargs)
            created.append(c)
            return c

        with patch("le_beta_vis.backend.FileProcessing.Cluster", side_effect=_capture):
            cluster_fits(
                process_context=context,
                config=config,
                capture=[hdu],
                fits_id=7,
                kev=1.0,
                ped_width=1.0,
                cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
            )

        socket.connect.assert_called_once_with("ipc:///tmp/test-cluster.ipc")
        socket.send_json.assert_called_once()
        sent_payload = socket.send_json.call_args.args[0]
        assert sent_payload["Action"] == "BulkStorage"
        assert len(sent_payload["clusters"]) == 1
        sent_cluster = sent_payload["clusters"][0]
        assert sent_cluster["fits_id"] == 7
        assert sent_cluster["hdu_id"] == 0
        assert sent_cluster["total_energy"] == pytest.approx(2.0)
        assert sent_cluster["total_pixels"] == 1
        socket.close.assert_called_once()

        assert len(created) == 1
        assert created[0].clusterId == 55

    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position")
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_buffer_reaching_capacity_flushes_exactly_once(
        self,
        mock_label,
        mock_maximum_position,
        _mock_sigmas,
    ):
        """A buffer_size equal to the detected cluster count triggers auto-flush via add()."""
        config = _make_config(buffer_size=2)
        hdu, labeled = _make_two_cluster_hdu()
        mock_label.return_value = (labeled, 2)
        mock_maximum_position.side_effect = [(6, 6), (6, 7)]

        context, socket = _make_context_and_socket()
        socket.recv_json.return_value = {"result": "success", "cluster_ids": [101, 102]}

        cluster_fits(
            process_context=context,
            config=config,
            capture=[hdu],
            fits_id=1,
            kev=1.0,
            ped_width=1.0,
            cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
        )

        socket.send_json.assert_called_once()
        sent_payload = socket.send_json.call_args.args[0]
        assert len(sent_payload["clusters"]) == 2

    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position")
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_buffer_larger_than_cluster_count_flushes_once_on_exit(
        self,
        mock_label,
        mock_maximum_position,
        _mock_sigmas,
    ):
        """A buffer_size larger than the detected cluster count still flushes the trailing partial
        batch."""
        config = _make_config(buffer_size=10)
        hdu, labeled = _make_two_cluster_hdu()
        mock_label.return_value = (labeled, 2)
        mock_maximum_position.side_effect = [(6, 6), (6, 7)]

        context, socket = _make_context_and_socket()
        socket.recv_json.return_value = {"result": "success", "cluster_ids": [101, 102]}

        cluster_fits(
            process_context=context,
            config=config,
            capture=[hdu],
            fits_id=1,
            kev=1.0,
            ped_width=1.0,
            cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
        )

        socket.send_json.assert_called_once()
        sent_payload = socket.send_json.call_args.args[0]
        assert len(sent_payload["clusters"]) == 2

    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position")
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_partial_response_assigns_only_the_recovered_cluster_ids(
        self,
        mock_label,
        mock_maximum_position,
        _mock_sigmas,
    ):
        config = _make_config()
        hdu, labeled = _make_two_cluster_hdu()
        mock_label.return_value = (labeled, 2)
        mock_maximum_position.side_effect = [(6, 6), (6, 7)]

        context, socket = _make_context_and_socket()
        socket.recv_json.return_value = {
            "result": "partial", "cluster_ids": [101, None], "error": "1/2 fallback rows failed",
        }

        created = []

        def _capture(**kwargs):
            c = Cluster(**kwargs)
            created.append(c)
            return c

        with patch("le_beta_vis.backend.FileProcessing.Cluster", side_effect=_capture):
            cluster_fits(
                process_context=context,
                config=config,
                capture=[hdu],
                fits_id=1,
                kev=1.0,
                ped_width=1.0,
                cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
            )

        assert len(created) == 2
        assert created[0].clusterId == 101
        assert created[1].clusterId is None

    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(6, 6))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_failure_response_leaves_cluster_id_unset(
        self,
        mock_label,
        _mock_maximum_position,
        _mock_sigmas,
    ):
        config = _make_config()
        hdu, labeled = _make_single_cluster_hdu()
        mock_label.return_value = (labeled, 1)

        context, socket = _make_context_and_socket()
        socket.recv_json.return_value = {"result": "failure", "error": "db down"}

        created = []

        def _capture(**kwargs):
            c = Cluster(**kwargs)
            created.append(c)
            return c

        with patch("le_beta_vis.backend.FileProcessing.Cluster", side_effect=_capture):
            cluster_fits(
                process_context=context,
                config=config,
                capture=[hdu],
                fits_id=1,
                kev=1.0,
                ped_width=1.0,
                cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
            )

        assert len(created) == 1
        assert created[0].clusterId is None

    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(6, 6))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_zmq_error_during_flush_is_caught_logged_and_does_not_propagate(
        self,
        mock_label,
        _mock_maximum_position,
        _mock_sigmas,
    ):
        config = _make_config()
        hdu, labeled = _make_single_cluster_hdu()
        mock_label.return_value = (labeled, 1)

        context, socket = _make_context_and_socket()
        socket.send_json.side_effect = zmq.ZMQError("timeout")

        created = []

        def _capture(**kwargs):
            c = Cluster(**kwargs)
            created.append(c)
            return c

        with patch("le_beta_vis.backend.FileProcessing.Cluster", side_effect=_capture):
            cluster_fits(
                process_context=context,
                config=config,
                capture=[hdu],
                fits_id=1,
                kev=1.0,
                ped_width=1.0,
                cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
            )

        assert len(created) == 1
        assert created[0].clusterId is None
        socket.close.assert_called_once()

    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(2, 2))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_skips_low_energy_clusters(
        self,
        mock_label,
        _mock_maximum_position,
    ):
        config = _make_config()
        data = np.zeros((6, 6), dtype=float)
        data[2, 2] = 0.1

        labeled = np.zeros((6, 6), dtype=int)
        labeled[2, 2] = 1
        mock_label.return_value = (labeled, 1)

        hdu = _make_hdu(data, _make_capture_info(0.0, 1.0))
        context, socket = _make_context_and_socket()

        cluster_fits(
            process_context=context,
            config=config,
            capture=[hdu],
            fits_id=7,
            kev=1.0,
            ped_width=1.0,
            cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
        )

        socket.send_json.assert_not_called()

    @patch("le_beta_vis.backend.FileProcessing.maximum_position", side_effect=Exception("bad max"))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_skips_cluster_when_maximum_position_fails(
        self,
        mock_label,
        _mock_maximum_position,
    ):
        config = _make_config()
        data = np.zeros((6, 6), dtype=float)
        data[2, 2] = 2.0

        labeled = np.zeros((6, 6), dtype=int)
        labeled[2, 2] = 1
        mock_label.return_value = (labeled, 1)

        hdu = _make_hdu(data, _make_capture_info(0.0, 2.0))
        context, socket = _make_context_and_socket()

        cluster_fits(
            process_context=context,
            config=config,
            capture=[hdu],
            fits_id=7,
            kev=1.0,
            ped_width=1.0,
            cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
        )

        socket.send_json.assert_not_called()


class TestClusterStorageBufferInjection:
    """Proves cluster_fits depends on the ClusterStorageBuffer ABC, not a concrete implementation --
    FileProcessing never imports/constructs InMemoryClusterStorageBuffer itself."""

    @patch("le_beta_vis.backend.FileProcessing.compute_cluster_sigmas", return_value=(1.2, 2.3))
    @patch("le_beta_vis.backend.FileProcessing.maximum_position", return_value=(6, 6))
    @patch("le_beta_vis.backend.FileProcessing.label")
    def test_cluster_fits_uses_the_injected_factory(
        self,
        mock_label,
        _mock_maximum_position,
        _mock_sigmas,
    ):
        config = _make_config()
        hdu, labeled = _make_single_cluster_hdu()
        mock_label.return_value = (labeled, 1)
        context, socket = _make_context_and_socket()
        socket.recv_json.return_value = {"result": "success", "cluster_ids": [1]}

        class _FakeBuffer:
            """Minimal ClusterStorageBuffer stand-in with no relation to
            InMemoryClusterStorageBuffer."""

            def __init__(self, capacity, flush_callback):
                self.capacity = capacity
                self.flush_callback = flush_callback
                self.items = []

            def add(self, item):
                self.items.append(item)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None and self.items:
                    self.flush_callback(self.items)
                return False

        built_buffers = []

        def fake_factory(capacity, flush_callback):
            buf = _FakeBuffer(capacity, flush_callback)
            built_buffers.append(buf)
            return buf

        cluster_fits(
            process_context=context,
            config=config,
            capture=[hdu],
            fits_id=7,
            kev=1.0,
            ped_width=1.0,
            cluster_storage_buffer_factory=fake_factory,
        )

        assert len(built_buffers) == 1
        assert built_buffers[0].capacity == 32
        assert len(built_buffers[0].items) == 1
        socket.send_json.assert_called_once()
