from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.RoiRect import RoiRect
from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.ClusterAnalysisViewModel import (
    ClusterAnalysisViewModel,
)
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    ActiveTool,
    RawDataViewModel,
)

_RAW = np.zeros((10, 10), dtype=float)


@pytest.fixture
def cavm():
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    return ClusterAnalysisViewModel(config, physics, lambda: _RAW.copy())


@pytest.fixture
def rdvm():
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics)
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
    return vm


# --- isBoxSelectActive (RDVM tool state) ---


def test_is_box_select_active_initial(rdvm):
    """Box select is active by default."""
    assert rdvm.isBoxSelectActive is True


def test_is_box_select_active_after_switch(rdvm):
    """isBoxSelectActive remains True after explicit BOX_SELECT set."""
    rdvm.setActiveTool(ActiveTool.BOX_SELECT)
    assert rdvm.isBoxSelectActive is True


def test_is_box_select_active_after_switch_away(rdvm):
    """isBoxSelectActive is False after switching to MAGNIFIER."""
    rdvm.setActiveTool(ActiveTool.MAGNIFIER)
    assert rdvm.isBoxSelectActive is False


# --- addRoi ---


def test_add_roi_stores_roi(cavm):
    """addRoi creates and stores the ROI."""
    roi = cavm.addRoi(10, 20, 50, 80)
    assert isinstance(roi, RoiRect)
    assert roi.geometry() == BoundingBox(10, 20, 50, 80)
    assert len(cavm.rois) == 1


def test_add_roi_normalizes_coords(cavm):
    """addRoi normalizes inverted coordinates."""
    roi = cavm.addRoi(50, 80, 10, 20)
    bbox = roi.geometry()
    assert bbox.top == 10
    assert bbox.left == 20
    assert bbox.bottom == 50
    assert bbox.right == 80


def test_add_roi_fires_callbacks(cavm):
    """addRoi fires both roi_changed and box_selection_completed."""
    roi_cb = MagicMock()
    sel_cb = MagicMock()
    cavm.add_roi_changed_callback(roi_cb)
    cavm.add_box_selection_completed_callback(sel_cb)
    cavm.addRoi(0, 0, 10, 10)
    roi_cb.assert_called_once()
    sel_cb.assert_called_once()


def test_multiple_rois(cavm):
    """Multiple ROIs can be added."""
    cavm.addRoi(0, 0, 10, 10)
    cavm.addRoi(20, 20, 30, 30)
    assert len(cavm.rois) == 2


# --- clearRois ---


def test_clear_rois(cavm):
    """clearRois removes all ROIs and fires callback."""
    cavm.addRoi(0, 0, 10, 10)
    cb = MagicMock()
    cavm.add_roi_changed_callback(cb)
    cavm.clearRois()
    assert len(cavm.rois) == 0
    cb.assert_called_once()


def test_clear_rois_when_empty(cavm):
    """clearRois does not fire if already empty."""
    cb = MagicMock()
    cavm.add_roi_changed_callback(cb)
    cavm.clearRois()
    cb.assert_not_called()


# --- removeRoi ---


def test_remove_roi(cavm):
    """Removing ROI by index works."""
    cavm.addRoi(0, 0, 10, 10)
    cavm.addRoi(20, 20, 30, 30)
    cb = MagicMock()
    cavm.add_roi_changed_callback(cb)
    cavm.removeRoi(0)
    assert len(cavm.rois) == 1
    assert cavm.rois[0].geometry() == BoundingBox(20, 20, 30, 30)
    cb.assert_called_once()


def test_remove_roi_invalid_index(cavm):
    """Removing out-of-bounds index does nothing."""
    cavm.addRoi(0, 0, 10, 10)
    cb = MagicMock()
    cavm.add_roi_changed_callback(cb)
    cavm.removeRoi(5)
    assert len(cavm.rois) == 1
    cb.assert_not_called()


def test_remove_roi_negative_index(cavm):
    """Removing negative index does nothing."""
    cavm.addRoi(0, 0, 10, 10)
    cb = MagicMock()
    cavm.add_roi_changed_callback(cb)
    cavm.removeRoi(-1)
    assert len(cavm.rois) == 1
    cb.assert_not_called()


# --- rois returns copy ---


def test_rois_returns_copy(cavm):
    """rois property returns a copy, not the internal list."""
    cavm.addRoi(0, 0, 10, 10)
    rois_copy = cavm.rois
    rois_copy.clear()
    assert len(cavm.rois) == 1


# --- Config properties ---


def test_box_select_color(cavm):
    """boxSelectColor returns config default."""
    assert cavm.boxSelectColor == "#00BFFF"


def test_box_select_border_width(cavm):
    """boxSelectBorderWidth returns config default."""
    assert cavm.boxSelectBorderWidth == 2


# --- clear + re-add cycle ---


def test_clear_then_readd_roi(cavm):
    """Clearing then adding a new ROI works correctly."""
    cavm.addRoi(0, 0, 10, 10)
    assert len(cavm.rois) == 1

    cavm.clearRois()
    assert len(cavm.rois) == 0

    roi = cavm.addRoi(20, 30, 40, 50)
    assert len(cavm.rois) == 1
    bbox = roi.geometry()
    assert bbox.top == 20
    assert bbox.left == 30
    assert bbox.bottom == 40
    assert bbox.right == 50
