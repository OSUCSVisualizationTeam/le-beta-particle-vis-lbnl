# Citation for Unit Tests: Validates generation of uint8 thumbnails from cluster energy data
# Date: 23/02/2026
# Adapted from Claude Code:
# "Identify headless test cases for the clustered event widget to avoid Qt dependencies in CI."

import numpy as np

from le_beta_vis.frontend.fitsconverters.cluster_thumbnail import (
    generate_cluster_thumbnail,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap


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


def test_rgb_with_colormap():
    """Colormap produces 3-channel RGB output."""
    data = np.random.rand(7, 12) * 50
    result = generate_cluster_thumbnail(data, colormap=Colormap.VIRIDIS)
    assert result.dtype == np.uint8
    assert result.ndim == 3
    assert result.shape == (7, 12, 3)


def test_empty_data_rgb_fallback():
    """Empty data with colormap returns 3-channel fallback."""
    result = generate_cluster_thumbnail(
        None, colormap=Colormap.PLASMA
    )
    assert result.shape == (48, 48, 3)
    assert result.dtype == np.uint8
    assert (result == 0).all()


def test_none_colormap_returns_grayscale():
    """Explicit colormap=None produces 2D grayscale."""
    data = np.random.rand(5, 5) * 100
    result = generate_cluster_thumbnail(data, colormap=None)
    assert result.ndim == 2


def test_pad_to_square_default_false():
    """Default behavior preserves the input shape (no padding)."""
    data = np.random.rand(3, 9) * 100
    result = generate_cluster_thumbnail(data)
    assert result.shape == (3, 9)


def test_pad_to_square_grayscale_non_square():
    """pad_to_square=True pads a non-square grayscale buffer to a square."""
    data = np.random.rand(3, 9) * 100
    result = generate_cluster_thumbnail(data, pad_to_square=True)
    assert result.shape == (9, 9)
    assert result.dtype == np.uint8
    # Padding rows above and below the data block must be zero.
    # 3 rows centered in 9 -> top pad = (9-3)//2 = 3, bottom pad = 3.
    assert (result[:3, :] == 0).all()
    assert (result[-3:, :] == 0).all()
    # The 3 middle rows contain the converted data and may be non-zero.
    assert result[3:6, :].shape == (3, 9)


def test_pad_to_square_rgb_non_square():
    """pad_to_square=True pads an RGB buffer to a square with zero fill."""
    data = np.random.rand(3, 9) * 100
    result = generate_cluster_thumbnail(
        data, colormap=Colormap.VIRIDIS, pad_to_square=True
    )
    assert result.shape == (9, 9, 3)
    assert result.dtype == np.uint8
    assert (result[:3, :, :] == 0).all()
    assert (result[-3:, :, :] == 0).all()


def test_pad_to_square_no_op_on_square():
    """pad_to_square=True is a no-op when the input is already square."""
    data = np.random.rand(7, 7) * 100
    result = generate_cluster_thumbnail(data, pad_to_square=True)
    assert result.shape == (7, 7)


def test_pad_to_square_tall_grayscale():
    """A tall (more rows than cols) input is padded horizontally."""
    data = np.random.rand(9, 3) * 100
    result = generate_cluster_thumbnail(data, pad_to_square=True)
    assert result.shape == (9, 9)
    assert (result[:, :3] == 0).all()
    assert (result[:, -3:] == 0).all()
