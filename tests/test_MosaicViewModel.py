import pytest
import numpy as np
from unittest.mock import MagicMock
from le_beta_vis.frontend.viewmodels.MosaicViewModel import MosaicViewModel
from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.frontend.fitsconverters import ScalingFunction, Colormap


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    # Ensure known config values
    config.set("global:physics:kev_conversion", 2.0)  # Simple factor

    # Updated keys (Shared)
    config.set("gui:raw_analysis:vis_range_min", 10.0)
    config.set("gui:raw_analysis:vis_range_max", 100.0)

    # Mosaic keys
    config.set("gui:mosaic:height", 150)
    config.set("gui:mosaic:thumbnail_height", 120)
    config.set("gui:mosaic:scaling_function", "log")

    vm = MosaicViewModel(config)

    # Mock the converter to return a numpy array
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10), dtype=np.uint8)

    return vm


def test_initial_state(view_model):
    """Test initial state."""
    assert view_model.thumbnails == []
    assert view_model.selectedIndex == -1
    # Check config accessors
    assert view_model.containerHeight == 150
    assert view_model.thumbnailHeight == 120


def test_set_captures(view_model):
    """Test processing captures into thumbnails."""

    # Mock Captures
    capture1 = MagicMock(spec=CCDCaptureModel)
    capture1.rawData.return_value = np.zeros((10, 10))

    capture2 = MagicMock(spec=CCDCaptureModel)
    capture2.rawData.return_value = np.zeros((10, 10))

    captures = [capture1, capture2]

    # Setup Callbacks
    thumbnails_cb = MagicMock()
    selection_cb = MagicMock()
    view_model.add_thumbnails_changed_callback(thumbnails_cb)
    view_model.add_selection_changed_callback(selection_cb)

    # Execute
    view_model.setCaptures(captures)

    # Verify State
    assert len(view_model.thumbnails) == 2
    assert isinstance(view_model.thumbnails[0], np.ndarray)
    assert view_model.selectedIndex == 0

    # Verify Converter Calls with scaled data (0.0 * 2.0 = 0.0)
    # Using np.array_equal check on call arguments
    args, kwargs = view_model._converter.convert.call_args
    assert np.array_equal(args[0], np.zeros((10, 10)) * 2.0)
    assert args[1] == Colormap.VIRIDIS
    assert args[2] == (10.0, 100.0)
    assert kwargs["scaling"] == ScalingFunction.LOG

    # Verify Callbacks
    thumbnails_cb.assert_called_once()
    selection_cb.assert_called_once_with(0)


def test_select_index(view_model):
    """Test selection logic."""
    # Setup state with 2 items
    view_model._captures = [MagicMock(), MagicMock()]
    view_model._thumbnails = ["T1", "T2"]
    view_model._selectedIndex = 0

    selection_cb = MagicMock()
    view_model.add_selection_changed_callback(selection_cb)

    # Valid selection
    view_model.selectIndex(1)
    assert view_model.selectedIndex == 1
    selection_cb.assert_called_once_with(1)

    selection_cb.reset_mock()

    # Same selection (Should be no-op)
    view_model.selectIndex(1)
    selection_cb.assert_not_called()

    # Invalid selection
    view_model.selectIndex(99)
    assert view_model.selectedIndex == 1  # Unchanged
    selection_cb.assert_not_called()
