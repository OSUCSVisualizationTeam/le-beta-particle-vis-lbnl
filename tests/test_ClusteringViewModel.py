import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    ActiveTool,
    ClusteringState,
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


def _setup_for_clustering(vm):
    """Helper: load mock data, set tool, add ROI, set extractor."""
    mock_capture = MagicMock()
    mock_capture.rawData.return_value = np.arange(
        100, dtype=float
    ).reshape(10, 10)
    mock_capture.info.return_value = MagicMock(
        rows=10, cols=10, min=0, max=99
    )
    vm._captures = [mock_capture]
    vm._activeIndex = 0
    vm._image_bounds = (10, 10)

    vm.setClusterExtractor(MockClusterExtractor(delay_seconds=0.01))
    vm.setActiveTool(ActiveTool.BOX_SELECT)
    vm.addRoi(0, 0, 5, 5)


# --- isClusteringAvailable ---


def test_clustering_unavailable_no_extractor(view_model):
    """False when no extractor is set."""
    assert view_model.isClusteringAvailable is False


def test_clustering_unavailable_wrong_tool(view_model):
    """False when not in BOX_SELECT mode."""
    _setup_for_clustering(view_model)
    view_model.setActiveTool(ActiveTool.POINTER)
    assert view_model.isClusteringAvailable is False


def test_clustering_unavailable_no_roi(view_model):
    """False when no ROI exists."""
    _setup_for_clustering(view_model)
    view_model.clearRois()
    assert view_model.isClusteringAvailable is False


def test_clustering_unavailable_no_data(view_model):
    """False when no raw data is loaded."""
    view_model.setClusterExtractor(
        MockClusterExtractor(delay_seconds=0.01)
    )
    view_model.setActiveTool(ActiveTool.BOX_SELECT)
    view_model.addRoi(0, 0, 5, 5)
    assert view_model.isClusteringAvailable is False


def test_clustering_available(view_model):
    """True when all conditions are met."""
    _setup_for_clustering(view_model)
    assert view_model.isClusteringAvailable is True


# --- triggerClustering ---


def test_trigger_sets_running(view_model):
    """triggerClustering sets state to RUNNING."""
    _setup_for_clustering(view_model)
    view_model.triggerClustering()
    assert view_model.clusteringState == ClusteringState.RUNNING


def test_trigger_fires_state_callback(view_model):
    """triggerClustering fires the state changed callback."""
    _setup_for_clustering(view_model)
    cb = MagicMock()
    view_model.add_clustering_state_changed_callback(cb)
    view_model.triggerClustering()
    cb.assert_called()


def test_trigger_noop_when_unavailable(view_model):
    """triggerClustering does nothing when conditions not met."""
    cb = MagicMock()
    view_model.add_clustering_state_changed_callback(cb)
    view_model.triggerClustering()
    assert view_model.clusteringState == ClusteringState.IDLE
    cb.assert_not_called()


# --- cancelClustering ---


def test_cancel_resets_idle(view_model):
    """cancelClustering sets state back to IDLE."""
    _setup_for_clustering(view_model)
    view_model.triggerClustering()
    view_model.cancelClustering()
    assert view_model.clusteringState == ClusteringState.IDLE


# --- Extraction completion ---


def test_success_stores_results(view_model):
    """Results are populated after extraction completes."""
    _setup_for_clustering(view_model)
    done = threading.Event()

    def on_completed():
        done.set()

    view_model.add_clustering_completed_callback(on_completed)
    view_model.triggerClustering()
    done.wait(timeout=2.0)

    results = view_model.clusteringResults
    assert len(results) == 1
    assert view_model.clusteringState == ClusteringState.IDLE


def test_success_fires_completed_callback(view_model):
    """Completed callback fires on success."""
    _setup_for_clustering(view_model)
    done = threading.Event()
    cb = MagicMock(side_effect=lambda: done.set())

    view_model.add_clustering_completed_callback(cb)
    view_model.triggerClustering()
    done.wait(timeout=2.0)

    cb.assert_called_once()


def test_cancel_prevents_completed_callback(view_model):
    """Cancelling during extraction suppresses completed callback."""
    extractor = MockClusterExtractor(delay_seconds=1.0)
    _setup_for_clustering(view_model)
    view_model.setClusterExtractor(extractor)

    cb = MagicMock()
    view_model.add_clustering_completed_callback(cb)
    view_model.triggerClustering()
    view_model.cancelClustering()

    import time
    time.sleep(0.1)
    cb.assert_not_called()


# --- Timeout ---


def test_timeout_fires_error_callback(view_model):
    """Error callback fires when extraction times out."""
    # Use a slow extractor and a very short timeout
    slow = MockClusterExtractor(delay_seconds=5.0)
    _setup_for_clustering(view_model)
    view_model.setClusterExtractor(slow)
    view_model._config.set(
        "gui:raw_analysis:clustering_timeout_seconds", 0.1
    )

    error_fired = threading.Event()
    view_model.add_clustering_error_callback(lambda: error_fired.set())

    view_model.triggerClustering()
    assert error_fired.wait(timeout=2.0), "Error callback not fired"
    assert view_model.clusteringState == ClusteringState.IDLE
    assert view_model.clusteringError is not None
    assert "timed out" in view_model.clusteringError.lower()


def test_timeout_cancels_extractor(view_model):
    """Timeout calls cancel() on the extractor."""
    slow = MockClusterExtractor(delay_seconds=5.0)
    _setup_for_clustering(view_model)
    view_model.setClusterExtractor(slow)
    view_model._config.set(
        "gui:raw_analysis:clustering_timeout_seconds", 0.1
    )

    done = threading.Event()
    view_model.add_clustering_error_callback(lambda: done.set())

    view_model.triggerClustering()
    done.wait(timeout=2.0)
    # MockClusterExtractor sets _cancelled = True on cancel()
    assert slow._cancelled is True


def test_successful_completion_cancels_timer(view_model):
    """Successful extraction cancels the timeout timer."""
    _setup_for_clustering(view_model)
    view_model._config.set(
        "gui:raw_analysis:clustering_timeout_seconds", 60
    )

    done = threading.Event()
    view_model.add_clustering_completed_callback(lambda: done.set())

    view_model.triggerClustering()
    assert done.wait(timeout=2.0), "Completion callback not fired"
    assert view_model._clustering_timeout_timer is None
    assert view_model.clusteringError is None


def test_clustering_error_cleared_on_new_trigger(view_model):
    """A new triggerClustering clears any previous error."""
    _setup_for_clustering(view_model)
    view_model._clusteringError = "previous error"

    done = threading.Event()
    view_model.add_clustering_completed_callback(lambda: done.set())
    view_model.triggerClustering()
    done.wait(timeout=2.0)
    assert view_model.clusteringError is None


# --- Progress tracking ---


def test_trigger_resets_progress(view_model):
    """triggerClustering resets clusteringProgress to 0.0."""
    _setup_for_clustering(view_model)
    view_model._clusteringProgress = 0.5
    view_model.triggerClustering()
    # Progress is reset before extraction starts
    assert view_model.clusteringProgress == 0.0


def test_progress_callback_fires(view_model):
    """Progress callback is registered and fires on extractor call."""
    from le_beta_vis.common.OptimalClassicalClusterExtractor import (
        OptimalClassicalClusterExtractor,
    )

    # Use OptimalClassical since it actually reports progress
    extractor = OptimalClassicalClusterExtractor(
        sigma_multiplier=4.0, ped_width=100, kev_conversion=0.01,
    )
    _setup_for_clustering(view_model)

    # Give it data with a cluster above threshold (4*100=400)
    data = np.zeros((20, 20), dtype=float)
    for i in range(5):
        data[10, 10 + i] = 500
    mock_capture = MagicMock()
    mock_capture.rawData.return_value = data
    mock_capture.info.return_value = MagicMock(
        rows=20, cols=20, min=0, max=500
    )
    view_model._captures = [mock_capture]
    view_model._image_bounds = (20, 20)
    view_model.clearRois()
    view_model.addRoi(0, 0, 20, 20)
    view_model.setClusterExtractor(extractor)

    progress_fired = threading.Event()
    view_model.add_clustering_progress_callback(
        lambda: progress_fired.set()
    )

    done = threading.Event()
    view_model.add_clustering_completed_callback(lambda: done.set())
    view_model.triggerClustering()
    done.wait(timeout=5.0)

    assert progress_fired.is_set()
    assert view_model.clusteringProgress > 0.0


def test_progress_passes_callback_to_extractor(view_model):
    """triggerClustering passes progress_callback to the extractor."""
    _setup_for_clustering(view_model)

    extract_kwargs = {}
    original_extract = view_model._clusterExtractor.extract

    def spy_extract(*args, **kwargs):
        extract_kwargs.update(kwargs)
        return original_extract(*args, **kwargs)

    view_model._clusterExtractor.extract = spy_extract

    done = threading.Event()
    view_model.add_clustering_completed_callback(lambda: done.set())
    view_model.triggerClustering()
    done.wait(timeout=2.0)

    assert "progress_callback" in extract_kwargs
    assert extract_kwargs["progress_callback"] is not None
