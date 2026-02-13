from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    ActiveTool,
    RawDataViewModel,
)


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    vm = RawDataViewModel(config)
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)

    def mock_request():
        vm._render_worker_logic()

    vm._request_render = mock_request
    return vm


def test_initial_active_tool_is_pointer(view_model):
    """Test that the initial active tool is POINTER."""
    assert view_model.activeTool == ActiveTool.POINTER
    assert view_model.isMagnifierActive is False


def test_set_active_tool_magnifier(view_model):
    """Test switching to magnifier tool fires callback."""
    cb = MagicMock()
    view_model.add_active_tool_changed_callback(cb)
    view_model.setActiveTool(ActiveTool.MAGNIFIER)
    assert view_model.activeTool == ActiveTool.MAGNIFIER
    assert view_model.isMagnifierActive is True
    cb.assert_called_once()


def test_set_active_tool_same_tool_no_callback(view_model):
    """Test that setting the same tool does not fire callback."""
    cb = MagicMock()
    view_model.add_active_tool_changed_callback(cb)
    view_model.setActiveTool(ActiveTool.POINTER)
    cb.assert_not_called()


def test_set_active_tool_box_select(view_model):
    """Test switching to box select deactivates magnifier."""
    view_model.setActiveTool(ActiveTool.MAGNIFIER)
    view_model.setActiveTool(ActiveTool.BOX_SELECT)
    assert view_model.activeTool == ActiveTool.BOX_SELECT
    assert view_model.isMagnifierActive is False


def test_toggle_magnifier_on(view_model):
    """Test toggleMagnifier activates from pointer."""
    view_model.toggleMagnifier()
    assert view_model.isMagnifierActive is True


def test_toggle_magnifier_off(view_model):
    """Test toggleMagnifier deactivates back to pointer."""
    view_model.toggleMagnifier()
    view_model.toggleMagnifier()
    assert view_model.activeTool == ActiveTool.POINTER
    assert view_model.isMagnifierActive is False


def test_initial_magnification_factor(view_model):
    """Test that initial magnification factor comes from config default."""
    assert view_model.magnificationFactor == 3.0


def test_adjust_magnification_up(view_model):
    """Test increasing magnification factor."""
    cb = MagicMock()
    view_model.add_magnifier_state_changed_callback(cb)
    view_model.adjustMagnification(1)
    assert view_model.magnificationFactor == 3.5
    cb.assert_called_once()


def test_adjust_magnification_down(view_model):
    """Test decreasing magnification factor."""
    view_model.adjustMagnification(-1)
    assert view_model.magnificationFactor == 2.5


def test_adjust_magnification_clamped_min(view_model):
    """Test magnification factor does not go below minimum."""
    view_model._magnificationFactor = 1.0
    cb = MagicMock()
    view_model.add_magnifier_state_changed_callback(cb)
    view_model.adjustMagnification(-1)
    assert view_model.magnificationFactor == 1.0
    cb.assert_not_called()


def test_adjust_magnification_clamped_max(view_model):
    """Test magnification factor does not exceed maximum."""
    view_model._magnificationFactor = 100.0
    cb = MagicMock()
    view_model.add_magnifier_state_changed_callback(cb)
    view_model.adjustMagnification(1)
    assert view_model.magnificationFactor == 100.0
    cb.assert_not_called()


def test_active_raw_data_no_capture(view_model):
    """Test activeRawData returns None when no capture is loaded."""
    assert view_model.activeRawData is None


def test_active_raw_data_with_capture(view_model):
    """Test activeRawData returns the raw numpy array."""
    mock_capture = MagicMock()
    expected_data = np.zeros((10, 10))
    mock_capture.rawData.return_value = expected_data
    view_model._captures = [mock_capture]
    view_model._activeIndex = 0
    result = view_model.activeRawData
    assert np.array_equal(result, expected_data)


def test_kev_conversion_factor(view_model):
    """Test kevConversionFactor returns the config value."""
    assert view_model.kevConversionFactor == 1.02857e-5


# --- Magnifier Position ---

def test_magnifier_move_step(view_model):
    """Test magnifierMoveStep reads from config."""
    assert view_model.magnifierMoveStep == 1


def test_show_tool_hints(view_model):
    """Test showToolHints reads from config."""
    assert view_model.showToolHints is True


def test_initial_magnifier_position(view_model):
    """Test magnifierPosition starts at (0, 0)."""
    assert view_model.magnifierPosition == (0, 0)


def test_set_magnifier_position(view_model):
    """Test setMagnifierPosition stores and fires callback."""
    view_model._image_bounds = (100, 100)
    cb = MagicMock()
    view_model.add_magnifier_position_changed_callback(cb)
    view_model.setMagnifierPosition(50, 60)
    assert view_model.magnifierPosition == (50, 60)
    cb.assert_called_once()


def test_set_magnifier_position_clamped(view_model):
    """Test setMagnifierPosition clamps to image bounds."""
    view_model._image_bounds = (100, 100)
    view_model.setMagnifierPosition(200, -5)
    assert view_model.magnifierPosition == (99, 0)


def test_set_magnifier_position_no_callback_if_unchanged(
    view_model,
):
    """Test setMagnifierPosition does not fire if pos unchanged."""
    view_model._image_bounds = (100, 100)
    view_model.setMagnifierPosition(10, 20)
    cb = MagicMock()
    view_model.add_magnifier_position_changed_callback(cb)
    view_model.setMagnifierPosition(10, 20)
    cb.assert_not_called()


def test_move_magnifier(view_model):
    """Test moveMagnifier applies step and delegates."""
    view_model._image_bounds = (100, 100)
    view_model.setMagnifierPosition(50, 50)
    view_model.moveMagnifier(-1, 0)
    assert view_model.magnifierPosition == (49, 50)


def test_move_magnifier_clamped_at_zero(view_model):
    """Test moveMagnifier stops at image boundary."""
    view_model._image_bounds = (100, 100)
    view_model.setMagnifierPosition(0, 0)
    view_model.moveMagnifier(-1, -1)
    assert view_model.magnifierPosition == (0, 0)
