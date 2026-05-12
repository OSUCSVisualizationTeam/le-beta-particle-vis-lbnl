import numpy as np

from le_beta_vis.common.VizFilter import (
    ScalingFunction,
    UniformFilter,
    UniformVizFilter,
)
from le_beta_vis.frontend.fitsconverters import Colormap
from le_beta_vis.frontend.fitsconverters.RenderPipeline import (
    ColormapStage,
    FilterStage,
    RenderPipeline,
)


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
# ColormapStage — trusts Window to deliver [0, 1]; no per-frame stretch
# ---------------------------------------------------------------------------


def test_colormap_stage_enabled_produces_rgb_uint8():
    stage = ColormapStage(Colormap.VIRIDIS, enabled=True)
    data = np.linspace(0.0, 1.0, num=16).reshape(4, 4)
    out = stage.apply(data)
    assert out.dtype == np.uint8
    assert out.shape == (4, 4, 3)


def test_colormap_stage_disabled_grayscale_from_unit_interval():
    """Disabled colormap maps a [0, 1] input straight to a uint8 ramp.

    No min/max stretch — Window has already normalised, and an extra
    stretch here would silently override the user's chosen window.
    """
    stage = ColormapStage(Colormap.VIRIDIS, enabled=False)
    data = np.array([[0.0, 0.5], [0.5, 1.0]])
    out = stage.apply(data)
    assert out.dtype == np.uint8
    assert out.shape == (2, 2, 3)
    assert out[0, 0, 0] == 0
    assert out[1, 1, 0] == 255
    # Mid value rounds to 127 (0.5 * 255 = 127.5 → 127 after astype).
    assert out[0, 1, 0] == 127
    assert np.array_equal(out[..., 0], out[..., 1])
    assert np.array_equal(out[..., 1], out[..., 2])


def test_colormap_stage_disabled_clips_values_outside_unit_interval():
    """Defensive: if a buggy upstream emits values outside [0, 1],
    grayscale conversion clips rather than blowing up."""
    stage = ColormapStage(Colormap.VIRIDIS, enabled=False)
    out = stage.apply(np.array([[-0.5, 1.5]]))
    assert out[0, 0, 0] == 0
    assert out[0, 1, 0] == 255


def test_colormap_stage_disabled_empty_input_returns_empty():
    stage = ColormapStage(Colormap.VIRIDIS, enabled=False)
    out = stage.apply(np.array([]))
    assert out.size == 0
    assert out.dtype == np.uint8


# ---------------------------------------------------------------------------
# RenderPipeline (end-to-end)
# ---------------------------------------------------------------------------


def _pinned_chain(vmin: float, vmax: float) -> list:
    """Helper: ADU→keV / Linear ScalePreset / Window in pipeline order."""
    return [
        UniformFilter.ADUtoKeV(factor=1.02857e-5),
        UniformFilter.ScalePreset(mode=ScalingFunction.LINEAR),
        UniformFilter.Window(vmin=vmin, vmax=vmax),
    ]


def test_render_pipeline_pinned_chain_produces_rgb_buffer():
    """End-to-end smoke test: raw ADU input flows through the canonical
    pinned chain into an RGB buffer with the same shape as the input."""
    data = np.linspace(0.0, 100000.0, num=64).reshape(8, 8)
    pipeline = RenderPipeline(
        filters=_pinned_chain(0.0, 1.0),
        colormap=Colormap.VIRIDIS,
        colormap_enabled=True,
    )
    out = pipeline.render(data)
    assert out.shape == (8, 8, 3)
    assert out.dtype == np.uint8


def test_render_pipeline_user_filter_changes_output():
    """A user filter inserted between ADU→keV and ScalePreset must
    visibly alter the rendered buffer."""
    data = np.linspace(0.0, 100000.0, num=16).reshape(4, 4)

    plain = RenderPipeline(
        filters=_pinned_chain(0.0, 1.0),
        colormap=Colormap.VIRIDIS,
    ).render(data)

    with_offset = RenderPipeline(
        filters=[
            UniformFilter.ADUtoKeV(factor=1.02857e-5),
            UniformFilter.Add(value=0.5),
            UniformFilter.ScalePreset(mode=ScalingFunction.LINEAR),
            UniformFilter.Window(vmin=0.0, vmax=1.0),
        ],
        colormap=Colormap.VIRIDIS,
    ).render(data)

    assert plain.shape == with_offset.shape
    assert not np.array_equal(plain, with_offset)


def test_render_pipeline_none_input_returns_empty():
    pipeline = RenderPipeline(
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
        filters=[],
        colormap=Colormap.VIRIDIS,
        converter=converter,
    )
    out = pipeline.render(np.zeros((4, 4)))

    converter.convert.assert_called_once()
    assert out is fake_buffer


def test_render_pipeline_empty_filter_chain_passes_raw_input_to_converter():
    """With no filters the converter sees the raw input verbatim; this
    guards the FilterStage-is-identity contract."""
    from unittest.mock import MagicMock

    converter = MagicMock()
    converter.convert.return_value = np.zeros((1, 1, 3), dtype=np.uint8)

    pipeline = RenderPipeline(
        filters=[],
        colormap=Colormap.VIRIDIS,
        converter=converter,
    )
    data = np.array([[0.25, 0.75]])
    pipeline.render(data)

    args, _ = converter.convert.call_args
    np.testing.assert_array_equal(args[0], data)
