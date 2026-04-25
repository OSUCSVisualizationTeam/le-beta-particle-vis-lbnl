"""Tests for the shared Colormap LUT module."""
from __future__ import annotations

import numpy as np

from le_beta_vis.common.Colormap import Colormap
from le_beta_vis.common.ColormapLUT import colormap_lut, resolve_colormap


class TestColormapLUT:
    def test_lut_shape_and_dtype_for_all_colormaps(self) -> None:
        for cm in Colormap:
            lut = colormap_lut(cm)
            assert lut.shape == (256, 3), f"{cm} produced shape {lut.shape}"
            assert lut.dtype == np.uint8, f"{cm} produced dtype {lut.dtype}"

    def test_grayscale_lut_is_identity_ramp(self) -> None:
        lut = colormap_lut(Colormap.GRAYSCALE)
        assert np.array_equal(lut[:, 0], lut[:, 1])
        assert np.array_equal(lut[:, 1], lut[:, 2])
        assert int(lut[0, 0]) == 0
        assert int(lut[255, 0]) == 255
        assert (np.diff(lut[:, 0].astype(np.int16)) >= 0).all()

    def test_lut_is_cached(self) -> None:
        lut_a = colormap_lut(Colormap.VIRIDIS)
        lut_b = colormap_lut(Colormap.VIRIDIS)
        assert lut_a is lut_b


class TestResolveColormap:
    def test_valid_name_returns_enum(self) -> None:
        assert resolve_colormap("viridis") is Colormap.VIRIDIS
        assert resolve_colormap("grayscale") is Colormap.GRAYSCALE

    def test_invalid_name_returns_none(self) -> None:
        assert resolve_colormap("bogus") is None

    def test_none_returns_none(self) -> None:
        assert resolve_colormap(None) is None
