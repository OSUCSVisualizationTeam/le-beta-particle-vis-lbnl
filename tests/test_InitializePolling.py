import pytest
import queue
from unittest.mock import MagicMock, patch, ANY

from le_beta_vis.backend.InitializePolling import PollingThread
from le_beta_vis.backend.InitializePolling import EventHandler
from le_beta_vis.backend.InitializePolling import FileWatcher
from le_beta_vis.backend.InitializePolling import file_uploaded

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get.return_value = "/tmp"
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

def test_only_fits_processed():
    """
    Tests the file watcher to ensure that it only acts on .fits files.
    """
    mock_queue = MagicMock()
    mock_queue.get.side_effect = ["testing.fits", "testing.txt", Exception("STOP")]

    with patch('ProcessFile') as mock_process:
        with pytest.raises(Exception, match="STOP"):
            file_uploaded(mock_queue)
        mock_process.assert_called_once_with(config_service=ANY, file="testing.fits")

def test_polling_thread_begins(mock_config):
    """
    Tests the polling thread creation of the file watcher and event handler
    """
    with patch('FileWatcher') as MockWatcher, patch('threading.Thread') as MockThread:
        polling = PollingThread(mock_config)
        polling.begin()
        MockWatcher.assert_called_once_with(polling.handler, "/tmp")
        MockThread.assert_called_once()
        assert MockThread.return_value.start.called