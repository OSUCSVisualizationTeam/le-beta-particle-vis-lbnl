# Citation for Unit Tests: Verifies RawDataViewModel initialization, state management, and
# interaction with physical models.
# Date: 28/02/2026
# Adapted from Claude Code:
# Write headless PyTest unit tests for RawDataViewModel covering configuration, active tool changes,
# and interaction with CCDCaptureModel without using Qt.

import sys
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl
from le_beta_vis.frontend.fitsconverters import OpenCVBasedConverter, ScalingFunction
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    ActiveTool,
    RawDataViewModel,
)


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    physics_manager = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics_manager)
    # Mock the converter to return a numpy array
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)

    # Force synchronous execution for tests
    def mock_request():
        vm._render_worker_logic()

    vm._request_render = mock_request
    return vm


def test_initial_colormap_from_config():
    """Test that RawDataViewModel initializes its colormap from config."""
    config = MockConfigurationService()
    config.set("gui:raw_analysis:default_colormap", "plasma")
    physics_manager = PhysicsConversionManagerImpl(config)

    vm = RawDataViewModel(config, physics_manager)
    assert vm.colormap == "plasma"


def test_initial_state(view_model):
    """Test the initial state of the ViewModel."""
    assert view_model.activeIndex == -1


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


def test_default_tool_is_box_select(view_model):
    """Default active tool should be BOX_SELECT (ROI)."""
    assert view_model.activeTool == ActiveTool.BOX_SELECT
    assert view_model.isBoxSelectActive is True


def test_toggle_magnifier(view_model):
    """toggleMagnifier toggles between MAGNIFIER and BOX_SELECT."""
    assert view_model.activeTool == ActiveTool.BOX_SELECT

    view_model.toggleMagnifier()
    assert view_model.activeTool == ActiveTool.MAGNIFIER
    assert view_model.isMagnifierActive is True

    view_model.toggleMagnifier()
    assert view_model.activeTool == ActiveTool.BOX_SELECT
    assert view_model.isBoxSelectActive is True


def test_toggle_magnifier_notifies(view_model):
    """toggleMagnifier fires the active_tool_changed callback."""
    cb = MagicMock()
    view_model.add_active_tool_changed_callback(cb)

    view_model.toggleMagnifier()
    assert cb.call_count == 1

    view_model.toggleMagnifier()
    assert cb.call_count == 2


def test_pointer_hover_position(view_model):
    """setPointerHoverPosition stores the position and notifies."""
    mock_capture = MagicMock(spec=CCDCaptureModel)
    raw = np.ones((10, 10))
    mock_capture.rawData.return_value = raw
    view_model._captures = [mock_capture]
    view_model._activeIndex = 0
    view_model._image_bounds = (10, 10)

    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)

    view_model.setPointerHoverPosition(3, 7)
    assert cb.call_count == 1

    info = view_model.pointerHoverInfo
    assert info is not None
    row, col, kev = info
    assert row == 3
    assert col == 7


def test_clear_pointer_hover(view_model):
    """clearPointerHover resets hover info to None."""
    view_model._image_bounds = (10, 10)
    view_model.setPointerHoverPosition(5, 5)

    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)

    view_model.clearPointerHover()
    assert cb.call_count == 1
    assert view_model.pointerHoverInfo is None


def test_clear_pointer_hover_noop_when_already_none(view_model):
    """clearPointerHover is a no-op when hover is already None."""
    cb = MagicMock()
    view_model.add_pointer_hover_changed_callback(cb)

    view_model.clearPointerHover()
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# Regression tests: initial render with real converter (issue: blank FITS)
# ---------------------------------------------------------------------------


def _make_vm_with_real_converter(config):
    """Helper: build a RawDataViewModel with OpenCVBasedConverter and sync render."""
    physics = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics)
    vm._converter = OpenCVBasedConverter()

    def sync_render():
        vm._render_worker_logic()

    vm._request_render = sync_render
    return vm


def test_loadfile_produces_buffer_with_real_converter():
    """loadFile with OpenCVBasedConverter must produce a non-None buffer."""
    config = MockConfigurationService()
    vm = _make_vm_with_real_converter(config)

    mock_capture = MagicMock(spec=CCDCaptureModel)
    mock_capture.rawData.return_value = np.random.randint(
        0, 65535, (64, 64), dtype=np.uint16
    ).astype(np.float64)
    mock_capture.info.return_value.rows = 64
    mock_capture.info.return_value.cols = 64
    mock_capture.info.return_value.min = 0
    mock_capture.info.return_value.max = 65535

    module = sys.modules["le_beta_vis.frontend.viewmodels.RawDataViewModel"]
    with patch.object(module, "Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        with patch.object(CCDCaptureModel, "load", return_value=[mock_capture]):
            vm.loadFile("test.fits")

    assert vm.currentBuffer is not None
    assert vm.currentBuffer.dtype == np.uint8
    assert len(vm.currentBuffer.shape) == 3


def test_render_with_yaml_backed_config(tmp_path):
    """Render pipeline works with YAMLBackedConfigurationService."""
    from le_beta_vis.common.YAMLBackedConfigurationService import (
        YAMLBackedConfigurationService,
    )

    config = YAMLBackedConfigurationService(yaml_path=tmp_path / "test.yaml")
    vm = _make_vm_with_real_converter(config)

    mock_capture = MagicMock(spec=CCDCaptureModel)
    mock_capture.rawData.return_value = np.ones((32, 32), dtype=np.float64)
    mock_capture.info.return_value.rows = 32
    mock_capture.info.return_value.cols = 32
    mock_capture.info.return_value.min = 0
    mock_capture.info.return_value.max = 1

    module = sys.modules["le_beta_vis.frontend.viewmodels.RawDataViewModel"]
    with patch.object(module, "Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        with patch.object(CCDCaptureModel, "load", return_value=[mock_capture]):
            vm.loadFile("test.fits")

    assert vm.currentBuffer is not None


def test_render_with_wide_vis_range():
    """Render must not throw with vis_range_max=700.0 (user-reported config)."""
    config = MockConfigurationService()
    config.set("gui:raw_analysis:vis_range_max", 700.0)
    config.set("gui:raw_analysis:default_colormap", "inferno")
    vm = _make_vm_with_real_converter(config)

    mock_capture = MagicMock(spec=CCDCaptureModel)
    mock_capture.rawData.return_value = np.zeros((16, 16), dtype=np.float64)
    mock_capture.info.return_value.rows = 16
    mock_capture.info.return_value.cols = 16
    mock_capture.info.return_value.min = 0
    mock_capture.info.return_value.max = 0

    vm._captures = [mock_capture]
    vm._activeIndex = 0
    vm._render_worker_logic()

    assert vm.currentBuffer is not None


def test_render_exception_is_logged():
    """Exceptions in render are logged via logger.exception."""
    config = MockConfigurationService()
    vm = _make_vm_with_real_converter(config)

    mock_capture = MagicMock(spec=CCDCaptureModel)
    mock_capture.rawData.side_effect = RuntimeError("boom")
    vm._captures = [mock_capture]
    vm._activeIndex = 0

    module = sys.modules["le_beta_vis.frontend.viewmodels.RawDataViewModel"]
    with patch.object(module, "logger") as mock_logger:
        vm._render_worker_logic()

    mock_logger.exception.assert_called_once()
    assert vm.currentBuffer is None


def test_request_render_skips_when_no_data():
    """_request_render is a no-op when no captures are loaded.

    Prevents stale renders during View initialisation (e.g. colormap
    selector emitting currentTextChanged) from enqueuing a render that
    clears the display buffer.
    """
    config = MockConfigurationService()
    vm = _make_vm_with_real_converter(config)

    assert vm._activeIndex == -1
    assert vm._captures == []

    # Trigger setColormap which calls _request_render internally
    vm.setColormap("inferno")

    # Queue should be empty — render was skipped
    assert vm._render_queue.empty()


def test_request_render_coalescing_does_not_raise():
    """Rapid concurrent _request_render calls must not raise or deadlock.

    Verifies the put_nowait/Full guard is safe under concurrent callers.
    With the old get_nowait()/put() pair, two racing threads could both
    drain the queue and then both block on put(), deadlocking the UI thread.
    """
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics)

    errors: list = []

    def call_many() -> None:
        for _ in range(200):
            try:
                vm._request_render()
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=call_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"_request_render raised: {errors}"
    assert vm._render_queue.qsize() <= 1


def test_current_buffer_lock_allows_concurrent_access():
    """Concurrent reads and writes of _current_buffer must not raise.

    Verifies that _buffer_lock serialises access so no RuntimeError or
    corruption occurs when the render thread writes while the UI thread reads.
    """
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics)

    errors: list = []

    def read_buffer() -> None:
        for _ in range(500):
            try:
                _ = vm.currentBuffer
            except Exception as exc:
                errors.append(exc)

    def write_buffer() -> None:
        for _ in range(500):
            try:
                with vm._buffer_lock:
                    vm._current_buffer = None
            except Exception as exc:
                errors.append(exc)

    threads = [
        threading.Thread(target=read_buffer),
        threading.Thread(target=read_buffer),
        threading.Thread(target=write_buffer),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"concurrent buffer access raised: {errors}"


# ---------------------------------------------------------------------------
# Scaling function tests (issue #83)
# ---------------------------------------------------------------------------


def test_initial_scaling_from_config():
    """Test that RawDataViewModel initializes its scaling function from config."""
    config = MockConfigurationService()
    config.set("gui:raw_analysis:default_scaling_function", "log")
    physics_manager = PhysicsConversionManagerImpl(config)

    vm = RawDataViewModel(config, physics_manager)
    assert vm.scalingFunction == "log"


def test_set_scaling_function_triggers_render(view_model):
    """Test that setScalingFunction updates state and triggers render."""
    mock_capture = MagicMock()
    mock_capture.rawData.return_value = np.zeros((10, 10))
    view_model._captures = [mock_capture]
    view_model._activeIndex = 0

    view_model.setScalingFunction("sqrt")

    assert view_model.scalingFunction == "sqrt"
    _, kwargs = view_model._converter.convert.call_args
    assert kwargs["scaling"] == ScalingFunction.SQRT


def test_set_scaling_function_invalid_is_noop(view_model):
    """Test that an invalid scaling function string is silently ignored."""
    original = view_model.scalingFunction
    view_model.setScalingFunction("invalid")
    assert view_model.scalingFunction == original
