# Citation for Unit Tests: HistoricalFilterBarViewModel
# Date: 02/03/2026
# Adapted from Claude Code:
# Write pure Python unit tests for HistoricalFilterBarViewModel covering
# initialization, setters, build_filter() keV/ADU conversion, apply/reset
# callbacks, and classification_options.

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.frontend.viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
    _PRESET_TO_HOURS,
)


def _make_physics_mock(factor: float = 1.02857e-5):
    mock = MagicMock()
    mock.kev_conversion_factor = factor
    return mock


@pytest.fixture
def config():
    return MockConfigurationService()


@pytest.fixture
def physics():
    return _make_physics_mock()


@pytest.fixture
def vm(config, physics):
    return HistoricalFilterBarViewModel(config, physics)


# --- Initialization ---


class TestInitialization:
    def test_default_time_preset_24h(self, config, physics):
        """Default query hours 24 maps to '24h' preset."""
        config.set("gui:historical:default_query_hours", 24)
        vm = HistoricalFilterBarViewModel(config, physics)
        assert vm.time_preset == "24h"

    def test_default_time_preset_3d(self, config, physics):
        """Default query hours 72 maps to '3d' preset."""
        config.set("gui:historical:default_query_hours", 72)
        vm = HistoricalFilterBarViewModel(config, physics)
        assert vm.time_preset == "3d"

    def test_default_time_preset_7d(self, config, physics):
        """Default query hours 168 maps to '7d' preset."""
        config.set("gui:historical:default_query_hours", 168)
        vm = HistoricalFilterBarViewModel(config, physics)
        assert vm.time_preset == "7d"

    def test_default_time_preset_30d(self, config, physics):
        """Default query hours 720 maps to '30d' preset."""
        config.set("gui:historical:default_query_hours", 720)
        vm = HistoricalFilterBarViewModel(config, physics)
        assert vm.time_preset == "30d"

    def test_default_time_preset_unknown_hours(self, config, physics):
        """Unknown default_query_hours falls back to '24h'."""
        config.set("gui:historical:default_query_hours", 999)
        vm = HistoricalFilterBarViewModel(config, physics)
        assert vm.time_preset == "24h"

    def test_energy_unit_label_kev(self, vm):
        """Energy unit label defaults to 'keV'."""
        assert vm.energy_unit_label == "keV"

    def test_energy_unit_label_adu(self, config, physics):
        """Energy unit label is 'ADU' when keV display is off."""
        config.set("gui:raw_analysis:display_energy_in_kev", False)
        vm = HistoricalFilterBarViewModel(config, physics)
        assert vm.energy_unit_label == "ADU"

    def test_all_fields_none(self, vm):
        """All filter fields start as None."""
        assert vm.cluster_id is None
        assert vm.fits_id is None
        assert vm.hdu_id is None
        assert vm.min_sigma_x is None
        assert vm.min_sigma_y is None
        assert vm.min_total_energy is None
        assert vm.min_total_pixels is None
        assert vm.classification is None


# --- Setters ---


class TestSetters:
    def test_cluster_id(self, vm):
        vm.cluster_id = 42
        assert vm.cluster_id == 42

    def test_fits_id(self, vm):
        vm.fits_id = 7
        assert vm.fits_id == 7

    def test_hdu_id(self, vm):
        vm.hdu_id = 3
        assert vm.hdu_id == 3

    def test_min_sigma_x(self, vm):
        vm.min_sigma_x = 1.5
        assert vm.min_sigma_x == 1.5

    def test_min_sigma_y(self, vm):
        vm.min_sigma_y = 2.0
        assert vm.min_sigma_y == 2.0

    def test_min_total_energy(self, vm):
        vm.min_total_energy = 0.05
        assert vm.min_total_energy == 0.05

    def test_min_total_pixels(self, vm):
        vm.min_total_pixels = 10
        assert vm.min_total_pixels == 10

    def test_classification(self, vm):
        vm.classification = "tritium"
        assert vm.classification == "tritium"

    def test_time_preset(self, vm):
        vm.time_preset = "7d"
        assert vm.time_preset == "7d"


# --- build_filter() ---


class TestBuildFilter:
    def test_empty_filter(self, vm):
        """No fields set produces a default filter."""
        f = vm.build_filter()
        assert f == ClusterQueryFilter()

    def test_energy_kev_to_adu_conversion(self, config, physics):
        """Energy in keV is converted to ADU via physics factor."""
        config.set("gui:raw_analysis:display_energy_in_kev", True)
        vm = HistoricalFilterBarViewModel(config, physics)
        vm.min_total_energy = 0.5  # 0.5 keV
        f = vm.build_filter()
        expected_adu = 0.5 / physics.kev_conversion_factor
        assert f.min_total_energy == pytest.approx(expected_adu)

    def test_energy_adu_passthrough(self, config, physics):
        """When display is ADU, energy passes through unchanged."""
        config.set("gui:raw_analysis:display_energy_in_kev", False)
        vm = HistoricalFilterBarViewModel(config, physics)
        vm.min_total_energy = 50000.0
        f = vm.build_filter()
        assert f.min_total_energy == 50000.0

    def test_all_fields_populated(self, vm):
        """All fields are forwarded to ClusterQueryFilter."""
        vm.cluster_id = 1
        vm.fits_id = 2
        vm.hdu_id = 3
        vm.min_sigma_x = 0.5
        vm.min_sigma_y = 0.6
        vm.min_total_energy = 0.1
        vm.min_total_pixels = 5
        vm.classification = "tritium"
        f = vm.build_filter()
        assert f.cluster_id == 1
        assert f.fits_id == 2
        assert f.hdu_id == 3
        assert f.min_sigma_x == 0.5
        assert f.min_sigma_y == 0.6
        assert f.min_total_pixels == 5
        assert f.classification == "tritium"

    def test_none_fields_stay_none(self, vm):
        """Only populated fields appear in the filter."""
        vm.cluster_id = 5
        f = vm.build_filter()
        assert f.cluster_id == 5
        assert f.fits_id is None
        assert f.min_total_energy is None

    def test_zero_kev_conversion_factor(self, config):
        """Zero conversion factor produces None energy."""
        config.set("gui:raw_analysis:display_energy_in_kev", True)
        physics = _make_physics_mock(factor=0.0)
        vm = HistoricalFilterBarViewModel(config, physics)
        vm.min_total_energy = 0.5
        f = vm.build_filter()
        assert f.min_total_energy is None


# --- apply() ---


class TestApply:
    def test_fires_callback_with_filter(self, vm):
        """apply() fires callback with the built filter."""
        received = []
        vm.add_filter_applied_callback(received.append)
        vm.min_total_pixels = 10
        vm.apply()
        assert len(received) == 1
        assert received[0].min_total_pixels == 10

    def test_multiple_callbacks(self, vm):
        """apply() fires all registered callbacks."""
        cb1 = MagicMock()
        cb2 = MagicMock()
        vm.add_filter_applied_callback(cb1)
        vm.add_filter_applied_callback(cb2)
        vm.apply()
        cb1.assert_called_once()
        cb2.assert_called_once()


# --- reset() ---


class TestReset:
    def test_clears_all_fields(self, vm):
        """reset() sets all fields back to None."""
        vm.cluster_id = 1
        vm.fits_id = 2
        vm.hdu_id = 3
        vm.min_sigma_x = 1.0
        vm.min_sigma_y = 2.0
        vm.min_total_energy = 3.0
        vm.min_total_pixels = 4
        vm.classification = "tritium"
        vm.time_preset = "30d"
        vm.start_datetime = datetime(2025, 1, 1)
        vm.end_datetime = datetime(2025, 6, 1)

        vm.reset()

        assert vm.cluster_id is None
        assert vm.fits_id is None
        assert vm.hdu_id is None
        assert vm.min_sigma_x is None
        assert vm.min_sigma_y is None
        assert vm.min_total_energy is None
        assert vm.min_total_pixels is None
        assert vm.classification is None
        assert vm.start_datetime is None
        assert vm.end_datetime is None

    def test_restores_default_time_preset(self, config, physics):
        """reset() restores the default time preset from config."""
        config.set("gui:historical:default_query_hours", 168)
        vm = HistoricalFilterBarViewModel(config, physics)
        vm.time_preset = "30d"
        vm.reset()
        assert vm.time_preset == "7d"

    def test_fires_reset_callback(self, vm):
        """reset() fires registered callbacks."""
        cb = MagicMock()
        vm.add_filter_reset_callback(cb)
        vm.reset()
        cb.assert_called_once()


# --- classification_options ---


class TestClassificationOptions:
    def test_starts_with_all(self, vm):
        """First option is ('All', None)."""
        options = vm.classification_options
        assert options[0] == ("All", None)

    def test_contains_particle_types(self, vm):
        """Options include all ParticleType members."""
        options = vm.classification_options
        values = [v for _, v in options]
        for pt in ParticleType:
            assert pt.name.lower() in values

    def test_tritium_label_includes_symbol(self, vm):
        """Tritium option uses display name and symbol."""
        options = vm.classification_options
        tritium_opts = [
            (label, val) for label, val in options
            if val == "tritium"
        ]
        assert len(tritium_opts) == 1
        label = tritium_opts[0][0]
        assert "\u00b3H" in label
        assert "Tritium" in label

    def test_unclassified_label(self, vm):
        """Unclassified option shows display name only."""
        options = vm.classification_options
        unclass = [
            (label, val) for label, val in options
            if val == "unclassified"
        ]
        assert len(unclass) == 1
        assert unclass[0][0] == "Unknown"

    def test_option_count(self, vm):
        """Total options = 1 (All) + len(ParticleType)."""
        options = vm.classification_options
        assert len(options) == 1 + len(ParticleType)


# --- datetime properties ---


class TestDateTimeProperties:
    def test_start_datetime_default_none(self, vm):
        """start_datetime defaults to None."""
        assert vm.start_datetime is None

    def test_end_datetime_default_none(self, vm):
        """end_datetime defaults to None."""
        assert vm.end_datetime is None

    def test_start_datetime_setter(self, vm):
        dt = datetime(2025, 6, 15, 12, 0)
        vm.start_datetime = dt
        assert vm.start_datetime == dt

    def test_end_datetime_setter(self, vm):
        dt = datetime(2025, 6, 15, 18, 30)
        vm.end_datetime = dt
        assert vm.end_datetime == dt

    def test_clear_to_none(self, vm):
        """Setting back to None clears the value."""
        vm.start_datetime = datetime(2025, 1, 1)
        vm.start_datetime = None
        assert vm.start_datetime is None


# --- compute_dates_for_preset() ---


class TestComputeDatesForPreset:
    @pytest.mark.parametrize("preset,hours", list(_PRESET_TO_HOURS.items()))
    def test_known_presets(self, preset, hours):
        """Each known preset produces the correct interval."""
        start, end = HistoricalFilterBarViewModel.compute_dates_for_preset(
            preset
        )
        delta = end - start
        assert delta == timedelta(hours=hours)

    def test_unknown_preset_falls_back_to_24h(self):
        """Unknown key defaults to 24 hours."""
        start, end = HistoricalFilterBarViewModel.compute_dates_for_preset(
            "unknown"
        )
        delta = end - start
        assert delta == timedelta(hours=24)

    def test_end_close_to_now(self):
        """The end datetime should be very close to now."""
        _, end = HistoricalFilterBarViewModel.compute_dates_for_preset(
            "24h"
        )
        assert abs((datetime.now() - end).total_seconds()) < 2
