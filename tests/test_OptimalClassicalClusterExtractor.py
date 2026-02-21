"""Tests for OptimalClassicalClusterExtractor.

Uses ped_width=100, sigma=4.0 so threshold = 400.
kev_conversion=0.01 so energy of 500 ADU = 5 keV (above 1 keV minimum).
"""

import sys
import threading
import time
from unittest.mock import patch

import numpy as np
import pytest
from scipy.ndimage import label

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.OptimalClassicalClusterExtractor import (
    OptimalClassicalClusterExtractor,
)

_oce_mod = sys.modules['le_beta_vis.common.OptimalClassicalClusterExtractor']

_SIGMA = 4.0
_PED = 100
_KEV = 0.01


def _make_extractor() -> OptimalClassicalClusterExtractor:
    return OptimalClassicalClusterExtractor(
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


class TestOptimalClassicalClusterExtractor:
    def test_no_clusters_returns_empty_list(self):
        data = np.zeros((20, 20), dtype=np.float64)
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert results == []

    def test_single_cluster_returned(self):
        data = np.zeros((20, 20), dtype=np.float64)
        # 5 pixels above threshold (min pixel filter = 5)
        for i in range(5):
            data[10, 10 + i] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1

    def test_multiple_clusters_returned(self):
        data = np.zeros((30, 30), dtype=np.float64)
        # Cluster A at top-left — 5 pixels
        for i in range(5):
            data[2, 2 + i] = 500
        # Cluster B at bottom-right — 5 pixels
        for i in range(5):
            data[25, 25 + i] = 600
        bbox = BoundingBox(0, 0, 30, 30)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 2

    def test_min_pixel_filter(self):
        data = np.zeros((20, 20), dtype=np.float64)
        # Only 4 pixels — below the 5-pixel minimum
        for i in range(4):
            data[10, 10 + i] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert results == []

    def test_min_energy_filter(self):
        data = np.zeros((20, 20), dtype=np.float64)
        # 5 pixels but very low energy: 5 * 10 * 0.01 = 0.5 keV < 1.0
        for i in range(5):
            data[10, 10 + i] = 10  # below threshold! won't even be labeled
        bbox = BoundingBox(0, 0, 20, 20)
        results = _run_extract(_make_extractor(), data, bbox)
        assert results == []

    def test_energy_minimum_param(self):
        data = np.zeros((20, 20), dtype=np.float64)
        # 5 pixels: total energy = 5*500*0.01 = 25 keV
        for i in range(5):
            data[10, 10 + i] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        # Set minimum to 30 keV — should filter out
        results = _run_extract(
            _make_extractor(), data, bbox, energyMinimum=30.0
        )
        assert results == []

    def test_energy_maximum_param(self):
        data = np.zeros((20, 20), dtype=np.float64)
        # 5 pixels: total energy = 5*500*0.01 = 25 keV
        for i in range(5):
            data[10, 10 + i] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        # Set maximum to 10 keV — should filter out
        results = _run_extract(
            _make_extractor(), data, bbox, energyMaximum=10.0
        )
        assert results == []

    def test_center_coords_global_frame(self):
        data = np.zeros((20, 20), dtype=np.float64)
        for i in range(5):
            data[10, 10 + i] = 500
        # Peak is at the highest value — all equal, so first pixel
        data[10, 12] = 1000  # make peak at col 12
        bbox = BoundingBox(top=100, left=200, bottom=120, right=220)
        results = _run_extract(_make_extractor(), data, bbox)
        assert len(results) == 1
        assert results[0].centerX == 200 + 12
        assert results[0].centerY == 100 + 10

    def test_cancel_prevents_callback(self):
        data = np.zeros((20, 20), dtype=np.float64)
        for i in range(5):
            data[10, 10 + i] = 500
        bbox = BoundingBox(0, 0, 20, 20)
        extractor = _make_extractor()

        called = []
        worker_started = threading.Event()

        original_label = label

        def _synced_label(*args, **kwargs):
            worker_started.set()
            time.sleep(0.1)
            return original_label(*args, **kwargs)

        with patch.object(_oce_mod, 'label', _synced_label):
            extractor.extract(data, bbox, lambda e: called.extend(e))
            worker_started.wait(timeout=2)
            extractor.cancel()

        time.sleep(0.2)
        assert called == []
