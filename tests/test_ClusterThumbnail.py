# Citation for Unit Tests: Validates generation of uint8 thumbnails from cluster energy data
# Date: 23/02/2026
# Adapted from Claude Code:
# "Identify headless test cases for the clustered event widget to avoid Qt dependencies in CI."

import numpy as np

from le_beta_vis.frontend.fitsconverters.cluster_thumbnail import (
    generate_cluster_thumbnail,
)


def test_returns_uint8():
    """Output is a uint8 numpy array."""
    data = np.random.rand(5, 5) * 100
    result = generate_cluster_thumbnail(data)
    assert result.dtype == np.uint8


def test_shape_matches_input():
    """Output shape matches input data dimensions."""
    data = np.random.rand(7, 12) * 50
    result = generate_cluster_thumbnail(data)
    assert result.shape == (7, 12)


def test_empty_data_returns_fallback():
    """Empty array returns fallback-sized zero buffer."""
    data = np.array([], dtype=float)
    result = generate_cluster_thumbnail(data)
    assert result.shape == (48, 48)
    assert result.dtype == np.uint8
    assert (result == 0).all()


def test_none_data_returns_fallback():
    """None input returns fallback-sized zero buffer."""
    result = generate_cluster_thumbnail(None)
    assert result.shape == (48, 48)
    assert result.dtype == np.uint8
    assert (result == 0).all()


def test_custom_fallback_size():
    """Custom fallback_size is used for empty input."""
    result = generate_cluster_thumbnail(None, fallback_size=(32, 32))
    assert result.shape == (32, 32)


def test_single_pixel():
    """Single pixel array produces valid thumbnail."""
    data = np.array([[42.0]])
    result = generate_cluster_thumbnail(data)
    assert result.shape == (1, 1)
    assert result.dtype == np.uint8


def test_all_zeros():
    """All-zero input produces valid output."""
    data = np.zeros((5, 5), dtype=float)
    result = generate_cluster_thumbnail(data)
    assert result.shape == (5, 5)
    assert result.dtype == np.uint8
