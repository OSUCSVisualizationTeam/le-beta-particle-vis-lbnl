"""Tests for SettingsViewModel — pure Python, no QApplication required."""

import pytest

from le_beta_vis.frontend.viewmodels.SettingsViewModel import (
    SettingsViewModel,
    _parse_key,
    _humanize,
)
from le_beta_vis.common.ConfigurationService import ConfigurationService
from typing import Any, Dict, Optional


# ------------------------------------------------------------------
# Minimal mock that satisfies ConfigurationService + get_metadata
# ------------------------------------------------------------------

_TEST_METADATA: Dict[str, Dict[str, Any]] = {
    "gui:raw_analysis:clustering_threshold": {
        "type": "float",
        "default": 4.0,
        "description": "Signal-to-noise ratio for clustering.",
    },
    "gui:raw_analysis:default_colormap": {
        "type": "enum",
        "choices": ["viridis", "plasma", "magma"],
        "default": "viridis",
        "description": "Initial colormap for FITS files.",
    },
    "gui:raw_analysis:show_tool_hints": {
        "type": "bool",
        "default": True,
        "description": "Show inline usage hints on interactive tools.",
    },
    "gui:window:default_width": {
        "type": "int",
        "default": 1024,
        "description": "Default initial width of the application window.",
    },
    "eps:timeout_ms": {
        "type": "int",
        "default": 5000,
        "description": "Timeout in milliseconds for ZMQ operations.",
    },
    "global:db:connection_string": {
        "type": "str",
        "default": "mysql://localhost/le_beta_vis",
        "description": "Database connection URI.",
    },
}


class _TestConfigService(ConfigurationService):
    """Minimal config service for SettingsViewModel testing."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {
            k: v["default"] for k, v in _TEST_METADATA.items()
        }
        self._defaults = dict(self._store)
        self.set_calls: list = []

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self.set_calls.append((key, value))

    def get_description(self, key: str) -> Optional[str]:
        meta = _TEST_METADATA.get(key)
        return meta["description"] if meta else None

    def reset_to_defaults(self) -> None:
        self._store = dict(self._defaults)

    def get_metadata(self) -> Dict[str, Dict[str, Any]]:
        return dict(_TEST_METADATA)


@pytest.fixture
def config():
    return _TestConfigService()


@pytest.fixture
def vm(config):
    return SettingsViewModel(config)


# ------------------------------------------------------------------
# TestInitialization
# ------------------------------------------------------------------

class TestInitialization:
    def test_metadata_loaded(self, vm):
        assert len(vm.all_keys) == len(_TEST_METADATA)

    def test_current_values_populated(self, vm):
        assert vm.get_current_value(
            "gui:raw_analysis:clustering_threshold"
        ) == 4.0

    def test_no_pending_changes(self, vm):
        assert vm.has_pending_changes is False


# ------------------------------------------------------------------
# TestNamespaceParsing
# ------------------------------------------------------------------

class TestNamespaceParsing:
    def test_three_part_key(self):
        g, s, l = _parse_key("gui:raw_analysis:clustering_threshold")
        assert g == "GUI"
        assert s == "Raw Analysis"
        assert l == "Clustering Threshold"

    def test_two_part_key(self):
        g, s, l = _parse_key("eps:timeout_ms")
        assert g == "EPS"
        assert s == "General"
        assert l == "Timeout Ms"

    def test_single_part_key(self):
        g, s, l = _parse_key("standalone")
        assert g == "General"
        assert s == "General"
        assert l == "Standalone"

    def test_acronym_override_gui(self):
        assert _humanize("gui") == "GUI"

    def test_acronym_override_eps(self):
        assert _humanize("eps") == "EPS"

    def test_acronym_override_db(self):
        assert _humanize("db") == "Database"

    def test_humanize_snake_case(self):
        assert _humanize("raw_analysis") == "Raw Analysis"


# ------------------------------------------------------------------
# TestGrouping
# ------------------------------------------------------------------

class TestGrouping:
    def test_correct_group_names(self, vm):
        grouped = vm.filtered_grouped_settings()
        assert "GUI" in grouped
        assert "EPS" in grouped
        assert "Global" in grouped

    def test_subgroup_names(self, vm):
        grouped = vm.filtered_grouped_settings()
        assert "Raw Analysis" in grouped["GUI"]
        assert "Window" in grouped["GUI"]
        assert "General" in grouped["EPS"]

    def test_entry_counts(self, vm):
        grouped = vm.filtered_grouped_settings()
        # gui:raw_analysis has 3 keys
        assert len(grouped["GUI"]["Raw Analysis"]) == 3
        # gui:window has 1 key
        assert len(grouped["GUI"]["Window"]) == 1
        # eps has 1 key
        assert len(grouped["EPS"]["General"]) == 1

    def test_enum_choices_passed(self, vm):
        grouped = vm.filtered_grouped_settings()
        entries = grouped["GUI"]["Raw Analysis"]
        
        # Find the colormap entry
        colormap_entry = next(e for e in entries if e[0] == "gui:raw_analysis:default_colormap")
        
        # entry tuple: (key, leaf, type_str, current, default, desc, choices)
        choices = colormap_entry[6]
        assert choices == ["viridis", "plasma", "magma"]


# ------------------------------------------------------------------
# TestPendingChanges
# ------------------------------------------------------------------

class TestPendingChanges:
    def test_set_pending_records_change(self, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        assert vm.has_pending_changes is True

    def test_get_current_value_prefers_pending(self, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        assert vm.get_current_value("eps:timeout_ms") == 9999

    def test_get_current_value_returns_live_without_pending(self, vm):
        assert vm.get_current_value("eps:timeout_ms") == 5000


# ------------------------------------------------------------------
# TestFilter
# ------------------------------------------------------------------

class TestFilter:
    def test_empty_filter_returns_all(self, vm):
        vm.filter("")
        grouped = vm.filtered_grouped_settings()
        total = sum(
            len(entries)
            for subs in grouped.values()
            for entries in subs.values()
        )
        assert total == len(_TEST_METADATA)

    def test_match_by_key(self, vm):
        vm.filter("timeout")
        grouped = vm.filtered_grouped_settings()
        total = sum(
            len(entries)
            for subs in grouped.values()
            for entries in subs.values()
        )
        assert total == 1

    def test_match_by_description(self, vm):
        vm.filter("colormap")
        grouped = vm.filtered_grouped_settings()
        total = sum(
            len(entries)
            for subs in grouped.values()
            for entries in subs.values()
        )
        assert total == 1

    def test_case_insensitive(self, vm):
        vm.filter("TIMEOUT")
        grouped = vm.filtered_grouped_settings()
        total = sum(
            len(entries)
            for subs in grouped.values()
            for entries in subs.values()
        )
        assert total == 1

    def test_empty_groups_pruned(self, vm):
        vm.filter("timeout")
        grouped = vm.filtered_grouped_settings()
        assert "GUI" not in grouped
        assert "EPS" in grouped


# ------------------------------------------------------------------
# TestApply
# ------------------------------------------------------------------

class TestApply:
    def test_writes_to_config_service(self, config, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        vm.apply()
        assert config.get("eps:timeout_ms") == 9999

    def test_clears_pending(self, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        vm.apply()
        assert vm.has_pending_changes is False

    def test_refreshes_values(self, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        vm.apply()
        assert vm.get_current_value("eps:timeout_ms") == 9999


# ------------------------------------------------------------------
# TestCancel
# ------------------------------------------------------------------

class TestCancel:
    def test_discards_pending(self, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        vm.cancel()
        assert vm.has_pending_changes is False

    def test_no_writes(self, config, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        vm.cancel()
        assert config.get("eps:timeout_ms") == 5000
        assert len(config.set_calls) == 0


# ------------------------------------------------------------------
# TestRestoreDefaults
# ------------------------------------------------------------------

class TestRestoreDefaults:
    def test_calls_reset_to_defaults(self, config, vm):
        config.set("eps:timeout_ms", 9999)
        vm.restore_defaults()
        assert vm.get_current_value("eps:timeout_ms") == 5000

    def test_clears_pending(self, vm):
        vm.set_pending("eps:timeout_ms", 9999)
        vm.restore_defaults()
        assert vm.has_pending_changes is False


# ------------------------------------------------------------------
# TestCallbacks
# ------------------------------------------------------------------

class TestCallbacks:
    def test_values_changed_fires_on_apply(self, vm):
        calls = []
        vm.add_values_changed_callback(lambda: calls.append("v"))
        vm.set_pending("eps:timeout_ms", 9999)
        vm.apply()
        assert calls == ["v"]

    def test_values_changed_fires_on_restore(self, vm):
        calls = []
        vm.add_values_changed_callback(lambda: calls.append("v"))
        vm.restore_defaults()
        assert calls == ["v"]

    def test_pending_changed_fires_on_set_pending(self, vm):
        calls = []
        vm.add_pending_changed_callback(lambda: calls.append("p"))
        vm.set_pending("eps:timeout_ms", 9999)
        assert calls == ["p"]

    def test_pending_changed_fires_on_filter(self, vm):
        calls = []
        vm.add_pending_changed_callback(lambda: calls.append("p"))
        vm.filter("timeout")
        assert calls == ["p"]
