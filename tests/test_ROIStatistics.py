# Citation for Unit Tests: ROIStatistics pure-Python tests
# Date: 28/02/2026
# Adapted from Claude Code:
# Write pure Python tests for ROIStatistics covering
# from_roi_data, coordinate offsets, edge cases, and keV conversion.

"""Tests for ROIStatistics.

Pure Python tests — no QApplication instantiation.
"""
from typing import Union

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.common.ROIStatistics import ROIStatistics


class _MockPhysics(PhysicsConversionManager):
    """Minimal mock with a fixed conversion factor of 0.01."""

    @property
    def kev_conversion_factor(self) -> float:
        return 0.01

    @property
    def pedestal_width(self) -> int:
        return 0

    def calculate_threshold(self, sigma: float) -> float:
        return 0.0

    def adu_to_kev(
        self, value: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        return value * 0.01


def _make_physics() -> _MockPhysics:
    return _MockPhysics()


def test_basic_statistics():
    """Known 2x2 array, verify all numeric fields."""
    data = np.array([[100, 200], [300, 0]])
    bbox = BoundingBox(top=0, left=0, bottom=2, right=2)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    assert stats.min_adu == 100.0
    assert stats.max_adu == 300.0
    assert abs(stats.min_kev - 1.0) < 1e-9
    assert abs(stats.max_kev - 3.0) < 1e-9

    nz = np.array([100, 200, 300], dtype=float)
    assert abs(stats.mean_adu - nz.mean()) < 1e-9
    assert abs(stats.sigma_adu - nz.std()) < 1e-9
    assert abs(stats.mean_kev - nz.mean() * 0.01) < 1e-9
    assert abs(stats.sigma_kev - nz.std() * 0.01) < 1e-9


def test_coordinates_absolute():
    """Verify bbox offset is applied to absolute coordinates."""
    data = np.array([[0, 500], [700, 0]])
    bbox = BoundingBox(top=10, left=20, bottom=12, right=22)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    # min is 500 at ROI (0, 1), max is 700 at ROI (1, 0)
    assert stats.min_roi_coord == (0, 1)
    assert stats.max_roi_coord == (1, 0)
    assert stats.min_abs_coord == (10, 21)
    assert stats.max_abs_coord == (11, 20)


def test_all_zero_data():
    """All-zero data gives zero statistics gracefully."""
    data = np.zeros((3, 3), dtype=int)
    bbox = BoundingBox(top=5, left=5, bottom=8, right=8)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    assert stats.min_adu == 0.0
    assert stats.max_adu == 0.0
    assert stats.mean_adu == 0.0
    assert stats.sigma_adu == 0.0
    assert stats.nonzero_count == 0
    assert stats.pixel_count == 9


def test_single_nonzero_pixel():
    """Single non-zero pixel: sigma should be 0."""
    data = np.array([[0, 0], [0, 42]])
    bbox = BoundingBox(top=0, left=0, bottom=2, right=2)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    assert stats.min_adu == 42.0
    assert stats.max_adu == 42.0
    assert stats.mean_adu == 42.0
    assert stats.sigma_adu == 0.0
    assert stats.nonzero_count == 1
    assert stats.min_roi_coord == (1, 1)
    assert stats.max_roi_coord == (1, 1)


def test_pixel_count():
    """Total vs non-zero pixel count."""
    data = np.array([[1, 0, 3], [0, 5, 0]])
    bbox = BoundingBox(top=0, left=0, bottom=2, right=3)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    assert stats.pixel_count == 6
    assert stats.nonzero_count == 3


def test_kev_uses_physics_manager():
    """Mock with known factor, verify keV values match."""
    data = np.array([[1000]])
    bbox = BoundingBox(top=0, left=0, bottom=1, right=1)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    assert abs(stats.min_kev - 10.0) < 1e-9
    assert abs(stats.max_kev - 10.0) < 1e-9
    assert abs(stats.mean_kev - 10.0) < 1e-9


def test_frozen_dataclass():
    """ROIStatistics should be immutable."""
    data = np.array([[100]])
    bbox = BoundingBox(top=0, left=0, bottom=1, right=1)
    stats = ROIStatistics.from_roi_data(data, bbox, _make_physics())

    try:
        stats.min_adu = 999.0
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass
