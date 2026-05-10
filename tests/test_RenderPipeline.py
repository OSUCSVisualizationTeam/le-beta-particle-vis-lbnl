import numpy as np
import pytest

from le_beta_vis.common.VizFilter import UniformVizFilter
from le_beta_vis.frontend.fitsconverters import Colormap, ScalingFunction
from le_beta_vis.frontend.fitsconverters.RenderPipeline import (
    ColormapStage,
    FilterStage,
    RenderPipeline,
    ScaleStage,
)


# ---------------------------------------------------------------------------
# ScaleStage
# ---------------------------------------------------------------------------


def test_scale_stage_linear_normalises_to_unit_interval():
    stage = ScaleStage(ScalingFunction.LINEAR, (0.0, 10.0))
    out = stage.apply(np.array([0.0, 5.0, 10.0]))
    assert np.allclose(out, [0.0, 0.5, 1.0])


def test_scale_stage_clips_above_vmax():
    stage = ScaleStage(ScalingFunction.LINEAR, (0.0, 10.0))
    out = stage.apply(np.array([12.0, 20.0]))
    assert np.allclose(out, [1.0, 1.0])


def test_scale_stage_clips_below_zero_when_vmin_is_zero():
    stage = ScaleStage(ScalingFunction.LINEAR, (0.0, 10.0))
    out = stage.apply(np.array([-3.0, 5.0]))
    assert np.allclose(out, [0.0, 0.5])


def test_scale_stage_clips_below_vmin_when_positive():
    stage = ScaleStage(ScalingFunction.LINEAR, (5.0, 10.0))
    out = stage.apply(np.array([2.0, 5.0, 7.5, 10.0]))
    assert np.allclose(out, [0.0, 0.0, 0.5, 1.0])


def test_scale_stage_log_uses_log1p_normalisation():
    stage = ScaleStage(ScalingFunction.LOG, (0.0, 10.0))
    out = stage.apply(np.array([0.0, 10.0]))
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1.0)


def test_scale_stage_sqrt_uses_sqrt_normalisation():
    stage = ScaleStage(ScalingFunction.SQRT, (0.0, 4.0))
    out = stage.apply(np.array([0.0, 1.0, 4.0]))
    assert np.allclose(out, [0.0, 0.5, 1.0])


def test_scale_stage_zero_width_vrange_uses_safe_denom():
    """vmax == vmin would otherwise divide by zero; the stage falls
    back to denom = 1 so the call is safe."""
    stage = ScaleStage(ScalingFunction.LINEAR, (5.0, 5.0))
    out = stage.apply(np.array([5.0, 5.0]))
    # Clipped values - vmin = 0, divided by 1 = 0
    assert np.allclose(out, [0.0, 0.0])


# ---------------------------------------------------------------------------
# FilterStage
# ---------------------------------------------------------------------------


class _ScalarMultiplyFilter(UniformVizFilter):
    """Local fixture filter — keeps the test independent of skimage."""

    def __init__(self, factor: float) -> None:
        self._factor = factor

    def filter(self, matrix):
        return matrix * self._factor


class _AddFilter(UniformVizFilter):
    def __init__(self, value: float) -> None:
        self._value = value

    def filter(self, matrix):
        return matrix + self._value


def test_filter_stage_empty_chain_is_identity():
    stage = FilterStage([])
    arr = np.array([0.1, 0.5, 0.9])
    out = stage.apply(arr)
    assert np.array_equal(out, arr)


def test_filter_stage_applies_single_filter():
    stage = FilterStage([_ScalarMultiplyFilter(2.0)])
    out = stage.apply(np.array([1.0, 2.0]))
    assert np.allclose(out, [2.0, 4.0])


def test_filter_stage_applies_filters_in_order():
    """Multiplicative followed by additive must produce (x*2)+1, not
    (x+1)*2 — this catches order-sensitivity regressions."""
    stage = FilterStage([_ScalarMultiplyFilter(2.0), _AddFilter(1.0)])
    out = stage.apply(np.array([1.0, 2.0]))
    assert np.allclose(out, [3.0, 5.0])


# ---------------------------------------------------------------------------
# ColormapStage
# ---------------------------------------------------------------------------


def test_colormap_stage_enabled_produces_rgb_uint8():
    stage = ColormapStage(Colormap.VIRIDIS, enabled=True)
    data = np.linspace(0.0, 1.0, num=16).reshape(4, 4)
    out = stage.apply(data)
    assert out.dtype == np.uint8
    assert out.shape == (4, 4, 3)


def test_colormap_stage_disabled_grayscale_ramp():
    stage = ColormapStage(Colormap.VIRIDIS, enabled=False)
    data = np.array([[0.0, 1.0], [2.0, 3.0]])
    out = stage.apply(data)
    assert out.dtype == np.uint8
    assert out.shape == (2, 2, 3)
    # Expect min → 0, max → 255, all three channels equal (grayscale)
    assert out[0, 0, 0] == 0
    assert out[1, 1, 0] == 255
    assert np.array_equal(out[..., 0], out[..., 1])
    assert np.array_equal(out[..., 1], out[..., 2])


def test_colormap_stage_disabled_constant_input_is_zero():
    """When all values are equal, denom is 0; the stage emits a black
    buffer rather than blowing up on division."""
    stage = ColormapStage(Colormap.VIRIDIS, enabled=False)
    out = stage.apply(np.full((3, 3), 42.0))
    assert out.dtype == np.uint8
    assert np.all(out == 0)


def test_colormap_stage_disabled_empty_input_returns_empty():
    stage = ColormapStage(Colormap.VIRIDIS, enabled=False)
    out = stage.apply(np.array([]))
    assert out.size == 0
    assert out.dtype == np.uint8


# ---------------------------------------------------------------------------
# RenderPipeline (end-to-end)
# ---------------------------------------------------------------------------


def test_render_pipeline_empty_filter_chain_matches_legacy_converter():
    """With an empty filter chain, the new pipeline must produce a
    byte-identical buffer to the old monolithic OpenCVBasedConverter
    call shape used by RawDataViewModel."""
    from le_beta_vis.frontend.fitsconverters.opencv import OpenCVBasedConverter

    data = np.linspace(0.0, 50.0, num=64).reshape(8, 8)
    legacy = OpenCVBasedConverter().convert(
        data, Colormap.VIRIDIS, (0.0, 20.0), ScalingFunction.LINEAR,
    )

    pipeline = RenderPipeline(
        scaling=ScalingFunction.LINEAR,
        vrange=(0.0, 20.0),
        filters=[],
        colormap=Colormap.VIRIDIS,
        colormap_enabled=True,
    )
    new = pipeline.render(data)

    assert new.shape == legacy.shape
    assert np.array_equal(new, legacy)


def test_render_pipeline_with_filter_changes_output():
    data = np.linspace(0.0, 1.0, num=16).reshape(4, 4)

    pipeline_plain = RenderPipeline(
        scaling=ScalingFunction.LINEAR,
        vrange=(0.0, 1.0),
        filters=[],
        colormap=Colormap.VIRIDIS,
    )
    pipeline_filtered = RenderPipeline(
        scaling=ScalingFunction.LINEAR,
        vrange=(0.0, 1.0),
        filters=[_ScalarMultiplyFilter(0.5)],
        colormap=Colormap.VIRIDIS,
    )

    plain = pipeline_plain.render(data)
    filtered = pipeline_filtered.render(data)

    assert plain.shape == filtered.shape
    assert not np.array_equal(plain, filtered)


def test_render_pipeline_none_input_returns_empty():
    pipeline = RenderPipeline(
        scaling=ScalingFunction.LINEAR,
        vrange=(0.0, 1.0),
        filters=[],
        colormap=Colormap.VIRIDIS,
    )
    out = pipeline.render(None)
    assert out.size == 0


def test_render_pipeline_uses_injected_converter():
    """RawDataViewModel relies on injection so test mocks of
    `vm._converter` continue to work — guard that contract here."""
    from unittest.mock import MagicMock

    fake_buffer = np.zeros((4, 4, 3), dtype=np.uint8)
    converter = MagicMock()
    converter.convert.return_value = fake_buffer

    pipeline = RenderPipeline(
        scaling=ScalingFunction.LINEAR,
        vrange=(0.0, 1.0),
        filters=[],
        colormap=Colormap.VIRIDIS,
        converter=converter,
    )
    out = pipeline.render(np.zeros((4, 4)))

    converter.convert.assert_called_once()
    assert out is fake_buffer
