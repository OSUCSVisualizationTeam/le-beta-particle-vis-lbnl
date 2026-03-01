# Citation for Unit Tests: HistoricalViewModel default mode, config integration, and properties
# Date: 26/02/2026
# Adapted from Claude Code:
# Write pure Python unit tests for HistoricalViewModel checking initialization,
# state transitions, and configuration properties.

import pytest
from unittest.mock import MagicMock
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
    HistoricalMode,
)
from le_beta_vis.common.ConfigurationService import (
    MockConfigurationService,
)
from le_beta_vis.common.MockEventRepository import (
    MockEventRepository,
)


def _make_physics_mock():
    mock = MagicMock()
    mock.kev_conversion_factor = 1.02857e-5
    return mock


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    # Reset config to known state
    config.set(
        "gui:historical:mode", HistoricalMode.HISTORICAL
    )
    return HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )


def test_initial_state(view_model):
    """Test that ViewModel inits with the default mode."""
    assert view_model.mode == HistoricalMode.HISTORICAL


def test_set_mode_valid(view_model):
    """Test setting a valid mode."""
    # Setup callback mock
    mock_callback = MagicMock()
    view_model.add_mode_changed_callback(mock_callback)

    view_model.setMode(HistoricalMode.LIVE)

    assert view_model.mode == HistoricalMode.LIVE
    mock_callback.assert_called_once_with(HistoricalMode.LIVE)


def test_set_mode_invalid(view_model):
    """Test that setting an invalid mode raises ValueError."""
    with pytest.raises(ValueError):
        view_model.setMode("invalid_mode")


def test_toggle_mode(view_model):
    """Test toggling between modes."""
    assert view_model.mode == HistoricalMode.HISTORICAL

    view_model.toggleMode()
    assert view_model.mode == HistoricalMode.LIVE

    view_model.toggleMode()
    assert view_model.mode == HistoricalMode.HISTORICAL


def test_config_integration():
    """Test that ViewModel reads from config correctly."""
    config = MockConfigurationService()
    config.set("gui:historical:mode", HistoricalMode.LIVE)

    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )
    assert vm.mode == HistoricalMode.LIVE


def test_classification_threshold_default():
    """classificationThreshold should default to 0.75."""
    config = MockConfigurationService()
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )
    assert vm.classificationThreshold == 0.75


def test_classification_threshold_from_config():
    """classificationThreshold should read from config."""
    config = MockConfigurationService()
    config.set("gui:historical:classification_threshold", 0.60)
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )
    assert vm.classificationThreshold == 0.60


def test_display_energy_in_kev_default():
    """displayEnergyInKev should default to True."""
    config = MockConfigurationService()
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )
    assert vm.displayEnergyInKev is True


def test_display_energy_in_kev_false():
    """displayEnergyInKev should return False when config says so."""
    config = MockConfigurationService()
    config.set("gui:raw_analysis:display_energy_in_kev", False)
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )
    assert vm.displayEnergyInKev is False


def test_histogram_renderer_default():
    """histogramRenderer should default to MatplotlibHistogramRenderer."""
    from le_beta_vis.common.HistogramRenderer import (
        MatplotlibHistogramRenderer,
    )
    config = MockConfigurationService()
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository()
    )
    assert isinstance(vm.histogramRenderer, MatplotlibHistogramRenderer)


def test_histogram_renderer_injected():
    """histogramRenderer should use the injected renderer."""
    from MockHistogramRenderer import (
        MockHistogramRenderer,
    )
    config = MockConfigurationService()
    renderer = MockHistogramRenderer()
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository(),
        histogramRenderer=renderer,
    )
    assert vm.histogramRenderer is renderer
