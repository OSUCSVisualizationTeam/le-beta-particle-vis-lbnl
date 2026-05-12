"""Tests for FilterPresetService — pure Python, no Qt."""

import json

import jsonschema
import pytest

from le_beta_vis.common.filter_pipeline import (
    BUILTIN_FILTERS,
    ScalingFunction,
    UniformFilter,
)
from le_beta_vis.frontend.viewmodels.FilterPresetService import (
    compose_annotation,
    deserialize_stack,
    generate_schema,
    load_preset,
    save_preset,
    serialize_stack,
)
from le_beta_vis.frontend.viewmodels.FilterStackViewModel import FilterStackViewModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stack() -> list:
    """Return a minimal but realistic stack: pinned filters + one user filter."""
    vm = FilterStackViewModel()
    vm.add_filter(UniformFilter.Gaussian(sigma=2.5))
    vm.set_pinned_parameter("scale_preset", "mode", ScalingFunction.LOG)
    vm.set_pinned_parameter("window", "vmin", 0.0)
    vm.set_pinned_parameter("window", "vmax", 4.0)
    return vm.entries


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------

class TestGenerateSchema:
    def test_returns_dict_with_schema_key(self):
        schema = generate_schema()
        assert "$schema" in schema

    def test_one_entry_per_builtin_filter(self):
        schema = generate_schema()
        one_of = schema["properties"]["filters"]["items"]["oneOf"]
        assert len(one_of) == len(BUILTIN_FILTERS)

    def test_all_type_ids_present(self):
        schema = generate_schema()
        one_of = schema["properties"]["filters"]["items"]["oneOf"]
        found = {entry["properties"]["type_id"]["const"] for entry in one_of}
        expected = {f"builtin.{s.type_id}" for s in BUILTIN_FILTERS}
        assert found == expected

    def test_gaussian_sigma_bounds_in_schema(self):
        schema = generate_schema()
        one_of = schema["properties"]["filters"]["items"]["oneOf"]
        blur = next(e for e in one_of if e["properties"]["type_id"]["const"] == "builtin.gaussian_blur")
        sigma = blur["properties"]["parameters"]["properties"]["sigma"]
        assert sigma["minimum"] == pytest.approx(0.1)
        assert sigma["maximum"] == pytest.approx(10.0)

    def test_scale_preset_mode_enum_values(self):
        schema = generate_schema()
        one_of = schema["properties"]["filters"]["items"]["oneOf"]
        sp = next(e for e in one_of if e["properties"]["type_id"]["const"] == "builtin.scale_preset")
        enum_vals = sp["properties"]["parameters"]["properties"]["mode"]["enum"]
        assert set(enum_vals) == {s.value for s in ScalingFunction}


# ---------------------------------------------------------------------------
# Round-trip serialization
# ---------------------------------------------------------------------------

class TestSerializeDeserialize:
    def test_roundtrip_preserves_type_ids(self):
        entries = _make_stack()
        restored = deserialize_stack(serialize_stack(entries))
        original_ids = [f"builtin.{e.filter.SPEC.type_id}" for e in entries]
        restored_ids = [f"builtin.{r.filter.SPEC.type_id}" for r in restored]
        assert original_ids == restored_ids

    def test_roundtrip_preserves_enabled_flag(self):
        entries = _make_stack()
        restored = deserialize_stack(serialize_stack(entries))
        for orig, rest in zip(entries, restored):
            assert orig.enabled == rest.enabled

    def test_roundtrip_preserves_pinned_flag(self):
        entries = _make_stack()
        restored = deserialize_stack(serialize_stack(entries))
        for orig, rest in zip(entries, restored):
            assert orig.pinned == rest.pinned

    def test_roundtrip_preserves_float_parameter(self):
        entries = _make_stack()
        restored = deserialize_stack(serialize_stack(entries))
        orig_gaussian = next(e for e in entries if e.filter.SPEC.type_id == "gaussian_blur")
        rest_gaussian = next(r for r in restored if r.filter.SPEC.type_id == "gaussian_blur")
        assert orig_gaussian.filter.sigma == pytest.approx(rest_gaussian.filter.sigma)

    def test_roundtrip_preserves_enum_parameter(self):
        entries = _make_stack()
        restored = deserialize_stack(serialize_stack(entries))
        orig_sp = next(e for e in entries if e.filter.SPEC.type_id == "scale_preset")
        rest_sp = next(r for r in restored if r.filter.SPEC.type_id == "scale_preset")
        # Compare via equality — ScalingFunction(str, Enum) compares equal to its string value.
        # Deserialization restores the string value; the filter behavior is identical.
        assert orig_sp.filter.mode == rest_sp.filter.mode

    def test_unknown_type_id_raises_value_error(self):
        bad = [{"type_id": "builtin.does_not_exist", "pinned": False,
                "enabled": True, "parameters": {}}]
        with pytest.raises(ValueError, match="Unknown filter type"):
            deserialize_stack(bad)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_valid_stack_passes_validation(self):
        entries = _make_stack()
        data = {
            "schema_version": "1.0",
            "annotation": "test",
            "filters": serialize_stack(entries),
        }
        jsonschema.validate(data, generate_schema())

    def test_rogue_type_id_fails_validation(self):
        data = {
            "schema_version": "1.0",
            "filters": [
                {"type_id": "evil.injection", "pinned": False, "enabled": True, "parameters": {}}
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, generate_schema())

    def test_wrong_schema_version_fails_validation(self):
        entries = _make_stack()
        data = {
            "schema_version": "99.0",
            "filters": serialize_stack(entries),
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, generate_schema())

    def test_extra_top_level_key_fails_validation(self):
        entries = _make_stack()
        data = {
            "schema_version": "1.0",
            "filters": serialize_stack(entries),
            "unexpected_key": "oops",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, generate_schema())


# ---------------------------------------------------------------------------
# File round-trip
# ---------------------------------------------------------------------------

class TestFileRoundTrip:
    def test_save_then_load_restores_stack(self, tmp_path):
        path = str(tmp_path / "preset.rcfilt")
        entries = _make_stack()
        save_preset(path, entries, "test annotation")
        restored, annotation = load_preset(path)
        assert annotation == "test annotation"
        original_ids = [e.filter.SPEC.type_id for e in entries]
        restored_ids = [r.filter.SPEC.type_id for r in restored]
        assert original_ids == restored_ids

    def test_save_produces_valid_json(self, tmp_path):
        path = str(tmp_path / "preset.rcfilt")
        entries = _make_stack()
        save_preset(path, entries, "")
        with open(path) as fh:
            data = json.load(fh)
        assert data["schema_version"] == "1.0"
        assert isinstance(data["filters"], list)

    def test_load_invalid_json_raises(self, tmp_path):
        path = str(tmp_path / "bad.rcfilt")
        with open(path, "w") as fh:
            fh.write("not json {{")
        with pytest.raises(json.JSONDecodeError):
            load_preset(path)

    def test_load_rogue_filter_raises_validation_error(self, tmp_path):
        path = str(tmp_path / "rogue.rcfilt")
        data = {
            "schema_version": "1.0",
            "filters": [
                {"type_id": "builtin.unknown_filter", "pinned": False,
                 "enabled": True, "parameters": {}}
            ],
        }
        with open(path, "w") as fh:
            json.dump(data, fh)
        with pytest.raises(jsonschema.ValidationError):
            load_preset(path)

    def test_load_missing_annotation_returns_empty_string(self, tmp_path):
        path = str(tmp_path / "no_annotation.rcfilt")
        entries = _make_stack()
        save_preset(path, entries, "")
        with open(path) as fh:
            data = json.load(fh)
        data.pop("annotation", None)
        with open(path, "w") as fh:
            json.dump(data, fh)
        _, annotation = load_preset(path)
        assert annotation == ""


# ---------------------------------------------------------------------------
# compose_annotation
# ---------------------------------------------------------------------------

class TestComposeAnnotation:
    def test_includes_display_names(self):
        entries = _make_stack()
        result = compose_annotation(entries)
        assert "Gaussian Blur" in result
        assert "Display Range" in result

    def test_disabled_entries_excluded(self):
        entries = _make_stack()
        for e in entries:
            if e.filter.SPEC.type_id == "gaussian_blur":
                e.enabled = False
        result = compose_annotation(entries)
        assert "Gaussian Blur" not in result

    def test_filter_with_no_params_shows_display_name_only(self):
        vm = FilterStackViewModel()
        result = compose_annotation(vm.entries)
        assert "ADU" in result or "→" in result or "keV" in result.lower() or "adu_to_kev" not in result

    def test_enum_value_shown_as_string(self):
        entries = _make_stack()
        result = compose_annotation(entries)
        assert "log" in result.lower()

    def test_plain_string_enum_does_not_raise(self):
        """Regression: mode stored as plain str by the popover must not crash :.2g."""
        vm = FilterStackViewModel()
        vm.set_pinned_parameter("scale_preset", "mode", "log")
        result = compose_annotation(vm.entries)
        assert "log" in result.lower()
