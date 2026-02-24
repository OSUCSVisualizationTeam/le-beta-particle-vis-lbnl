# Citation for Unit Tests: Tests for LBNLOptimizedClusterExtractor verifying optimized labeling and brightest cluster selection.
# Date: 21/02/2026
# Adapted from Claude Code:
# Analyze the ClusterExtractor logic and implementations, derive suitable test cases to cover the most relevant scenarios

"""Tests for LBNLOptimizedClusterExtractor.

Uses ped_width=100, sigma=4.0 so threshold = 400.
Values of 500 are above threshold; 0 is below.
kev_conversion=0.01 so energy of 500 ADU = 5 keV (above 1 keV minimum).
"""

import sys
import threading
import time
from unittest.mock import patch
from typing import Union

import numpy as np
import pytest
from scipy.ndimage import label

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.LBNLOptimizedClusterExtractor import (
    LBNLOptimizedClusterExtractor,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager

_opt_mod = sys.modules['le_beta_vis.common.LBNLOptimizedClusterExtractor']

# Shared test parameters: threshold = 4.0 * 100 = 400
_SIGMA = 4.0
_PED = 100
_KEV = 0.01  # 500 ADU * 0.01 = 5 keV

class MockPhysicsManager(PhysicsConversionManager):
    def __init__(self, factor: float, ped_width: int):
        self._factor = factor
        self._ped_width = ped_width
    
    @property
    def kev_conversion_factor(self) -> float:
        return self._factor
    
    @property
    def pedestal_width(self) -> int:
        return self._ped_width
    
    def calculate_threshold(self, sigma: float) -> float:
        return sigma * self._ped_width
    
    def adu_to_kev(self, value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        return value * self._factor

def _make_extractor() -> LBNLOptimizedClusterExtractor:
    physics = MockPhysicsManager(factor=_KEV, ped_width=_PED)
    return LBNLOptimizedClusterExtractor(
        sigma_multiplier=_SIGMA, physics_manager=physics,
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


class TestLBNLOptimizedClusterExtractor:
    def test_no_clusters_returns_empty_list(self):
        data = np.zeros((20, 20), dtype=np.float64)
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert results == []

    def test_single_cluster_returned(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1

    def test_multiple_clusters_all_returned(self):
        """Both qualifying clusters are returned."""
        data = np.zeros((30, 30), dtype=np.float64)
        # Dimmer cluster at (5,5)
        data[5, 5] = 500
        # Brighter cluster at (25,25)
        data[25, 25] = 1000
        data[25, 26] = 900
        bbox = BoundingBox(0, 0, 30, 30)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 2
        energies = sorted(r.energy for r in results)
        assert energies[0] == pytest.approx(500.0)
        assert energies[1] == pytest.approx(1900.0)

    def test_center_coords_global_frame(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        bbox = BoundingBox(top=100, left=200, bottom=120, right=220)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].centerX == 210  # 200 + 10
        assert results[0].centerY == 110  # 100 + 10

    def test_bbox_global_frame(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        bbox = BoundingBox(top=50, left=60, bottom=70, right=80)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        result_bbox = results[0].boundingBox
        # 10x10 box centred on (10,10): rows 5..15, cols 5..15
        assert result_bbox.top == 50 + 5
        assert result_bbox.left == 60 + 5
        assert result_bbox.bottom == 50 + 15
        assert result_bbox.right == 60 + 15

    def test_data_is_copy(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].data is not data

    def test_cancel_prevents_callback(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        extractor = _make_extractor()

        called = []
        worker_started = threading.Event()

        original_label = label

        def _synced_label(*args, **kwargs):
            worker_started.set()
            time.sleep(0.1)
            return original_label(*args, **kwargs)

        with patch.object(_opt_mod, 'label', _synced_label):
            extractor.extract(data, bbox, lambda e: called.extend(e))
            worker_started.wait(timeout=2)
            extractor.cancel()

        time.sleep(0.2)
        assert called == []

    def test_cluster_data_zeros_background(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        data[10, 11] = 450  # adjacent, same cluster
        data[0, 0] = 300    # below threshold, background
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        result_data = results[0].data
        # Non-cluster pixels should be zero
        nonzero_count = np.count_nonzero(result_data)
        # Only cluster pixels (500, 450) should be nonzero
        assert nonzero_count == 2

    def test_energy_populated(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        data[10, 11] = 450
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].energy == pytest.approx(950.0)

    def test_pixel_count_populated(self):
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        data[10, 11] = 450
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].pixelCount == 2

    def test_low_energy_cluster_filtered(self):
        """Cluster below 1.0 keV is excluded."""
        data = np.zeros((20, 20), dtype=np.float64)
        # Energy = 500 ADU * 0.01 keV/ADU = 5 keV — qualifying
        data[5, 5] = 500
        # Energy = 50 ADU * 0.01 = 0.5 keV — below 1 keV minimum
        # But 50 < threshold (400), so it won't even be labeled.
        # Use a value above threshold but with low total energy:
        # single pixel at 401 ADU → 401 * 0.01 = 4.01 keV — still
        # above 1 keV. To get below 1 keV with kev=0.01, need
        # energy < 100 ADU total. That's impossible above threshold
        # (400). So with these test params, all labeled clusters
        # pass. Use a different kev to test filtering:
        physics = MockPhysicsManager(factor=0.001, ped_width=_PED)
        extractor = LBNLOptimizedClusterExtractor(
            sigma_multiplier=_SIGMA, physics_manager=physics,
        )
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(extractor, data, bbox)
        assert results == []

    def test_progress_callback_called(self):
        """Progress values end at 1.0."""
        data = np.zeros((30, 30), dtype=np.float64)
        data[5, 5] = 500
        data[25, 25] = 1000
        bbox = BoundingBox(0, 0, 30, 30)
        progress_values = []

        extractor = _make_extractor()
        result = []
        done = threading.Event()

        def cb(events):
            result.extend(events)
            done.set()

        extractor.extract(
            data, bbox, cb,
            progress_callback=lambda v: progress_values.append(v),
        )
        assert done.wait(timeout=5)
        assert len(progress_values) >= 1
        assert progress_values[-1] == pytest.approx(1.0)

    def test_progress_callback_none_accepted(self):
        """Extraction works when progress_callback is None."""
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1

    def test_sigma_is_populated(self):
        """Extracted cluster with spread has non-zero sigmaX."""
        data = np.zeros((20, 20), dtype=np.float64)
        data[10, 10] = 500
        data[10, 11] = 450
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        # Two adjacent pixels should produce horizontal spread
        assert results[0].sigmaX > 0.0
