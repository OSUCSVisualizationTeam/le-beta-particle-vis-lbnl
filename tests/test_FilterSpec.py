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


# ---------------------------------------------------------------------------
# Add (Offset).SPEC integrity
# ---------------------------------------------------------------------------


def test_add_spec_shape():
    spec = UniformFilter.Add.SPEC
    assert spec.type_id == "add"
    assert spec.display_name == "Offset"
    assert spec.filter_class is UniformFilter.Add
    assert len(spec.parameters) == 1


def test_add_spec_value_parameter():
    p = UniformFilter.Add.SPEC.parameters[0]
    assert p.name == "value"
    assert p.label == "Value"
    assert p.type is ParameterType.FLOAT
    assert p.min_value is None
    assert p.max_value is None
    assert p.default == 0.0
    assert p.units == "ADU"


def test_add_value_is_public_attribute():
    f = UniformFilter.Add(value=500.0)
    assert f.value == 500.0
    f.value = 200.0
    assert f.value == 200.0


def test_add_default_matches_spec_default():
    f = UniformFilter.Add()
    assert f.value == UniformFilter.Add.SPEC.parameters[0].default


def test_add_filter_offsets_all_pixels():
    f = UniformFilter.Add(value=10.0)
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    out = f.filter(data)
    assert out.shape == data.shape
    np.testing.assert_array_equal(out, data + 10.0)


# ---------------------------------------------------------------------------
# ScalarMultiply (Scale).SPEC integrity
# ---------------------------------------------------------------------------


def test_scalar_multiply_spec_shape():
    spec = UniformFilter.ScalarMultiply.SPEC
    assert spec.type_id == "scalar_multiply"
    assert spec.display_name == "Scale"
    assert spec.filter_class is UniformFilter.ScalarMultiply
    assert len(spec.parameters) == 1


def test_scalar_multiply_spec_factor_parameter():
    p = UniformFilter.ScalarMultiply.SPEC.parameters[0]
    assert p.name == "factor"
    assert p.label == "Factor"
    assert p.type is ParameterType.FLOAT
    assert p.min_value == 0.0
    assert p.max_value == 10.0
    assert p.default == 1.0


def test_scalar_multiply_factor_is_public_attribute():
    f = UniformFilter.ScalarMultiply(factor=2.0)
    assert f.factor == 2.0
    f.factor = 3.0
    assert f.factor == 3.0


def test_scalar_multiply_default_matches_spec_default():
    f = UniformFilter.ScalarMultiply()
    assert f.factor == UniformFilter.ScalarMultiply.SPEC.parameters[0].default


def test_scalar_multiply_filter_scales_pixels():
    f = UniformFilter.ScalarMultiply(factor=2.0)
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    out = f.filter(data)
    assert out.shape == data.shape
    np.testing.assert_array_equal(out, data * 2.0)


def test_scalar_multiply_does_not_mutate_input():
    f = UniformFilter.ScalarMultiply(factor=5.0)
    data = np.array([[1.0, 2.0]])
    original = data.copy()
    f.filter(data)
    np.testing.assert_array_equal(data, original)


# ---------------------------------------------------------------------------
# SubstituteInRange (Replace In Range).SPEC integrity
# ---------------------------------------------------------------------------


def test_substitute_in_range_spec_shape():
    spec = UniformFilter.SubstituteInRange.SPEC
    assert spec.type_id == "substitute_in_range"
    assert spec.display_name == "Replace In Range"
    assert spec.filter_class is UniformFilter.SubstituteInRange
    assert len(spec.parameters) == 3


def test_substitute_in_range_spec_parameters():
    params = {p.name: p for p in UniformFilter.SubstituteInRange.SPEC.parameters}
    assert params["start"].label == "Start"
    assert params["start"].units == "ADU"
    assert params["start"].default == 0.0
    assert params["end"].label == "End"
    assert params["end"].default == 1000.0
    assert params["value"].label == "Value"
    assert params["value"].default == 0.0
    for p in params.values():
        assert p.type is ParameterType.FLOAT
        assert p.min_value is None
        assert p.max_value is None


def test_substitute_in_range_attributes_are_public():
    f = UniformFilter.SubstituteInRange(start=100.0, end=500.0, value=0.0)
    assert f.start == 100.0
    assert f.end == 500.0
    assert f.value == 0.0
    f.start = 200.0
    assert f.start == 200.0


def test_substitute_in_range_defaults_match_spec():
    f = UniformFilter.SubstituteInRange()
    params = {p.name: p for p in UniformFilter.SubstituteInRange.SPEC.parameters}
    assert f.start == params["start"].default
    assert f.end == params["end"].default
    assert f.value == params["value"].default


def test_substitute_in_range_replaces_pixels_in_range():
    f = UniformFilter.SubstituteInRange(start=2.0, end=4.0, value=99.0)
    data = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]])
    out = f.filter(data)
    np.testing.assert_array_equal(out, [[1.0, 99.0, 99.0, 99.0, 5.0]])


def test_substitute_in_range_does_not_mutate_input():
    f = UniformFilter.SubstituteInRange(start=0.0, end=10.0, value=0.0)
    data = np.array([[5.0, 6.0]])
    original = data.copy()
    f.filter(data)
    np.testing.assert_array_equal(data, original)


# ---------------------------------------------------------------------------
# SubstituteOutOfRange (Clip to Range).SPEC integrity
# ---------------------------------------------------------------------------


def test_substitute_out_of_range_spec_shape():
    spec = UniformFilter.SubstituteOutOfRange.SPEC
    assert spec.type_id == "substitute_out_of_range"
    assert spec.display_name == "Clip to Range"
    assert spec.filter_class is UniformFilter.SubstituteOutOfRange
    assert len(spec.parameters) == 3


def test_substitute_out_of_range_spec_parameters():
    params = {p.name: p for p in UniformFilter.SubstituteOutOfRange.SPEC.parameters}
    assert params["start"].label == "Start"
    assert params["start"].default == 0.0
    assert params["end"].label == "End"
    assert params["end"].default == 65535.0
    assert params["value"].label == "Value"
    assert params["value"].default == 0.0
    for p in params.values():
        assert p.type is ParameterType.FLOAT
        assert p.min_value is None
        assert p.max_value is None
        assert p.units == "ADU"


def test_substitute_out_of_range_attributes_are_public():
    f = UniformFilter.SubstituteOutOfRange(start=100.0, end=50000.0, value=0.0)
    assert f.start == 100.0
    assert f.end == 50000.0
    assert f.value == 0.0
    f.end = 40000.0
    assert f.end == 40000.0


def test_substitute_out_of_range_defaults_match_spec():
    f = UniformFilter.SubstituteOutOfRange()
    params = {p.name: p for p in UniformFilter.SubstituteOutOfRange.SPEC.parameters}
    assert f.start == params["start"].default
    assert f.end == params["end"].default
    assert f.value == params["value"].default


def test_substitute_out_of_range_replaces_pixels_outside_range():
    f = UniformFilter.SubstituteOutOfRange(start=2.0, end=4.0, value=99.0)
    data = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]])
    out = f.filter(data)
    np.testing.assert_array_equal(out, [[99.0, 2.0, 3.0, 4.0, 99.0]])


def test_substitute_out_of_range_does_not_mutate_input():
    f = UniformFilter.SubstituteOutOfRange(start=0.0, end=10.0, value=0.0)
    data = np.array([[5.0, 15.0]])
    original = data.copy()
    f.filter(data)
    np.testing.assert_array_equal(data, original)
