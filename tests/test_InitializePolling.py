import pytest
import queue
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY
import threading
import time

from le_beta_vis.backend.InitializePolling import PollingThread
from le_beta_vis.backend.InitializePolling import EventHandler
from le_beta_vis.backend.InitializePolling import FileWatcher
from le_beta_vis.backend.PollingRunner import PollingRunner
from mock_configuration_service import MockConfigurationService

@pytest.fixture
def mock_config():
    config = MockConfigurationService()
    # Reset config to known state
    config.set("pipeline:ingress:polling_location", "/tmp")
    return config

def test_file_created_queue():
    """
    Tests the event handler to ensure that newly created files are put in the queue.
    """
    mock_queue = MagicMock()
    handler = EventHandler(mock_queue)
    event = MagicMock(is_directory=False, src_path="testing.fits")

    handler.on_created(event)
    mock_queue.put.assert_called_with("testing.fits")

def test_only_fits_processed(mock_config):
    """
    Tests the file watcher to ensure that it only acts on .fits files.
    """
    mock_queue = MagicMock()
    stop_event = threading.Event()

    # Simulate queue items: a .fits file, a .txt file, then timeout
    mock_queue.get.side_effect = ["testing.fits", "testing.txt", Exception("timeout")]

    with patch('le_beta_vis.backend.InitializePolling.ProcessFile') as mock_process:
        polling = PollingThread(mock_config)
        try:
            polling.file_uploaded(mock_queue, mock_config, stop_event)
        except Exception:
            pass  # Expected to timeout after processing
        mock_process.assert_called_once_with(config_service=mock_config, file="testing.fits")

def test_polling_thread_begins(mock_config):
    """
    Tests the polling thread creation of the file watcher and event handler
    """
    with patch('le_beta_vis.backend.InitializePolling.FileWatcher') as MockWatcher, patch('threading.Thread') as MockThread:
        polling = PollingThread(mock_config)
        polling.begin()
        MockWatcher.assert_called_once_with(polling.handler, Path("/tmp"))
        MockThread.assert_called_once()

@pytest.fixture
def polling_runner():
    return PollingRunner()

def test_polling_runner_start(polling_runner, mock_config):
    """
    Tests starting the PollingRunner with a PollingThread.
    """
    poller = PollingThread(mock_config)
    with patch.object(poller, '__call__') as mock_call:
        polling_runner.start(poller)
        assert polling_runner.running is True
        assert polling_runner.poller is poller
        assert polling_runner.thread is not None
        assert polling_runner.thread.daemon is True
        mock_call.assert_not_called()  # __call__ is called in the thread

def test_polling_runner_is_running(polling_runner, mock_config):
    """
    Tests the is_running method.
    """
    poller = PollingThread(mock_config)
    with patch.object(poller, 'begin'), patch.object(poller, 'end'):
        polling_runner.start(poller)
        assert polling_runner.is_running() is True
        polling_runner.stop()
        time.sleep(0.1)  # Allow thread to stop
        assert polling_runner.is_running() is False

def test_polling_runner_stop(polling_runner, mock_config):
    """
    Tests stopping the PollingRunner.
    """
    poller = PollingThread(mock_config)
    with patch.object(poller, 'end'):
        polling_runner.start(poller)
        polling_runner.stop()
        assert polling_runner.running is False
        poller.end.assert_called_once()

def test_polling_runner_start_already_running(polling_runner, mock_config, caplog):
    """
    Tests starting when already running logs a warning.
    """
    poller = PollingThread(mock_config)
    polling_runner.start(poller)
    polling_runner.start(poller)  # Try to start again
    assert "File Ingest is already running" in caplog.text
