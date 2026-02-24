# Citation for Unit Tests: Tests for LBNLClassicalClusterExtractor (cluster_sigma wrapper) with mocking.
# Date: 21/02/2026
# Adapted from Claude Code:
# Analyze the ClusterExtractor logic and implementations, derive suitable test cases to cover the most relevant scenarios

"""Tests for LBNLClassicalClusterExtractor (cluster_sigma wrapper).

Mocks ``mlccd_diffusion.help_functions.cluster_sigma`` so tests
run without the real library installed.

Uses ped_width=100, sigma=4.0 so threshold = 400.
"""

import threading
import time
from unittest.mock import patch

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.LBNLClassicalClusterExtractor import (
    LBNLClassicalClusterExtractor,
)

_SIGMA = 4.0
_PED = 100
_KEV = 0.01


def _make_extractor() -> LBNLClassicalClusterExtractor:
    return LBNLClassicalClusterExtractor(
        sigma_multiplier=_SIGMA, ped_width=_PED, kev_conversion=_KEV,
    )


def _run_extract(extractor, data, bbox, **kwargs):
    """Run extract synchronously, returning the result list."""
    result = []
    done = threading.Event()

    def cb(events):
        result.extend(events)
        done.set()

    extractor.extract(data, bbox, cb, **kwargs)
    assert done.wait(timeout=5), "Extraction timed out"
    return result


def _make_data_with_cluster():
    """Create a 20x20 array with a bright pixel at (10, 10)."""
    data = np.zeros((20, 20), dtype=np.float64)
    data[10, 10] = 500
    return data


class TestLBNLClassicalClusterExtractor:
    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        return_value=(0.0, 0.0, 0.0),
    )
    def test_no_clusters_returns_empty_list(self, mock_cs):
        data = np.zeros((20, 20), dtype=np.float64)
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert results == []

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        return_value=(1.5, 2.0, 500.0),
    )
    def test_single_cluster_returned(self, mock_cs):
        data = _make_data_with_cluster()
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        return_value=(3.14, 2.72, 500.0),
    )
    def test_sigma_values_propagated(self, mock_cs):
        data = _make_data_with_cluster()
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].sigmaX == pytest.approx(3.14)
        assert results[0].sigmaY == pytest.approx(2.72)

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        return_value=(1.0, 1.0, 999.0),
    )
    def test_energy_propagated(self, mock_cs):
        data = _make_data_with_cluster()
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].energy == pytest.approx(999.0)

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        return_value=(1.0, 1.0, 500.0),
    )
    def test_pixel_count_propagated(self, mock_cs):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        data[10, 11] = 450  # adjacent — same cluster label
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].pixelCount == 2

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        return_value=(1.0, 1.0, 500.0),
    )
    def test_center_coords_global_frame(self, mock_cs):
        data = _make_data_with_cluster()
        bbox = BoundingBox(top=100, left=200, bottom=120, right=220)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].centerX == 210  # 200 + 10
        assert results[0].centerY == 110  # 100 + 10

    def test_cancel_prevents_callback(self):
        data = _make_data_with_cluster()
        bbox = BoundingBox(0, 0, 20, 20)
        extractor = _make_extractor()

        called = []
        worker_started = threading.Event()

        def _synced_cs(*args, **kwargs):
            worker_started.set()
            time.sleep(0.1)
            return (1.0, 1.0, 500.0)

        with patch(
            'mlccd_diffusion.help_functions.cluster_sigma',
            _synced_cs,
        ):
            extractor.extract(data, bbox, lambda e: called.extend(e))
            worker_started.wait(timeout=2)
            extractor.cancel()

        time.sleep(0.2)
        assert called == []

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
    )
    def test_cluster_sigma_called_with_correct_args(self, mock_cs):
        mock_cs.return_value = (1.0, 1.0, 500.0)
        data = _make_data_with_cluster()
        bbox = BoundingBox(0, 0, 20, 20)
        _run_extract(_make_extractor(), data, bbox)

        mock_cs.assert_called_once()
        call_kwargs = mock_cs.call_args
        # Positional arg is the data array (square, so no padding)
        assert call_kwargs[0][0].shape == (20, 20)
        # Keyword args
        assert call_kwargs[1]["threshold"] == pytest.approx(400.0)
        assert call_kwargs[1]["min_pixels_in_cluster"] == 5

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
    )
    def test_non_square_data_padded_to_square(self, mock_cs):
        """Non-square data is zero-padded to square for cluster_sigma."""
        mock_cs.return_value = (1.0, 1.0, 500.0)
        # 15 rows x 25 cols — non-square
        data = np.zeros((15, 25), dtype=np.float64)
        data[7, 12] = 500
        bbox = BoundingBox(0, 0, 15, 25)
        results = _run_extract(_make_extractor(), data, bbox)

        mock_cs.assert_called_once()
        passed_data = mock_cs.call_args[0][0]
        # Padded to 25x25 (max of 15, 25)
        assert passed_data.shape == (25, 25)
        # Original data preserved in top-left
        assert passed_data[7, 12] == 500
        # Padding region is zeros
        assert passed_data[15, 0] == 0
        assert len(results) == 1

    @patch(
        "mlccd_diffusion.help_functions.cluster_sigma",
        side_effect=ValueError("broadcast error"),
    )
    def test_exception_in_cluster_sigma_returns_empty_list(self, mock_cs):
        """When cluster_sigma raises, callback gets an empty list."""
        data = _make_data_with_cluster()
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert results == []
