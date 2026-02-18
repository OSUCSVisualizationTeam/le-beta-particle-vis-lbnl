import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.frontend.viewmodels.RawDataViewModel import RawDataViewModel


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    vm = RawDataViewModel(config)
    # Mock the converter to return a numpy array
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)

    # Force synchronous execution for tests
    def mock_request():
        vm._render_worker_logic()

    vm._request_render = mock_request
    return vm


def test_initial_state(view_model):
    """Test the initial state of the ViewModel."""
    assert view_model.activeIndex == -1
    assert view_model.hduSummaries == []


def test_load_file_success(view_model):
    """Test loading a file successfully updates state and invokes callbacks."""
    # Mock mosaic VM converter to return buffer
    view_model.mosaicViewModel._converter = MagicMock()
    view_model.mosaicViewModel._converter.convert.return_value = np.zeros((10, 10))

    mock_capture1 = MagicMock(spec=CCDCaptureModel)
    mock_capture1.info.return_value.rows = 100
    mock_capture1.info.return_value.cols = 100
    mock_capture1.rawData.return_value = np.zeros((10, 10))

    mock_file_loaded_cb = MagicMock()
    view_model.add_file_loaded_callback(mock_file_loaded_cb)

    module = sys.modules["le_beta_vis.frontend.viewmodels.RawDataViewModel"]
    with patch.object(module, "Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        with patch.object(
            CCDCaptureModel, "load", return_value=[mock_capture1]
        ) as mock_load:
            view_model.loadFile("dummy/path/file.fits")
            mock_load.assert_called_once()
            mock_file_loaded_cb.assert_called_once()
            assert view_model.activeIndex == 0
            assert "100x100" in view_model.hduSummaries[0]


def test_load_file_renders_first_hdu(view_model):
    """Test that loadFile results in a render request for the first HDU."""
    mock_capture = MagicMock(spec=CCDCaptureModel)
    mock_capture.rawData.return_value = np.zeros((10, 10))
    mock_capture.info.return_value.rows = 10
    mock_capture.info.return_value.cols = 10

    module = sys.modules["le_beta_vis.frontend.viewmodels.RawDataViewModel"]
    with patch.object(module, "Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        with patch.object(CCDCaptureModel, "load", return_value=[mock_capture]):
            view_model.loadFile("dummy.fits")

            # The flow is:
            # 1. loadFile
            # 2. mosaic.setCaptures
            # 3. notify_selection(0)
            # 4. setActiveHDU(0)
            # 5. render
            assert view_model.activeIndex == 0
            view_model._converter.convert.assert_called()


def test_set_active_hdu(view_model):
    """Test switching HDUs and verify keV conversion factor."""
    view_model._config.set("global:physics:kev_conversion", 0.5)

    mock_capture = MagicMock(spec=CCDCaptureModel)
    data = np.array([[10, 20], [30, 40]])
    mock_capture.rawData.return_value = data
    view_model._captures = [mock_capture, mock_capture]
    view_model._activeIndex = 0

    view_model.setActiveHDU(1)

    assert view_model.activeIndex == 1
    # Verify converter called with scaled data (data * 0.5)
    args, _ = view_model._converter.convert.call_args
    assert np.array_equal(args[0], data * 0.5)
    assert isinstance(view_model.currentBuffer, np.ndarray)


def test_set_colormap(view_model):
    """Test updating parameters triggers render."""
    mock_capture = MagicMock()
    mock_capture.rawData.return_value = np.zeros((10, 10))
    view_model._captures = [mock_capture]
    view_model._activeIndex = 0

    mock_image_changed_cb = MagicMock()
    view_model.add_image_changed_callback(mock_image_changed_cb)

    view_model.setColormap("magma")

    assert view_model.colormap == "magma"
    view_model._converter.convert.assert_called()


def test_zoom_logic(view_model):
    """Test zoom in and out logic."""
    # Default is 1.0
    assert view_model.scale == 1.0

    mock_cb = MagicMock()
    view_model.add_scale_changed_callback(mock_cb)

    # Zoom In
    # Default zoom factor is 1.2
    view_model.zoomIn()
    assert view_model.scale == 1.2
    mock_cb.assert_called_once()
    mock_cb.reset_mock()

    # Zoom Out
    view_model.zoomOut()
    assert abs(view_model.scale - 1.0) < 0.0001
    mock_cb.assert_called_once()

    # Reset Zoom
    view_model.zoomIn()
    view_model.zoomIn()
    assert view_model.scale > 1.0
    mock_cb.reset_mock()
    view_model.resetZoom()
    assert view_model.scale == 1.0
    mock_cb.assert_called_once()
