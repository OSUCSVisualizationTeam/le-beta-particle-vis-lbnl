import pytest
import sys
import numpy as np
from unittest.mock import MagicMock, patch
from le_beta_vis.frontend.viewmodels.RawDataViewModel import RawDataViewModel
from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel


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


def test_set_active_hdu(view_model):
    """Test switching HDUs."""
    mock_capture = MagicMock(spec=CCDCaptureModel)
    mock_capture.rawData.return_value = np.zeros((10, 10))
    view_model._captures = [mock_capture, mock_capture]
    view_model._activeIndex = 0

    mock_image_changed_cb = MagicMock()
    view_model.add_image_changed_callback(mock_image_changed_cb)

    view_model.setActiveHDU(1)

    assert view_model.activeIndex == 1
    view_model._converter.convert.assert_called()
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
