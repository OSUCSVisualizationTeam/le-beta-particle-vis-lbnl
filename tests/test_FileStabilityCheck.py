from le_beta_vis.backend.FileStabilityCheck import wait_for_file_stable
import os
import sys
import threading
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestWaitForFileStable:
    """Test cases for wait_for_file_stable()"""

    def test_returns_true_immediately_when_file_already_stable(self, tmp_path):
        target = tmp_path / "stable.fits"
        target.write_bytes(b"\x00" * 1024)

        with patch('time.sleep') as mock_sleep:
            assert wait_for_file_stable(str(target), poll_interval_ms=50, max_wait_ms=5000) is True
        mock_sleep.assert_called_once()

    def test_returns_true_once_growth_stops(self, tmp_path):
        target = tmp_path / "growing.fits"
        target.write_bytes(b"\x00" * 100)

        def _grow_once():
            time.sleep(0.05)
            with open(target, "ab") as f:
                f.write(b"\x00" * 100)

        writer = threading.Thread(target=_grow_once)
        writer.start()
        try:
            assert wait_for_file_stable(str(target), poll_interval_ms=20, max_wait_ms=5000) is True
        finally:
            writer.join()

    def test_returns_false_when_max_wait_exceeded(self, tmp_path):
        target = tmp_path / "never_stable.fits"
        target.write_bytes(b"\x00" * 100)

        # Writer appends much faster than the poll interval below, so every
        # poll observes growth — the check should never see two equal reads.
        stop_growing = threading.Event()

        def _keep_growing():
            while not stop_growing.is_set():
                with open(target, "ab") as f:
                    f.write(b"\x00")
                time.sleep(0.001)

        writer = threading.Thread(target=_keep_growing)
        writer.start()
        try:
            assert wait_for_file_stable(str(target), poll_interval_ms=30, max_wait_ms=150) is False
        finally:
            stop_growing.set()
            writer.join()

    def test_returns_false_when_file_missing(self, tmp_path):
        missing = tmp_path / "does_not_exist.fits"
        assert wait_for_file_stable(str(missing), poll_interval_ms=10, max_wait_ms=100) is False

    def test_stop_event_aborts_early(self, tmp_path):
        target = tmp_path / "never_stable.fits"
        target.write_bytes(b"\x00" * 100)

        # Writer appends much faster than the poll interval, so the file
        # never looks stable — the only way out is stop_event.
        stop_growing = threading.Event()

        def _keep_growing():
            while not stop_growing.is_set():
                with open(target, "ab") as f:
                    f.write(b"\x00")
                time.sleep(0.001)

        writer = threading.Thread(target=_keep_growing)
        writer.start()

        stop_event = threading.Event()

        def _stop_soon():
            time.sleep(0.05)
            stop_event.set()

        stopper = threading.Thread(target=_stop_soon)
        stopper.start()

        try:
            start = time.monotonic()
            result = wait_for_file_stable(
                str(target), poll_interval_ms=30, max_wait_ms=5000, stop_event=stop_event
            )
            elapsed = time.monotonic() - start
            assert result is False
            assert elapsed < 1.0
        finally:
            stop_growing.set()
            writer.join()
            stopper.join()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
