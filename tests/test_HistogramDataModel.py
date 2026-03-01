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
