import pytest
import queue
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from le_beta_vis.backend.InitializePolling import PollingThread
from le_beta_vis.backend.InitializePolling import EventHandler
from le_beta_vis.backend.InitializePolling import FileWatcher
from le_beta_vis.backend.PollingRunner import PollingRunner
from mock_configuration_service import MockConfigurationService


@pytest.fixture
def mock_config():
    config = MockConfigurationService()
    config.set("pipeline:ingress:polling_location", "/tmp")
    return config


class TestEventHandler:
    """Test cases for EventHandler class"""

    def test_on_created_file(self):
        """Test that on_created adds file paths to queue"""
        mock_queue = MagicMock()
        handler = EventHandler(mock_queue)

        event = MagicMock(is_directory=False, src_path="/tmp/test.fits")
        handler.on_created(event)

        mock_queue.put.assert_called_once_with("/tmp/test.fits")

    def test_on_created_directory_ignored(self):
        """Test that on_created ignores directories"""
        mock_queue = MagicMock()
        handler = EventHandler(mock_queue)

        event = MagicMock(is_directory=True, src_path="/tmp/somedir")
        handler.on_created(event)

        mock_queue.put.assert_not_called()

    def test_on_moved_file(self):
        """Test that on_moved adds destination path to queue"""
        mock_queue = MagicMock()
        handler = EventHandler(mock_queue)

        event = MagicMock(is_directory=False, dest_path="/tmp/moved.fits")
        handler.on_moved(event)

        mock_queue.put.assert_called_once_with("/tmp/moved.fits")

    def test_on_moved_directory_ignored(self):
        """Test that on_moved ignores directories"""
        mock_queue = MagicMock()
        handler = EventHandler(mock_queue)

        event = MagicMock(is_directory=True)
        handler.on_moved(event)

        mock_queue.put.assert_not_called()

    def test_on_moved_no_dest_path(self):
        """Test that on_moved handles missing dest_path"""
        mock_queue = MagicMock()
        handler = EventHandler(mock_queue)

        event = MagicMock(is_directory=False, spec=['is_directory'])
        handler.on_moved(event)

        mock_queue.put.assert_not_called()


class TestFileWatcher:
    """Test cases for FileWatcher class"""

    @patch('le_beta_vis.backend.InitializePolling.Observer')
    def test_file_watcher_initialization(self, mock_observer_class):
        """Test FileWatcher initialization"""
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer

        mock_handler = MagicMock()
        watch_path = "/tmp"

        watcher = FileWatcher(mock_handler, watch_path)

        assert watcher.handler is mock_handler
        assert watcher.path == watch_path
        assert watcher.observer is mock_observer
        mock_observer.start.assert_called_once()

    @patch('le_beta_vis.backend.InitializePolling.Observer')
    def test_file_watcher_observe_schedule(self, mock_observer_class):
        """Test that observe schedules handler"""
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer

        mock_handler = MagicMock()

        watcher = FileWatcher(mock_handler, "/tmp")

        mock_observer.schedule.assert_called_once_with(mock_handler, "/tmp", recursive=False)

    @patch('le_beta_vis.backend.InitializePolling.Observer')
    def test_file_watcher_stop(self, mock_observer_class):
        """Test FileWatcher stop method"""
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer

        mock_handler = MagicMock()
        watcher = FileWatcher(mock_handler, "/tmp")

        watcher.stop()
        mock_observer.stop.assert_called_once()


class TestPollingThread:
    """Test cases for PollingThread class"""

    def test_polling_thread_initialization(self, mock_config):
        """Test PollingThread initialization"""
        with patch('os.path.exists', return_value=True):
            polling = PollingThread(mock_config)

            assert polling.config_service is mock_config
            # Path gets normalized by os.path.normpath()
            assert polling.polling_location == os.path.normpath("/tmp")
            assert isinstance(polling.file_queue, queue.Queue)
            assert isinstance(polling.handler, EventHandler)
            assert isinstance(polling.stop_event, threading.Event)

    def test_polling_thread_initialization_with_default_config(self):
        """Test PollingThread initialization with default config"""
        with patch('le_beta_vis.backend.InitializePolling.YAMLBackedConfigurationService') as mock_config_class, \
             patch('os.path.exists', return_value=True):

            mock_config = MagicMock()
            mock_config.get.return_value = "/tmp"
            mock_config_class.return_value = mock_config

            polling = PollingThread()

            assert polling.config_service is mock_config

    def test_polling_thread_begin(self, mock_config):
        """Test PollingThread.begin() creates and starts threads"""
        with patch('os.path.exists', return_value=True), \
             patch('le_beta_vis.backend.InitializePolling.FileWatcher') as MockWatcher, \
             patch('threading.Thread') as MockThread, \
             patch('time.sleep'):

            mock_watcher = MagicMock()
            MockWatcher.return_value = mock_watcher

            mock_thread = MagicMock()
            MockThread.return_value = mock_thread

            polling = PollingThread(mock_config)
            polling.begin()

            # Path is normalized, so /tmp becomes \\tmp on Windows
            normalized_path = os.path.normpath("/tmp")
            MockWatcher.assert_called_once_with(polling.handler, normalized_path)
            assert polling.observer is mock_watcher

            MockThread.assert_called_once()
            mock_thread.start.assert_called_once()

    def test_polling_thread_end(self, mock_config):
        """Test PollingThread.end() stops observer and joins threads"""
        with patch('os.path.exists', return_value=True), \
             patch('le_beta_vis.backend.InitializePolling.FileWatcher') as MockWatcher, \
             patch('threading.Thread') as MockThread, \
             patch('time.sleep'):

            mock_watcher = MagicMock()
            MockWatcher.return_value = mock_watcher

            mock_thread = MagicMock()
            MockThread.return_value = mock_thread

            polling = PollingThread(mock_config)
            polling.observer = mock_watcher
            polling.ingest_thread = mock_thread
            polling.end()

            assert polling.stop_event.is_set()
            mock_watcher.stop.assert_called_once()
            mock_thread.join.assert_called_once()

    def test_file_uploaded_filters_fits_files(self, mock_config):
        """Test file_uploaded only processes .fits files"""
        with patch('le_beta_vis.backend.InitializePolling.process_file') as mock_process:
            polling = PollingThread(mock_config)

            # Create a test queue with controlled items
            test_queue = queue.Queue()
            test_queue.put("test.fits")
            test_queue.put("test.txt")

            stop_event = threading.Event()

            # Create a counter to limit iterations
            call_count = [0]
            original_get = test_queue.get

            def limited_get(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] > 2:
                    stop_event.set()
                return original_get(*args, **kwargs)

            test_queue.get = limited_get

            polling.file_uploaded(test_queue, mock_config, stop_event)

            # Should only process the .fits file
            mock_process.assert_called_once_with(config_service=mock_config, file="test.fits")

    def test_file_uploaded_exits_on_stop_event(self, mock_config):
        """Test file_uploaded exits when stop_event is set"""
        polling = PollingThread(mock_config)

        test_queue = queue.Queue()
        stop_event = threading.Event()

        # Set stop event immediately
        stop_event.set()

        # Should exit immediately without processing
        polling.file_uploaded(test_queue, mock_config, stop_event)


class TestPollingRunner:
    """Test cases for PollingRunner class"""

    def test_polling_runner_initialization(self):
        """Test PollingRunner initialization"""
        runner = PollingRunner()

        assert runner.thread is None
        assert runner.running is False

    def test_polling_runner_start(self, mock_config):
        """Test PollingRunner.start()"""
        runner = PollingRunner()
        poller = PollingThread(mock_config)

        with patch.object(poller, 'begin'), \
             patch.object(poller, 'end'), \
             patch('threading.Thread') as MockThread, \
             patch('time.sleep'):

            mock_thread = MagicMock()
            MockThread.return_value = mock_thread

            runner.start(poller)

            assert runner.running is True
            assert runner.poller is poller
            mock_thread.start.assert_called_once()

    def test_polling_runner_is_running_true(self):
        """Test is_running returns True when running and thread alive"""
        runner = PollingRunner()

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        runner.running = True
        runner.thread = mock_thread

        assert runner.is_running() is True

    def test_polling_runner_is_running_false_not_running(self):
        """Test is_running returns False when not running"""
        runner = PollingRunner()

        mock_thread = MagicMock()
        runner.running = False
        runner.thread = mock_thread

        assert runner.is_running() is False

    def test_polling_runner_is_running_false_thread_dead(self):
        """Test is_running returns False when thread is not alive"""
        runner = PollingRunner()

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        runner.running = True
        runner.thread = mock_thread

        assert runner.is_running() is False
        # After stopping, both should be False
        runner.running = False
        assert runner.is_running() is False

    def test_polling_runner_start_already_running(self, mock_config, caplog):
        """Test starting when already running logs warning"""
        runner = PollingRunner()
        runner.running = True
        poller = PollingThread(mock_config)

        runner.start(poller)

        assert "File Ingest is already running" in caplog.text

    def test_polling_runner_stop(self, mock_config):
        """Test PollingRunner.stop()"""
        runner = PollingRunner()
        poller = PollingThread(mock_config)
        runner.running = True
        runner.poller = poller

        with patch.object(poller, 'end') as mock_end:
            runner.stop()

            assert runner.running is False
            mock_end.assert_called_once()


class TestPollingThreadCallable:
    """Test PollingThread __call__ method"""

    def test_polling_thread_callable(self, mock_config):
        """Test PollingThread is callable and calls begin"""
        with patch('os.path.exists', return_value=True), \
             patch.object(PollingThread, 'begin') as mock_begin:

            polling = PollingThread(mock_config)
            polling()

            mock_begin.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
