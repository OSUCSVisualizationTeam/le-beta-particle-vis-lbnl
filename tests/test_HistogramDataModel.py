# Citation for Unit Tests: HistogramDataModel pure-Python tests
# Date: 28/02/2026
# Adapted from Claude Code:
# Write pure Python tests for HistogramDataModel covering
# from_pixel_data, bin_centers, bin_widths, and edge cases.

"""Tests for HistogramDataModel.

Pure Python tests — no QApplication instantiation.
"""
import numpy as np

from le_beta_vis.common.HistogramDataModel import HistogramDataModel
from le_beta_vis.frontend.widgets.InteractiveHistogramWidget import (
    _format_value,
)


def test_from_pixel_data_normal():
    """Normal 2-D data produces valid counts and edges."""
    data = np.array([[100, 200], [300, 0]])
    model = HistogramDataModel.from_pixel_data(
        data, bins=5, x_label="Energy (ADU)",
    )
    assert model is not None
    assert len(model.counts) == 5
    assert len(model.bin_edges) == 6
    assert model.counts.sum() == 3  # three non-zero pixels


def test_from_pixel_data_all_zero():
    """All-zero data returns None."""
    data = np.zeros((4, 4))
    model = HistogramDataModel.from_pixel_data(
        data, bins=10, x_label="Energy (ADU)",
    )
    assert model is None


def test_from_pixel_data_2d():
    """2-D array is correctly flattened."""
    data = np.ones((3, 3))
    model = HistogramDataModel.from_pixel_data(
        data, bins=5, x_label="Energy (keV)",
    )
    assert model is not None
    assert model.counts.sum() == 9


def test_from_pixel_data_1d():
    """1-D array works without error."""
    data = np.array([10, 20, 0, 30, 0])
    model = HistogramDataModel.from_pixel_data(
        data, bins=3, x_label="Energy (ADU)",
    )
    assert model is not None
    assert model.counts.sum() == 3


def test_bin_centers():
    """bin_centers returns midpoints of bin edges."""
    edges = np.array([0.0, 1.0, 2.0, 3.0])
    counts = np.array([5, 10, 3])
    model = HistogramDataModel(
        counts=counts, bin_edges=edges, x_label="x",
    )
    expected = np.array([0.5, 1.5, 2.5])
    np.testing.assert_array_almost_equal(
        model.bin_centers, expected,
    )


def test_bin_widths():
    """bin_widths returns the width of each bin."""
    edges = np.array([0.0, 2.0, 5.0, 10.0])
    counts = np.array([1, 2, 3])
    model = HistogramDataModel(
        counts=counts, bin_edges=edges, x_label="x",
    )
    expected = np.array([2.0, 3.0, 5.0])
    np.testing.assert_array_almost_equal(
        model.bin_widths, expected,
    )


def test_x_label_passthrough():
    """x_label is stored as given."""
    data = np.array([1, 2, 3])
    model = HistogramDataModel.from_pixel_data(
        data, bins=2, x_label="Energy (keV)",
    )
    assert model is not None
    assert model.x_label == "Energy (keV)"


def test_colormap_passthrough():
    """colormap is stored as given."""
    data = np.array([1, 2, 3])
    model = HistogramDataModel.from_pixel_data(
        data, bins=2, x_label="x", colormap="viridis",
    )
    assert model is not None
    assert model.colormap == "viridis"


def test_colormap_default_none():
    """colormap defaults to None when not supplied."""
    data = np.array([1, 2, 3])
    model = HistogramDataModel.from_pixel_data(
        data, bins=2, x_label="x",
    )
    assert model is not None
    assert model.colormap is None


def test_x_unit_passthrough():
    """x_unit is stored as given."""
    data = np.array([1, 2, 3])
    model = HistogramDataModel.from_pixel_data(
        data, bins=2, x_label="Energy (keV)", x_unit="keV",
    )
    assert model is not None
    assert model.x_unit == "keV"


def test_x_unit_default_none():
    """x_unit defaults to None when not supplied."""
    data = np.array([1, 2, 3])
    model = HistogramDataModel.from_pixel_data(
        data, bins=2, x_label="x",
    )
    assert model is not None
    assert model.x_unit is None


def test_frozen_dataclass():
    """HistogramDataModel should be immutable."""
    edges = np.array([0.0, 1.0])
    counts = np.array([5])
    model = HistogramDataModel(
        counts=counts, bin_edges=edges, x_label="x",
    )
    try:
        model.x_label = "y"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


# --- _format_value tests ---


def test_format_value_large_bin_width():
    """ADU-scale bin width uses 2 decimal places."""
    assert _format_value(150.0, 62.0) == "150.00"


def test_format_value_small_bin_width():
    """keV-scale bin width uses enough decimals to show digits."""
    result = _format_value(0.0000156, 1.6e-5)
    # bin_width 1.6e-5 → floor(log10)=-5 → decimals=6
    assert result == "0.000016"


def test_format_value_zero_bin_width():
    """Zero bin width falls back to 2 decimal places."""
    assert _format_value(3.14159, 0.0) == "3.14"


def test_format_value_integer_scale():
    """Integer-scale values with large bin width use 2 decimals."""
    assert _format_value(3200.0, 100.0) == "3200.00"
