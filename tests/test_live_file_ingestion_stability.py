"""Live/manual-verification test for the file-ingestion stability race
(diagnosed 2026-07-16, fix/windows_zmq_fallbak — watchdog's on_created can
fire before a streamed write finishes).

Unlike the rest of the suite, this test touches a real ``watchdog.Observer``
and a real ``PollingThread`` consumer thread — it is not mocked. Skipped by
default; set ``LBNLVIS_LIVE_TESTS=1`` to run it:

    LBNLVIS_LIVE_TESTS=1 uv run pytest tests/test_live_file_ingestion_stability.py -v

Follows the tests/test_live_ipc_fallback.py convention (see that file's
docstring). No QApplication is used here, so — unlike that file — this one
needs no --ignore entry in python-package-conda.yml; the skipif gate alone
is sufficient in headless CI.
"""

from mock_configuration_service import MockConfigurationService
from le_beta_vis.backend.InitializePolling import PollingThread
import os
import sys
import threading
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))


pytestmark = pytest.mark.skipif(
    os.environ.get("LBNLVIS_LIVE_TESTS") != "1",
    reason="Live/manual-verification test; set LBNLVIS_LIVE_TESTS=1 to run.",
)


def test_live_slow_write_is_not_processed_until_stable(tmp_path):
    """Real Observer + real PollingThread consumer loop against a file that
    is created and then grows in chunks, simulating a large streamed FITS
    capture arriving via network copy/NFS/cloud-sync. Asserts process_file
    is only invoked once the file has reached its final size — never a
    truncated intermediate size."""
    seen_sizes = []

    def _fake_process_file(config_service, file, cluster_storage_buffer_factory):
        seen_sizes.append(os.path.getsize(file))

    # The poll interval must exceed the writer's inter-chunk gap, or the
    # check can catch two "stable" reads in the pause between chunks and
    # declare victory early — the same trade-off documented for
    # pipeline:ingress:stability_poll_interval_ms in defaults.yaml. This
    # mirrors that requirement: chunks land every 30ms, so a 150ms poll
    # interval comfortably spans multiple chunk arrivals before it can
    # observe two genuinely-unchanged reads.
    config = MockConfigurationService()
    config.set("pipeline:ingress:polling_location", str(tmp_path))
    config.set("pipeline:ingress:stability_poll_interval_ms", 150)
    config.set("pipeline:ingress:stability_max_wait_ms", 5000)
    config.set("pipeline:ingress:process_file_timeout_seconds", 5)

    with patch(
        "le_beta_vis.backend.InitializePolling.process_file",
        side_effect=_fake_process_file,
    ):
        polling = PollingThread(config)
        polling.begin()
        try:
            target = tmp_path / "slow_capture.fits"
            chunk = b"\x00" * (512 * 1024)  # 512 KB
            total_chunks = 6  # ~3 MB total, "multi-MB" per the diagnosis report

            def _write_slowly():
                with open(target, "wb") as f:
                    for _ in range(total_chunks):
                        f.write(chunk)
                        # Load-bearing, not decoration: without an explicit
                        # flush+fsync after every chunk, buffered writes may
                        # not be visible via os.stat().st_size until close,
                        # which would let this test pass without ever
                        # exercising the race.
                        f.flush()
                        os.fsync(f.fileno())
                        time.sleep(0.03)

            writer = threading.Thread(target=_write_slowly)
            writer.start()
            writer.join()

            deadline = time.monotonic() + 5
            while not seen_sizes and time.monotonic() < deadline:
                time.sleep(0.1)
        finally:
            polling.end()

    assert seen_sizes == [len(chunk) * total_chunks]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
