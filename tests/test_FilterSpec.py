import numpy as np
import pytest

from le_beta_vis.common.FilterSpec import (
    FilterSpec,
    ParameterSpec,
    ParameterType,
    UIHint,
)
from le_beta_vis.common.VizFilter import UniformFilter


# ---------------------------------------------------------------------------
# ParameterSpec
# ---------------------------------------------------------------------------


def test_parameter_spec_defaults():
    p = ParameterSpec(name="x", label="x")
    assert p.type is ParameterType.FLOAT
    assert p.min_value is None
    assert p.max_value is None
    assert p.ui_hint is UIHint.AUTO


def test_parameter_spec_clamp_below_min():
    p = ParameterSpec(name="x", label="x", min_value=0.0, max_value=10.0)
    assert p.clamp(-1.0) == 0.0


def test_parameter_spec_clamp_above_max():
    p = ParameterSpec(name="x", label="x", min_value=0.0, max_value=10.0)
    assert p.clamp(99.0) == 10.0


def test_parameter_spec_clamp_inside_range_unchanged():
    p = ParameterSpec(name="x", label="x", min_value=0.0, max_value=10.0)
    assert p.clamp(5.0) == 5.0


def test_parameter_spec_clamp_unbounded_passes_through():
    p = ParameterSpec(name="x", label="x")
    assert p.clamp(1e6) == 1e6
    assert p.clamp(-1e6) == -1e6


def test_parameter_spec_clamp_int_type_coerces():
    p = ParameterSpec(
        name="n", label="n", type=ParameterType.INT, min_value=1, max_value=10,
    )
    result = p.clamp(3.7)
    assert result == 3
    assert isinstance(result, int)


def test_parameter_spec_clamp_int_above_max():
    p = ParameterSpec(
        name="n", label="n", type=ParameterType.INT, min_value=1, max_value=10,
    )
    result = p.clamp(99)
    assert result == 10
    assert isinstance(result, int)


def test_parameter_spec_clamp_enum_passes_through():
    p = ParameterSpec(
        name="mode",
        label="mode",
        type=ParameterType.ENUM,
        enum_values=("a", "b", "c"),
    )
    assert p.clamp("b") == "b"


def test_parameter_spec_is_frozen():
    p = ParameterSpec(name="x", label="x")
    with pytest.raises(Exception):
        p.name = "renamed"  # frozen dataclass — assignment forbidden


# ---------------------------------------------------------------------------
# FilterSpec
# ---------------------------------------------------------------------------


def test_filter_spec_construction():
    spec = FilterSpec(
        type_id="t",
        display_name="Test",
        parameters=[ParameterSpec(name="x", label="x")],
    )
    assert spec.type_id == "t"
    assert spec.display_name == "Test"
    assert len(spec.parameters) == 1
    assert spec.filter_class is None


def test_filter_spec_defaults_to_empty_parameters():
    spec = FilterSpec(type_id="empty", display_name="Empty")
    assert spec.parameters == []


def test_filter_spec_is_frozen():
    spec = FilterSpec(type_id="t", display_name="T")
    with pytest.raises(Exception):
        spec.display_name = "renamed"


# ---------------------------------------------------------------------------
# Gaussian.SPEC integrity
# ---------------------------------------------------------------------------


def test_gaussian_spec_shape():
    spec = UniformFilter.Gaussian.SPEC
    assert spec.type_id == "gaussian_blur"
    assert spec.display_name == "Gaussian Blur"
    assert spec.filter_class is UniformFilter.Gaussian
    assert len(spec.parameters) == 1


def test_gaussian_spec_sigma_parameter():
    sigma_param = UniformFilter.Gaussian.SPEC.parameters[0]
    assert sigma_param.name == "sigma"
    assert sigma_param.label == "σ"
    assert sigma_param.type is ParameterType.FLOAT
    assert sigma_param.min_value == 0.1
    assert sigma_param.max_value == 10.0
    assert sigma_param.default == 1.5


def test_gaussian_sigma_is_public_attribute():
    g = UniformFilter.Gaussian(sigma=2.5)
    assert g.sigma == 2.5
    g.sigma = 3.0
    assert g.sigma == 3.0


def test_gaussian_default_sigma_matches_spec_default():
    g = UniformFilter.Gaussian()
    assert g.sigma == UniformFilter.Gaussian.SPEC.parameters[0].default


def test_gaussian_filter_runs_on_ndarray():
    g = UniformFilter.Gaussian(sigma=1.0)
    data = np.zeros((8, 8), dtype=float)
    data[4, 4] = 1.0
    out = g.filter(data)
    assert out.shape == data.shape
    assert out[4, 4] > 0  # smoothed spike still strongest at the source
