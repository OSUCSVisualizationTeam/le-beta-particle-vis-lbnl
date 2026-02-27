# Citation for Unit Tests: Validates weighted-mean sigma computation
# Date: 23/02/2026
# Adapted from Claude Code:
# "Implement compute_cluster_sigmas utility and verify against known values"

"""Tests for compute_cluster_sigmas."""

import numpy as np
import pytest

from le_beta_vis.common.cluster_sigma import compute_cluster_sigmas


def test_zero_data_returns_zeros():
    """All-zero array returns (0.0, 0.0)."""
    data = np.zeros((5, 5), dtype=float)
    sx, sy = compute_cluster_sigmas(data)
    assert sx == 0.0
    assert sy == 0.0


def test_empty_data_returns_zeros():
    """Empty array returns (0.0, 0.0)."""
    data = np.zeros((0, 0), dtype=float)
    sx, sy = compute_cluster_sigmas(data)
    assert sx == 0.0
    assert sy == 0.0


def test_single_pixel_returns_zeros():
    """A single non-zero pixel has no spread."""
    data = np.zeros((5, 5), dtype=float)
    data[2, 2] = 100.0
    sx, sy = compute_cluster_sigmas(data)
    assert sx == 0.0
    assert sy == 0.0


def test_horizontal_spread():
    """Spread along x-axis gives sigma_x > 0 and sigma_y == 0."""
    data = np.zeros((1, 5), dtype=float)
    data[0, :] = [1.0, 2.0, 4.0, 2.0, 1.0]
    sx, sy = compute_cluster_sigmas(data)
    assert sx > 0.0
    assert sy == 0.0


def test_vertical_spread():
    """Spread along y-axis gives sigma_y > 0 and sigma_x == 0."""
    data = np.zeros((5, 1), dtype=float)
    data[:, 0] = [1.0, 2.0, 4.0, 2.0, 1.0]
    sx, sy = compute_cluster_sigmas(data)
    assert sx == 0.0
    assert sy > 0.0


def test_symmetric_gaussian():
    """Symmetric distribution gives approximately equal sigmas."""
    data = np.zeros((5, 5), dtype=float)
    # Place identical weights symmetrically around center
    data[2, 2] = 10.0
    data[1, 2] = 5.0
    data[3, 2] = 5.0
    data[2, 1] = 5.0
    data[2, 3] = 5.0
    sx, sy = compute_cluster_sigmas(data)
    assert sx == pytest.approx(sy, abs=1e-10)


def test_known_values():
    """Hand-computed weighted sigma for a simple 3-pixel row."""
    # Three pixels at cols 0, 1, 2 with equal weight 1.0 each
    # mean_x = (0*1 + 1*1 + 2*1) / 3 = 1.0
    # var_x = (1*(0-1)^2 + 1*(1-1)^2 + 1*(2-1)^2) / 3 = 2/3
    # sigma_x = sqrt(2/3)
    data = np.array([[1.0, 1.0, 1.0]])
    sx, sy = compute_cluster_sigmas(data)
    assert sx == pytest.approx(np.sqrt(2.0 / 3.0), abs=1e-10)
    assert sy == 0.0


def test_negative_values_treated_as_weight():
    """Negative values reduce total weight; all-negative returns zeros."""
    data = np.full((3, 3), -1.0)
    sx, sy = compute_cluster_sigmas(data)
    assert sx == 0.0
    assert sy == 0.0
