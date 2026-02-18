import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.RoiRect import RoiRect


# --- Geometry ---


def test_initial_geometry():
    """Test that RoiRect stores the initial bounding box."""
    roi = RoiRect(10, 20, 50, 80)
    bbox = roi.geometry()
    assert bbox == BoundingBox(10, 20, 50, 80)


def test_set_geometry():
    """Test that set_geometry updates the bounding box."""
    roi = RoiRect(0, 0, 1, 1)
    roi.set_geometry(5, 10, 15, 20)
    bbox = roi.geometry()
    assert bbox == BoundingBox(5, 10, 15, 20)


# --- extract_raw_data ---


def test_extract_raw_data_valid():
    """Test extracting a sub-region from 2D raw data."""
    data = np.arange(100).reshape(10, 10)
    roi = RoiRect(2, 3, 5, 7)
    result = roi.extract_raw_data(data)
    assert result is not None
    assert result.shape == (3, 4)
    np.testing.assert_array_equal(result, data[2:5, 3:7])


def test_extract_raw_data_returns_copy():
    """Test that extract_raw_data returns a copy, not a view."""
    data = np.ones((10, 10))
    roi = RoiRect(0, 0, 5, 5)
    result = roi.extract_raw_data(data)
    result[0, 0] = 999
    assert data[0, 0] == 1.0


def test_extract_raw_data_clamped():
    """Test that ROI is clamped to source array bounds."""
    data = np.arange(25).reshape(5, 5)
    roi = RoiRect(-2, -3, 3, 3)
    result = roi.extract_raw_data(data)
    assert result is not None
    assert result.shape == (3, 3)
    np.testing.assert_array_equal(result, data[0:3, 0:3])


def test_extract_raw_data_fully_outside():
    """Test that ROI fully outside returns None."""
    data = np.ones((10, 10))
    roi = RoiRect(20, 20, 30, 30)
    result = roi.extract_raw_data(data)
    assert result is None


def test_extract_raw_data_zero_area():
    """Test that zero-area ROI returns None."""
    data = np.ones((10, 10))
    roi = RoiRect(5, 5, 5, 5)
    result = roi.extract_raw_data(data)
    assert result is None


def test_extract_raw_data_overflow_clamped():
    """Test that ROI extending beyond bottom-right is clamped."""
    data = np.arange(25).reshape(5, 5)
    roi = RoiRect(3, 3, 100, 100)
    result = roi.extract_raw_data(data)
    assert result is not None
    assert result.shape == (2, 2)
    np.testing.assert_array_equal(result, data[3:5, 3:5])


# --- extract_rendered_region ---


def test_extract_rendered_region():
    """Test extracting from an RGB buffer (H, W, 3)."""
    rendered = np.zeros((10, 10, 3), dtype=np.uint8)
    rendered[2:5, 3:7, :] = 128
    roi = RoiRect(2, 3, 5, 7)
    result = roi.extract_rendered_region(rendered)
    assert result is not None
    assert result.shape == (3, 4, 3)
    assert np.all(result == 128)


# --- run_clustering ---


def test_run_clustering_noop():
    """Test that run_clustering does not raise."""
    roi = RoiRect(0, 0, 10, 10)
    roi.run_clustering()


# --- Equality ---


def test_equality():
    """Test that two RoiRects with the same geometry are equal."""
    a = RoiRect(1, 2, 3, 4)
    b = RoiRect(1, 2, 3, 4)
    assert a == b


def test_inequality():
    """Test that different RoiRects are not equal."""
    a = RoiRect(1, 2, 3, 4)
    b = RoiRect(1, 2, 3, 5)
    assert a != b


def test_equality_with_non_roi():
    """Test equality with a non-RoiRect returns NotImplemented."""
    roi = RoiRect(1, 2, 3, 4)
    assert roi.__eq__("not a roi") is NotImplemented


# --- repr ---


def test_repr():
    """Test repr output."""
    roi = RoiRect(10, 20, 30, 40)
    assert repr(roi) == "RoiRect(top=10, left=20, bottom=30, right=40)"
