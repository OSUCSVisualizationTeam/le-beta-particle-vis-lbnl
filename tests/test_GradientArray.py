"""
Pure-NumPy tests for ``generate_gradient_array``.

No QApplication — safe for headless CI.

References
----------
Issue #90 — Dynamic Gradient Rendering in VerticalRangeControl
"""
import numpy as np

from le_beta_vis.frontend.fitsconverters.colormaps import (
    generate_gradient_array,
)


class TestGradientArrayShape:
    """Basic shape, dtype, and default behaviour."""

    def test_default_shape_and_dtype(self):
        arr = generate_gradient_array("viridis")
        assert arr.shape == (256, 20, 3)
        assert arr.dtype == np.uint8

    def test_custom_dimensions(self):
        arr = generate_gradient_array("viridis", width=10, height=128)
        assert arr.shape == (128, 10, 3)

    def test_full_range_matches_default(self):
        default = generate_gradient_array("viridis")
        explicit = generate_gradient_array("viridis", 0.0, 1.0)
        np.testing.assert_array_equal(default, explicit)


class TestEndcapColors:
    """Rows outside the active range should be flat end-cap colors."""

    def test_top_endcap_uniform(self):
        arr = generate_gradient_array("viridis", 0.0, 0.5, height=100)
        # Top row (index 0) corresponds to position 1.0, which is above
        # vmax_ratio=0.5 → should be clamped to top color.
        top_color = arr[0, 0]
        # All rows in the top ~half should share this color.
        for row in range(0, 40):
            np.testing.assert_array_equal(arr[row, 0], top_color)

    def test_bottom_endcap_uniform(self):
        arr = generate_gradient_array("viridis", 0.5, 1.0, height=100)
        bottom_color = arr[-1, 0]
        for row in range(61, 100):
            np.testing.assert_array_equal(arr[row, 0], bottom_color)


class TestDegenerateRange:
    """When vmin_ratio == vmax_ratio the array is a single color."""

    def test_single_color(self):
        arr = generate_gradient_array("viridis", 0.5, 0.5, height=64)
        first_pixel = arr[0, 0]
        for row in range(64):
            np.testing.assert_array_equal(arr[row, 0], first_pixel)


class TestRatioCorrectionAndClamping:
    """Swapped and out-of-bounds ratios are auto-corrected."""

    def test_swapped_ratios_auto_corrected(self):
        normal = generate_gradient_array("viridis", 0.2, 0.8)
        swapped = generate_gradient_array("viridis", 0.8, 0.2)
        np.testing.assert_array_equal(normal, swapped)

    def test_out_of_bounds_clamped(self):
        clamped = generate_gradient_array("viridis", -0.5, 1.5)
        full = generate_gradient_array("viridis", 0.0, 1.0)
        np.testing.assert_array_equal(clamped, full)


class TestColormapVariation:
    """Different colormaps should produce different pixel data."""

    def test_different_colormaps_differ(self):
        a = generate_gradient_array("viridis")
        b = generate_gradient_array("plasma")
        assert not np.array_equal(a, b)


class TestRowUniformity:
    """All columns within a single row must be identical."""

    def test_columns_identical(self):
        arr = generate_gradient_array("inferno", 0.1, 0.9, width=30)
        for row in range(arr.shape[0]):
            first_col = arr[row, 0]
            for col in range(1, arr.shape[1]):
                np.testing.assert_array_equal(arr[row, col], first_col)
