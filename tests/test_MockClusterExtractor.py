import threading
import time
from unittest.mock import MagicMock

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor


def test_extract_calls_callback():
    """Extract completes and callback receives one ClusteredEventInfo."""
    extractor = MockClusterExtractor(delay_seconds=0.01)
    data = np.array([[1, 2], [3, 4]])
    bbox = BoundingBox(10, 20, 12, 22)
    done = threading.Event()
    results_holder = []

    def on_done(results):
        results_holder.extend(results)
        done.set()

    extractor.extract(data, bbox, on_done)
    done.wait(timeout=2.0)

    assert len(results_holder) == 1
    assert results_holder[0].boundingBox == bbox


def test_center_is_max_energy_pixel():
    """Center coordinates offset by bbox match the max pixel location."""
    extractor = MockClusterExtractor(delay_seconds=0.01)
    # max at (1, 1) in local data
    data = np.array([[1, 2], [3, 10]])
    bbox = BoundingBox(5, 10, 7, 12)
    done = threading.Event()
    results_holder = []

    def on_done(results):
        results_holder.extend(results)
        done.set()

    extractor.extract(data, bbox, on_done)
    done.wait(timeout=2.0)

    event = results_holder[0]
    assert event.centerY == 6   # bbox.top(5) + row(1)
    assert event.centerX == 11  # bbox.left(10) + col(1)


def test_data_is_copy():
    """Returned data is a copy, not the original array."""
    extractor = MockClusterExtractor(delay_seconds=0.01)
    data = np.array([[1, 2], [3, 4]])
    bbox = BoundingBox(0, 0, 2, 2)
    done = threading.Event()
    results_holder = []

    def on_done(results):
        results_holder.extend(results)
        done.set()

    extractor.extract(data, bbox, on_done)
    done.wait(timeout=2.0)

    assert results_holder[0].data is not data
    np.testing.assert_array_equal(results_holder[0].data, data)


def test_bounding_box_passthrough():
    """Result bounding box matches input."""
    extractor = MockClusterExtractor(delay_seconds=0.01)
    data = np.array([[5]])
    bbox = BoundingBox(100, 200, 101, 201)
    done = threading.Event()
    results_holder = []

    def on_done(results):
        results_holder.extend(results)
        done.set()

    extractor.extract(data, bbox, on_done)
    done.wait(timeout=2.0)

    assert results_holder[0].boundingBox == bbox


def test_cancel_prevents_callback():
    """Cancel should prevent callback from firing."""
    extractor = MockClusterExtractor(delay_seconds=1.0)
    data = np.array([[1, 2], [3, 4]])
    bbox = BoundingBox(0, 0, 2, 2)
    callback = MagicMock()

    extractor.extract(data, bbox, callback)
    extractor.cancel()

    time.sleep(0.1)
    callback.assert_not_called()
