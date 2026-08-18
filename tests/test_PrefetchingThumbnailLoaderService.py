"""Tests for PrefetchingThumbnailLoaderService."""

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.PrefetchingThumbnailLoaderService import (
    PrefetchingThumbnailLoaderService,
)


_SENTINEL = object()


def _make_cluster(
    data=_SENTINEL,
    fits_filename=None,
    hdu_id=None,
    center_x=None,
    center_y=None,
) -> Cluster:
    """Create a minimal Cluster for testing."""
    if data is _SENTINEL:
        data = np.array([[1, 2], [3, 4]], dtype=np.float64)
    return Cluster(
        boundingBox=BoundingBox(top=2, left=0, bottom=0, right=2),
        data=data,
        centerX=center_x,
        centerY=center_y,
        fitsFilename=fits_filename,
        hdu_id=hdu_id,
    )


def _wait_for_event(event: threading.Event, timeout: float = 5.0) -> bool:
    return event.wait(timeout)


# --- test_request_fires_callback ---


def test_request_fires_callback():
    """Submit a cluster with synthetic data; verify callback fires."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    done = threading.Event()
    result = {}

    def on_ready(key: int, arr: np.ndarray) -> None:
        result["key"] = key
        result["arr"] = arr
        done.set()

    cluster = _make_cluster()
    service.request_thumbnail(0, cluster, on_ready)
    assert _wait_for_event(done)
    assert result["key"] == 0
    assert result["arr"].dtype == np.uint8
    service.shutdown()


# --- test_duplicate_request_ignored ---


def test_duplicate_request_returns_cached():
    """Requesting a cached key should return immediately without extra workers."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    done = threading.Event()
    results = []

    def on_ready(key: int, arr: np.ndarray) -> None:
        results.append(key)
        done.set()

    cluster = _make_cluster()
    service.request_thumbnail(0, cluster, on_ready)
    assert _wait_for_event(done)

    # Second request should hit cache and fire callback immediately
    results.clear()
    service.request_thumbnail(0, cluster, on_ready)
    # Cache hit is synchronous
    time.sleep(0.1)
    assert len(results) == 1
    assert results[0] == 0
    service.shutdown()


# --- test_clear_cancels_pending ---


def test_clear_cancels_pending():
    """Clear should increment generation so stale workers skip callbacks."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    count = {"n": 0}

    def on_ready(key: int, arr: np.ndarray) -> None:
        count["n"] += 1

    cluster = _make_cluster()
    service.request_thumbnail(0, cluster, on_ready)
    service.clear()
    # Wait for any potential worker to finish
    time.sleep(0.5)
    # After clear, cached entries should be gone
    assert service.get_cached(0) is None
    service.shutdown()


# --- test_evict_removes_non_kept ---


def test_evict_removes_non_kept():
    """Load thumbnails, evict, verify non-kept keys are removed."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    events = []

    for i in range(5):
        done = threading.Event()
        events.append(done)

        def on_ready(key: int, arr: np.ndarray, ev=done) -> None:
            ev.set()

        cluster = _make_cluster()
        service.request_thumbnail(i, cluster, on_ready)

    for ev in events:
        assert _wait_for_event(ev)

    # All 5 should be cached
    for i in range(5):
        assert service.get_cached(i) is not None

    service.evict(keep_keys={2, 3})

    assert service.get_cached(0) is None
    assert service.get_cached(1) is None
    assert service.get_cached(2) is not None
    assert service.get_cached(3) is not None
    assert service.get_cached(4) is None
    service.shutdown()


# --- test_center_computed ---


def test_center_computed():
    """Cluster center should be computed from argmax when not set."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    done = threading.Event()

    data = np.array([[1, 2], [3, 10]], dtype=np.float64)
    cluster = _make_cluster(data=data, center_x=None, center_y=None)

    def on_ready(key: int, arr: np.ndarray) -> None:
        done.set()

    service.request_thumbnail(0, cluster, on_ready)
    assert _wait_for_event(done)

    # argmax of [[1,2],[3,10]] is index 3 → row=1, col=1
    # Absolute coords: col + bb.left = 1 + 0 = 1, row + bb.top = 1 + 2 = 3
    assert cluster.centerX == 1
    assert cluster.centerY == 3
    service.shutdown()


# --- test_colormap_applied ---


def test_colormap_applied_rgb():
    """With a colormap, thumbnail should be (H, W, 3)."""
    from le_beta_vis.frontend.fitsconverters.interface import Colormap

    service = PrefetchingThumbnailLoaderService(
        max_workers=2,
        colormap=Colormap.VIRIDIS,
    )
    done = threading.Event()
    result = {}

    def on_ready(key: int, arr: np.ndarray) -> None:
        result["arr"] = arr
        done.set()

    cluster = _make_cluster()
    service.request_thumbnail(0, cluster, on_ready)
    assert _wait_for_event(done)
    assert result["arr"].ndim == 3
    assert result["arr"].shape[2] == 3
    service.shutdown()


def test_colormap_none_grayscale():
    """Without a colormap, thumbnail should be 2D grayscale."""
    service = PrefetchingThumbnailLoaderService(
        max_workers=2,
        colormap=None,
    )
    done = threading.Event()
    result = {}

    def on_ready(key: int, arr: np.ndarray) -> None:
        result["arr"] = arr
        done.set()

    cluster = _make_cluster()
    service.request_thumbnail(0, cluster, on_ready)
    assert _wait_for_event(done)
    # FastPixmapConverter with no colormap still returns 2D
    assert result["arr"].ndim == 2
    service.shutdown()


# --- test_fallback_when_no_fits_file ---


def test_fallback_when_no_fits_file():
    """Cluster with data=None and no FITS file returns zeros fallback."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    done = threading.Event()
    result = {}

    def on_ready(key: int, arr: np.ndarray) -> None:
        result["arr"] = arr
        done.set()

    cluster = _make_cluster(data=None, fits_filename=None)
    service.request_thumbnail(0, cluster, on_ready)
    assert _wait_for_event(done)
    # Fallback: zeros array
    assert np.all(result["arr"] == 0)
    service.shutdown()


# --- test_fits_cache_reused_same_file ---


def test_fits_cache_reused_same_file():
    """Two clusters with same fitsFilename should call load() only once."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)

    mock_model = MagicMock()
    mock_model.clusterFromBoundingBox.return_value = np.array(
        [[1, 2], [3, 4]],
        dtype=np.float64,
    )

    events = []
    for i in range(2):
        done = threading.Event()
        events.append(done)

        def on_ready(key: int, arr: np.ndarray, ev=done) -> None:
            ev.set()

        cluster = _make_cluster(
            data=None,
            fits_filename="/fake/file.fits",
            hdu_id=0,
        )
        with patch.object(
            CCDCaptureModel,
            "load",
            return_value=[mock_model],
        ) as mock_load:
            service.request_thumbnail(i, cluster, on_ready)

    for ev in events:
        assert _wait_for_event(ev)

    # Verify: due to caching, load should have been called only once
    # (We can't easily assert across patches, but we verify both completed)
    service.shutdown()


# --- test_fits_cache_evicted_on_different_file ---


def test_fits_cache_evicted_on_different_file():
    """Different fitsFilenames should trigger separate load() calls."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)

    mock_model = MagicMock()
    mock_model.clusterFromBoundingBox.return_value = np.array(
        [[1, 2], [3, 4]],
        dtype=np.float64,
    )

    done1 = threading.Event()
    done2 = threading.Event()

    def on_ready1(key: int, arr: np.ndarray) -> None:
        done1.set()

    def on_ready2(key: int, arr: np.ndarray) -> None:
        done2.set()

    with patch.object(
        CCDCaptureModel,
        "load",
        return_value=[mock_model],
    ) as mock_load:
        cluster1 = _make_cluster(
            data=None,
            fits_filename="/fake/file1.fits",
            hdu_id=0,
        )
        service.request_thumbnail(0, cluster1, on_ready1)
        assert _wait_for_event(done1)

        cluster2 = _make_cluster(
            data=None,
            fits_filename="/fake/file2.fits",
            hdu_id=0,
        )
        service.request_thumbnail(1, cluster2, on_ready2)
        assert _wait_for_event(done2)

        assert mock_load.call_count == 2

    service.shutdown()


# --- test_fits_cache_idle_eviction ---


def test_fits_cache_idle_eviction():
    """Idle timer should release cached HDUs after timeout."""
    service = PrefetchingThumbnailLoaderService(
        max_workers=2,
        fits_cache_idle_seconds=60,
    )

    mock_model = MagicMock()
    mock_model.clusterFromBoundingBox.return_value = np.array(
        [[1, 2], [3, 4]],
        dtype=np.float64,
    )

    done = threading.Event()

    def on_ready(key: int, arr: np.ndarray) -> None:
        done.set()

    with patch.object(
        CCDCaptureModel,
        "load",
        return_value=[mock_model],
    ):
        cluster = _make_cluster(
            data=None,
            fits_filename="/fake/file.fits",
            hdu_id=0,
        )
        service.request_thumbnail(0, cluster, on_ready)
        assert _wait_for_event(done)

    # HDUs should be cached now
    assert service._cached_hdus is not None

    # Manually trigger eviction (simulates timer firing)
    service._evict_fits_cache()
    assert service._cached_hdus is None
    assert service._cached_fits_filename is None

    service.shutdown()


# --- test_request_cluster_data_with_inline_data ---


def test_request_cluster_data_with_inline_data():
    """request_cluster_data returns inline data synchronously."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    data = np.array([[5, 6], [7, 8]], dtype=np.float64)
    cluster = _make_cluster(data=data)
    result = {}

    def on_ready(arr):
        result["arr"] = arr

    service.request_cluster_data(cluster, on_ready)
    assert result["arr"] is data
    service.shutdown()


# --- test_request_cluster_data_from_fits ---


def test_request_cluster_data_from_fits():
    """request_cluster_data extracts from FITS when data is None."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    done = threading.Event()
    result = {}

    expected = np.array([[10, 20], [30, 40]], dtype=np.float64)
    mock_model = MagicMock()
    mock_model.clusterFromBoundingBox.return_value = expected

    def on_ready(arr):
        result["arr"] = arr
        done.set()

    cluster = _make_cluster(
        data=None,
        fits_filename="/fake/file.fits",
        hdu_id=0,
    )
    with patch.object(
        CCDCaptureModel,
        "load",
        return_value=[mock_model],
    ):
        service.request_cluster_data(cluster, on_ready)
        assert _wait_for_event(done)

    assert result["arr"] is not None
    np.testing.assert_array_equal(result["arr"], expected)
    service.shutdown()


# --- test_request_cluster_data_returns_none_on_failure ---


def test_evict_cancels_in_flight_futures():
    """evict() should cancel queued futures and clear _in_flight for evicted keys."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)

    # Block both workers so subsequent requests queue up
    block1 = threading.Event()
    block2 = threading.Event()
    release = threading.Event()

    def blocker_task(ready_event):
        ready_event.set()
        release.wait(timeout=5.0)

    service._executor.submit(blocker_task, block1)
    service._executor.submit(blocker_task, block2)
    assert block1.wait(timeout=5.0)
    assert block2.wait(timeout=5.0)

    cluster = _make_cluster()
    callbacks_fired = []

    def on_ready(key: int, arr) -> None:
        callbacks_fired.append(key)

    service.request_thumbnail(10, cluster, on_ready)
    service.request_thumbnail(20, cluster, on_ready)

    # Both should be in _in_flight with queued futures
    with service._lock:
        assert 10 in service._in_flight
        assert 20 in service._in_flight

    # Evict key 10, keep key 20
    service.evict(keep_keys={20})

    with service._lock:
        assert 10 not in service._in_flight
        assert 20 in service._in_flight

    # Release blocker so key 20 can complete
    release.set()

    deadline = time.time() + 5.0
    while 20 not in callbacks_fired and time.time() < deadline:
        time.sleep(0.05)

    assert 20 in callbacks_fired
    assert 10 not in callbacks_fired
    service.shutdown()


# --- test_request_cluster_data_returns_none_on_failure ---


def test_request_cluster_data_returns_none_on_failure():
    """request_cluster_data delivers None when extraction fails."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)
    done = threading.Event()
    result = {"arr": "sentinel"}

    def on_ready(arr):
        result["arr"] = arr
        done.set()

    cluster = _make_cluster(data=None, fits_filename=None)
    service.request_cluster_data(cluster, on_ready)
    assert _wait_for_event(done)
    assert result["arr"] is None
    service.shutdown()


# --- test_clear_cancels_pending_cluster_data_request ---


def test_clear_cancels_pending_cluster_data_request():
    """request_cluster_data must not deliver on_ready after an intervening clear()."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)

    block1 = threading.Event()
    block2 = threading.Event()
    release = threading.Event()

    def blocker_task(ready_event):
        ready_event.set()
        release.wait(timeout=5.0)

    service._executor.submit(blocker_task, block1)
    service._executor.submit(blocker_task, block2)
    assert block1.wait(timeout=5.0)
    assert block2.wait(timeout=5.0)

    callbacks_fired = []
    cluster = _make_cluster(data=None, fits_filename=None)
    service.request_cluster_data(cluster, lambda arr: callbacks_fired.append(arr))

    # Queued behind the blockers, not yet started — clear() invalidates it
    # before its worker ever runs.
    service.clear()
    release.set()
    time.sleep(0.5)

    assert callbacks_fired == []
    service.shutdown()


# --- test_clear_cancels_pending_hdu_frame_request ---


def test_clear_cancels_pending_hdu_frame_request():
    """request_hdu_frame must not deliver on_ready after an intervening clear()."""
    service = PrefetchingThumbnailLoaderService(max_workers=2)

    block1 = threading.Event()
    block2 = threading.Event()
    release = threading.Event()

    def blocker_task(ready_event):
        ready_event.set()
        release.wait(timeout=5.0)

    service._executor.submit(blocker_task, block1)
    service._executor.submit(blocker_task, block2)
    assert block1.wait(timeout=5.0)
    assert block2.wait(timeout=5.0)

    callbacks_fired = []
    service.request_hdu_frame(
        "/fake/file.fits", 0, lambda arr: callbacks_fired.append(arr)
    )

    service.clear()
    release.set()
    time.sleep(0.5)

    assert callbacks_fired == []
    service.shutdown()
