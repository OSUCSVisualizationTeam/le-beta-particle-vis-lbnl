from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.RoiRect import RoiRect
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    ActiveTool,
    RawDataViewModel,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    physics_manager = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics_manager)
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros(
        (10, 10, 3), dtype=np.uint8
    )

    def mock_request():
        vm._render_worker_logic()

    vm._request_render = mock_request
    return vm


# --- isBoxSelectActive ---


def test_is_box_select_active_initial(view_model):
    """Test that box select is active by default."""
    assert view_model.isBoxSelectActive is True


def test_is_box_select_active_after_switch(view_model):
    """Test isBoxSelectActive is True after switching to BOX_SELECT."""
    view_model.setActiveTool(ActiveTool.BOX_SELECT)
    assert view_model.isBoxSelectActive is True


def test_is_box_select_active_after_switch_away(view_model):
    """Test isBoxSelectActive returns False after switching away."""
    view_model.setActiveTool(ActiveTool.BOX_SELECT)
    view_model.setActiveTool(ActiveTool.MAGNIFIER)
    assert view_model.isBoxSelectActive is False


# --- addRoi ---


def test_add_roi_stores_roi(view_model):
    """Test that addRoi creates and stores the ROI."""
    roi = view_model.addRoi(10, 20, 50, 80)
    assert isinstance(roi, RoiRect)
    assert roi.geometry() == BoundingBox(10, 20, 50, 80)
    assert len(view_model.rois) == 1


def test_add_roi_normalizes_coords(view_model):
    """Test that addRoi normalizes inverted coordinates."""
    roi = view_model.addRoi(50, 80, 10, 20)
    bbox = roi.geometry()
    assert bbox.top == 10
    assert bbox.left == 20
    assert bbox.bottom == 50
    assert bbox.right == 80


def test_add_roi_fires_callbacks(view_model):
    """Test that addRoi fires both roi_changed and selection_completed."""
    roi_cb = MagicMock()
    sel_cb = MagicMock()
    view_model.add_roi_changed_callback(roi_cb)
    view_model.add_box_selection_completed_callback(sel_cb)
    view_model.addRoi(0, 0, 10, 10)
    roi_cb.assert_called_once()
    sel_cb.assert_called_once()


def test_multiple_rois(view_model):
    """Test adding multiple ROIs."""
    view_model.addRoi(0, 0, 10, 10)
    view_model.addRoi(20, 20, 30, 30)
    assert len(view_model.rois) == 2


# --- clearRois ---


def test_clear_rois(view_model):
    """Test that clearRois removes all ROIs and fires callback."""
    view_model.addRoi(0, 0, 10, 10)
    cb = MagicMock()
    view_model.add_roi_changed_callback(cb)
    view_model.clearRois()
    assert len(view_model.rois) == 0
    cb.assert_called_once()


def test_clear_rois_when_empty(view_model):
    """Test that clearRois does not fire if already empty."""
    cb = MagicMock()
    view_model.add_roi_changed_callback(cb)
    view_model.clearRois()
    cb.assert_not_called()


# --- removeRoi ---


def test_remove_roi(view_model):
    """Test removing an ROI by index."""
    view_model.addRoi(0, 0, 10, 10)
    view_model.addRoi(20, 20, 30, 30)
    cb = MagicMock()
    view_model.add_roi_changed_callback(cb)
    view_model.removeRoi(0)
    assert len(view_model.rois) == 1
    assert view_model.rois[0].geometry() == BoundingBox(20, 20, 30, 30)
    cb.assert_called_once()


def test_remove_roi_invalid_index(view_model):
    """Test that removing an invalid index does nothing."""
    view_model.addRoi(0, 0, 10, 10)
    cb = MagicMock()
    view_model.add_roi_changed_callback(cb)
    view_model.removeRoi(5)
    assert len(view_model.rois) == 1
    cb.assert_not_called()


def test_remove_roi_negative_index(view_model):
    """Test that removing a negative index does nothing."""
    view_model.addRoi(0, 0, 10, 10)
    cb = MagicMock()
    view_model.add_roi_changed_callback(cb)
    view_model.removeRoi(-1)
    assert len(view_model.rois) == 1
    cb.assert_not_called()


# --- rois returns copy ---


def test_rois_returns_copy(view_model):
    """Test that rois property returns a copy, not the internal list."""
    view_model.addRoi(0, 0, 10, 10)
    rois_copy = view_model.rois
    rois_copy.clear()
    assert len(view_model.rois) == 1


# --- Config properties ---


def test_box_select_color(view_model):
    """Test boxSelectColor returns config value."""
    assert view_model.boxSelectColor == "#00BFFF"


def test_box_select_border_width(view_model):
    """Test boxSelectBorderWidth returns config value."""
    assert view_model.boxSelectBorderWidth == 2


# --- clear + re-add cycle ---


def test_clear_then_readd_roi(view_model):
    """Test that clearing ROIs then adding a new one works correctly."""
    view_model.addRoi(0, 0, 10, 10)
    assert len(view_model.rois) == 1

    view_model.clearRois()
    assert len(view_model.rois) == 0

    roi = view_model.addRoi(20, 30, 40, 50)
    assert len(view_model.rois) == 1
    bbox = roi.geometry()
    assert bbox.top == 20
    assert bbox.left == 30
    assert bbox.bottom == 40
    assert bbox.right == 50
