"""Tests for YAMLBackedConfigurationService.

All tests use pytest's ``tmp_path`` fixture — no QApplication required.
"""

import enum
import threading

import yaml
import pytest

from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_service(tmp_path, initial=None):
    """Create a service pointing at a temp YAML file."""
    path = tmp_path / "test_config.yaml"
    if initial is not None:
        with open(path, "w") as fh:
            yaml.safe_dump(initial, fh)
    return YAMLBackedConfigurationService(yaml_path=path), path


def _read_yaml(path):
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


# ------------------------------------------------------------------
# Basic get / set
# ------------------------------------------------------------------

class TestGetSetRoundtrip:
    def test_set_then_get_returns_value(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        svc.set("foo", 42)
        assert svc.get("foo") == 42

    def test_persistence_across_instances(self, tmp_path):
        svc1, path = _make_service(tmp_path, initial={})
        svc1.set("key", "hello")

        svc2 = YAMLBackedConfigurationService(yaml_path=path)
        assert svc2.get("key") == "hello"


# ------------------------------------------------------------------
# Missing key behaviour
# ------------------------------------------------------------------

class TestMissingKeys:
    def test_missing_key_no_default_returns_none(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        assert svc.get("nonexistent") is None

    def test_missing_key_with_default_returns_default(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        assert svc.get("new_key", 99) == 99

    def test_missing_key_with_default_persists_to_disk(self, tmp_path):
        svc, path = _make_service(tmp_path, initial={})
        svc.get("auto_key", 3.14)
        data = _read_yaml(path)
        assert data["auto_key"] == pytest.approx(3.14)


# ------------------------------------------------------------------
# Type coercion
# ------------------------------------------------------------------

class TestTypeCoercion:
    def test_bool_coercion_from_string(self, tmp_path):
        """Simulates a user hand-editing YAML: writing "true" as a
        quoted string instead of bare ``true``."""
        svc, _ = _make_service(tmp_path, initial={})
        # First call registers bool via default
        svc.get("flag", True)
        # Overwrite on disk with a string
        svc.set("flag", "false")
        assert svc.get("flag") is False

    def test_int_coercion_from_string(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        svc.get("port", 6379)
        svc.set("port", "8080")
        assert svc.get("port") == 8080

    def test_float_coercion_from_string(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        svc.get("sigma", 1.5)
        svc.set("sigma", "2.7")
        assert svc.get("sigma") == pytest.approx(2.7)

    def test_str_returned_as_is(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={"name": "viridis"})
        assert svc.get("name") == "viridis"

    def test_yaml_native_types_without_registry(self, tmp_path):
        """Values loaded from YAML that have no registry entry
        should pass through unchanged."""
        svc, _ = _make_service(
            tmp_path, initial={"count": 10, "ratio": 0.5}
        )
        assert svc.get("count") == 10
        assert isinstance(svc.get("count"), int)
        assert svc.get("ratio") == pytest.approx(0.5)


# ------------------------------------------------------------------
# Lazy type registration
# ------------------------------------------------------------------

class TestLazyTypeRegistration:
    def test_default_registers_type(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        svc.get("my_int", 42)
        # The type should now be registered
        assert svc._type_registry["my_int"] == "int"

    def test_set_registers_type_if_absent(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        svc.set("new_float", 3.14)
        assert svc._type_registry["new_float"] == "float"


# ------------------------------------------------------------------
# Enum-subclass default
# ------------------------------------------------------------------

class TestEnumDefault:
    def test_str_enum_infers_as_str(self, tmp_path):
        class Color(str, enum.Enum):
            RED = "red"
            BLUE = "blue"

        svc, _ = _make_service(tmp_path, initial={})
        svc.get("color", Color.RED)
        assert svc._type_registry["color"] == "str"


# ------------------------------------------------------------------
# Bundled defaults bootstrap
# ------------------------------------------------------------------

class TestBundledDefaults:
    def test_creates_file_from_bundled_defaults(self, tmp_path):
        path = tmp_path / "fresh_config.yaml"
        assert not path.exists()
        svc = YAMLBackedConfigurationService(yaml_path=path)
        # Trigger lazy load
        val = svc.get("gui:raw_analysis:default_colormap")
        assert path.exists()
        assert val == "viridis"

    def test_bundled_defaults_contain_expected_keys(self, tmp_path):
        path = tmp_path / "fresh.yaml"
        svc = YAMLBackedConfigurationService(yaml_path=path)
        assert svc.get("global:physics:ped_width") == 1400
        assert svc.get("eps:timeout_ms") == 5000


# ------------------------------------------------------------------
# get_metadata()
# ------------------------------------------------------------------

class TestGetDescription:
    def test_known_key_returns_description_string(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        desc = svc.get_description("gui:raw_analysis:vis_range_min")
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_unknown_key_returns_none(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        assert svc.get_description("totally:unknown:key") is None


# ------------------------------------------------------------------
# get_metadata()
# ------------------------------------------------------------------

class TestGetMetadata:
    def test_returns_descriptions(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={})
        meta = svc.get_metadata()
        entry = meta.get("gui:raw_analysis:vis_range_min")
        assert entry is not None
        assert "default" in entry
        assert "description" in entry
        assert entry["type"] == "float"


# ------------------------------------------------------------------
# reset_to_defaults()
# ------------------------------------------------------------------

class TestResetToDefaults:
    def test_reset_restores_all_defaults(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        # Trigger lazy load then override a key
        svc.get("gui:raw_analysis:default_colormap")
        svc.set("gui:raw_analysis:default_colormap", "plasma")
        assert svc.get("gui:raw_analysis:default_colormap") == "plasma"

        svc.reset_to_defaults()
        assert svc.get("gui:raw_analysis:default_colormap") == "viridis"

    def test_reset_persists_to_disk(self, tmp_path):
        svc, path = _make_service(tmp_path)
        svc.get("eps:timeout_ms")
        svc.set("eps:timeout_ms", 9999)
        svc.reset_to_defaults()

        data = _read_yaml(path)
        assert data["eps:timeout_ms"] == 5000


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

def _writer(svc, n, errors):
    try:
        for i in range(50):
            svc.set(f"thread_{n}_{i}", i)
    except Exception as exc:
        errors.append(exc)


def _reader(svc, errors):
    try:
        for _ in range(50):
            svc.get("counter", 0)
    except Exception as exc:
        errors.append(exc)


class TestThreadSafety:
    def test_concurrent_get_set_no_exceptions(self, tmp_path):
        svc, _ = _make_service(tmp_path, initial={"counter": 0})
        errors: list = []

        threads = [
            threading.Thread(target=_writer, args=(svc, t, errors))
            for t in range(4)
        ] + [
            threading.Thread(target=_reader, args=(svc, errors))
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
