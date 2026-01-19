import pytest
from unittest.mock import MagicMock, patch
from le_beta_vis.frontend.viewmodels.RawDataViewModel import RawDataViewModel
from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    vm = RawDataViewModel(config)
    # Mock the converter to return a string/mock instead of a real QPixmap
    # This avoids GUI dependencies in logic tests
    vm._converter = MagicMock()
    vm._converter.convert.return_value = "MockPixmap"
    return vm


def test_initial_state(view_model):
    """Test the initial state of the ViewModel."""
    assert view_model.activeIndex == -1
    assert view_model.hduSummaries == []


def test_load_file_success(view_model):
    """Test loading a file successfully updates state and invokes callbacks."""

    # Mock CCDCaptureModel.load to return a list of dummy captures
    mock_capture1 = MagicMock(spec=CCDCaptureModel)
    mock_capture1.info.return_value.rows = 100
    mock_capture1.info.return_value.cols = 100
    mock_capture1.rawData.return_value = MagicMock()

    mock_capture2 = MagicMock(spec=CCDCaptureModel)
    mock_capture2.info.return_value.rows = 200
    mock_capture2.info.return_value.cols = 200
    mock_capture2.rawData.return_value = MagicMock()

    # Create mock callbacks
    mock_file_loaded_cb = MagicMock()
    mock_image_changed_cb = MagicMock()
    view_model.add_file_loaded_callback(mock_file_loaded_cb)
    view_model.add_image_changed_callback(mock_image_changed_cb)

    # Mock Path.exists to allow loading logic to proceed
    with patch(
        "le_beta_vis.frontend.viewmodels.RawDataViewModel.Path.exists",
        return_value=True,
    ):
        with patch(
            "le_beta_vis.common.CCDCaptureModel.CCDCaptureModel.load",
            return_value=[mock_capture1, mock_capture2],
        ) as mock_load:

            view_model.loadFile("dummy/path/file.fits")

            mock_load.assert_called_once()

            # Check callbacks
            mock_file_loaded_cb.assert_called_once()
            mock_image_changed_cb.assert_called_once()

            # Check State
            assert view_model.activeIndex == 0
            assert len(view_model.hduSummaries) == 2
            assert "100x100" in view_model.hduSummaries[0]

            # Verify the converter was called (logic check)
            view_model._converter.convert.assert_called()


def test_set_active_hdu(view_model):
    """Test switching HDUs."""
    # Setup state
    mock_captures = [MagicMock(), MagicMock()]
    view_model._captures = mock_captures
    view_model._activeIndex = 0

    mock_image_changed_cb = MagicMock()
    view_model.add_image_changed_callback(mock_image_changed_cb)

    view_model.setActiveHDU(1)

    assert view_model.activeIndex == 1
    mock_image_changed_cb.assert_called_once()


def test_set_colormap(view_model):
    """Test updating parameters triggers image refresh."""
    mock_image_changed_cb = MagicMock()
    view_model.add_image_changed_callback(mock_image_changed_cb)

    view_model.setColormap("magma")

    assert view_model._colormap == "magma"
    mock_image_changed_cb.assert_called_once()
