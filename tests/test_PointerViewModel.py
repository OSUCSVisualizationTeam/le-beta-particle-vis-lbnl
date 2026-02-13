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
    vm._converter.convert.return_value = np.zeros(
        (10, 10, 3), dtype=np.uint8
    )

    def mock_request():
        vm._render_worker_logic()

    vm._request_render = mock_request
    return vm


# --- isPointerActive ---


def test_is_pointer_active_initial(view_model):
    """Test that the pointer tool is active by default."""
    assert view_model.isPointerActive is True


def test_is_pointer_active_after_switch(view_model):
    """Test isPointerActive is False when another tool is active."""
    view_model.setActiveTool(ActiveTool.MAGNIFIER)
    assert view_model.isPointerActive is False


def test_is_pointer_active_after_switch_back(view_model):
    """Test isPointerActive returns True after switching back."""
    view_model.setActiveTool(ActiveTool.MAGNIFIER)
    view_model.setActiveTool(ActiveTool.POINTER)
    assert view_model.isPointerActive is True


# --- Pointer Hover Position ---


def test_initial_pointer_hover_is_none(view_model):
    """Test that pointerHoverInfo starts as None."""
    assert view_model.pointerHoverInfo is None


def test_set_pointer_hover_position(view_model):
    """Test setPointerHoverPosition stores and fires callback."""
    view_model._image_bounds = (100, 100)
    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)
    view_model.setPointerHoverPosition(50, 60)
    cb.assert_called_once()


def test_set_pointer_hover_position_clamped(view_model):
    """Test setPointerHoverPosition clamps to image bounds."""
    view_model._image_bounds = (100, 100)
    mock_capture = MagicMock()
    raw = np.ones((100, 100))
    mock_capture.rawData.return_value = raw
    view_model._captures = [mock_capture]
    view_model._activeIndex = 0

    view_model.setPointerHoverPosition(200, -5)
    info = view_model.pointerHoverInfo
    assert info is not None
    row, col, _ = info
    assert row == 99
    assert col == 0


def test_no_callback_if_position_unchanged(view_model):
    """Test that setting the same position doesn't fire callback."""
    view_model._image_bounds = (100, 100)
    view_model.setPointerHoverPosition(10, 20)
    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)
    view_model.setPointerHoverPosition(10, 20)
    cb.assert_not_called()


# --- clearPointerHover ---


def test_clear_pointer_hover(view_model):
    """Test clearPointerHover resets to None and fires callback."""
    view_model._image_bounds = (100, 100)
    view_model.setPointerHoverPosition(10, 20)
    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)
    view_model.clearPointerHover()
    assert view_model.pointerHoverInfo is None
    cb.assert_called_once()


def test_clear_pointer_hover_when_already_none(view_model):
    """Test clearPointerHover does not fire if already None."""
    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)
    view_model.clearPointerHover()
    cb.assert_not_called()


# --- pointerHoverInfo ---


def test_pointer_hover_info_with_capture(view_model):
    """Test pointerHoverInfo returns correct (row, col, keV) tuple."""
    mock_capture = MagicMock()
    raw = np.full((100, 100), 1000.0)
    mock_capture.rawData.return_value = raw
    view_model._captures = [mock_capture]
    view_model._activeIndex = 0
    view_model._image_bounds = (100, 100)

    view_model.setPointerHoverPosition(25, 30)
    info = view_model.pointerHoverInfo

    assert info is not None
    row, col, kev = info
    assert row == 25
    assert col == 30
    expected_kev = 1000.0 * view_model.kevConversionFactor
    assert abs(kev - expected_kev) < 1e-12


def test_pointer_hover_info_no_capture(view_model):
    """Test pointerHoverInfo returns None when no data loaded."""
    view_model._image_bounds = (100, 100)
    view_model.setPointerHoverPosition(10, 20)
    assert view_model.pointerHoverInfo is None
