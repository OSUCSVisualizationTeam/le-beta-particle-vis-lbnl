import pytest
from unittest.mock import MagicMock
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
    HistoricalMode,
)
from le_beta_vis.common.ConfigurationService import MockConfigurationService


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    # Reset config to known state
    config.set("gui:historical:mode", HistoricalMode.HISTORICAL)
    return HistoricalViewModel(config)


def test_initial_state(view_model):
    """Test that the ViewModel initializes with the default mode from config."""
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
    """Test that the ViewModel reads from the configuration service correctly."""
    config = MockConfigurationService()
    config.set("gui:historical:mode", HistoricalMode.LIVE)

    vm = HistoricalViewModel(config)
    assert vm.mode == HistoricalMode.LIVE
