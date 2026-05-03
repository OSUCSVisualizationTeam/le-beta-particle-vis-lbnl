import threading
from unittest.mock import MagicMock
from typing import Union

import numpy as np
import pytest

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.ClusterAnalysisViewModel import (
    ClusterAnalysisViewModel,
    ClusteringState,
)

_DEFAULT_RAW = np.arange(100, dtype=float).reshape(10, 10)


class MockPhysicsManager(PhysicsConversionManager):
    def __init__(self, factor: float, ped_width: int):
        self._factor = factor
        self._ped_width = ped_width

    @property
    def kev_conversion_factor(self) -> float:
        return self._factor

    @property
    def pedestal_width(self) -> int:
        return self._ped_width

    def calculate_threshold(self, sigma: float) -> float:
        return sigma * self._ped_width

    def adu_to_kev(
        self, value: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        return value * self._factor


@pytest.fixture
def raw_holder():
    """Mutable container so tests can swap the raw data array."""
    return [_DEFAULT_RAW.copy()]


@pytest.fixture
def vm(raw_holder):
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    return ClusterAnalysisViewModel(
        config, physics, lambda: raw_holder[0]
    )


@pytest.fixture
def vm_no_data():
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    return ClusterAnalysisViewModel(config, physics, lambda: None)


def _setup_for_clustering(vm: ClusterAnalysisViewModel) -> None:
    """Inject extractor and add ROI so clustering is available."""
    vm.setClusterExtractor(MockClusterExtractor(delay_seconds=0.01))
    vm.addRoi(0, 0, 5, 5)


# --- isClusteringAvailable ---


def test_clustering_unavailable_no_extractor(vm):
    """False when no extractor is set."""
    assert vm.isClusteringAvailable is False


def test_clustering_unavailable_no_roi(vm):
    """False when no ROI exists."""
    _setup_for_clustering(vm)
    vm.clearRois()
    assert vm.isClusteringAvailable is False


def test_clustering_unavailable_no_data(vm_no_data):
    """False when no raw data is available."""
    vm_no_data.setClusterExtractor(MockClusterExtractor(delay_seconds=0.01))
    vm_no_data.addRoi(0, 0, 5, 5)
    assert vm_no_data.isClusteringAvailable is False


def test_clustering_available(vm):
    """True when all conditions are met."""
    _setup_for_clustering(vm)
    assert vm.isClusteringAvailable is True


# --- triggerClustering ---


def test_trigger_sets_running(vm):
    """triggerClustering sets state to RUNNING."""
    _setup_for_clustering(vm)
    vm.triggerClustering()
    assert vm.clusteringState == ClusteringState.RUNNING


def test_trigger_fires_state_callback(vm):
    """triggerClustering fires the state changed callback."""
    _setup_for_clustering(vm)
    cb = MagicMock()
    vm.add_clustering_state_changed_callback(cb)
    vm.triggerClustering()
    cb.assert_called()


def test_trigger_noop_when_unavailable(vm):
    """triggerClustering does nothing when conditions not met."""
    cb = MagicMock()
    vm.add_clustering_state_changed_callback(cb)
    vm.triggerClustering()
    assert vm.clusteringState == ClusteringState.IDLE
    cb.assert_not_called()


# --- cancelClustering ---


def test_cancel_resets_idle(vm):
    """cancelClustering sets state back to IDLE."""
    _setup_for_clustering(vm)
    vm.triggerClustering()
    vm.cancelClustering()
    assert vm.clusteringState == ClusteringState.IDLE


# --- Extraction completion ---


def test_success_stores_results(vm):
    """Results are populated after extraction completes."""
    _setup_for_clustering(vm)
    done = threading.Event()

    vm.add_clustering_completed_callback(lambda: done.set())
    vm.triggerClustering()
    done.wait(timeout=2.0)

    results = vm.clusteringResults
    assert len(results) == 1
    assert vm.clusteringState == ClusteringState.IDLE


def test_success_fires_completed_callback(vm):
    """Completed callback fires on success."""
    _setup_for_clustering(vm)
    done = threading.Event()
    cb = MagicMock(side_effect=lambda: done.set())

    vm.add_clustering_completed_callback(cb)
    vm.triggerClustering()
    done.wait(timeout=2.0)

    cb.assert_called_once()


def test_cancel_prevents_completed_callback(vm):
    """Cancelling during extraction suppresses completed callback."""
    extractor = MockClusterExtractor(delay_seconds=1.0)
    vm.setClusterExtractor(extractor)
    vm.addRoi(0, 0, 5, 5)

    cb = MagicMock()
    vm.add_clustering_completed_callback(cb)
    vm.triggerClustering()
    vm.cancelClustering()

    import time
    time.sleep(0.1)
    cb.assert_not_called()


# --- Timeout ---


def test_timeout_fires_error_callback(vm):
    """Error callback fires when extraction times out."""
    slow = MockClusterExtractor(delay_seconds=5.0)
    vm.setClusterExtractor(slow)
    vm.addRoi(0, 0, 5, 5)
    vm._config.set("gui:raw_analysis:clustering_timeout_seconds", 0.1)

    error_fired = threading.Event()
    vm.add_clustering_error_callback(lambda: error_fired.set())

    vm.triggerClustering()
    assert error_fired.wait(timeout=2.0), "Error callback not fired"
    assert vm.clusteringState == ClusteringState.IDLE
    assert vm.clusteringError is not None
    assert "timed out" in vm.clusteringError.lower()


def test_timeout_cancels_extractor(vm):
    """Timeout calls cancel() on the extractor."""
    slow = MockClusterExtractor(delay_seconds=5.0)
    vm.setClusterExtractor(slow)
    vm.addRoi(0, 0, 5, 5)
    vm._config.set("gui:raw_analysis:clustering_timeout_seconds", 0.1)

    done = threading.Event()
    vm.add_clustering_error_callback(lambda: done.set())

    vm.triggerClustering()
    done.wait(timeout=2.0)
    assert slow._cancelled is True


def test_successful_completion_cancels_timer(vm):
    """Successful extraction cancels the timeout timer."""
    _setup_for_clustering(vm)
    vm._config.set("gui:raw_analysis:clustering_timeout_seconds", 60)

    done = threading.Event()
    vm.add_clustering_completed_callback(lambda: done.set())

    vm.triggerClustering()
    assert done.wait(timeout=2.0), "Completion callback not fired"
    assert vm._clustering_timeout_timer is None
    assert vm.clusteringError is None


def test_clustering_error_cleared_on_new_trigger(vm):
    """A new triggerClustering clears any previous error."""
    _setup_for_clustering(vm)
    vm._clusteringError = "previous error"

    done = threading.Event()
    vm.add_clustering_completed_callback(lambda: done.set())
    vm.triggerClustering()
    done.wait(timeout=2.0)
    assert vm.clusteringError is None


# --- Progress tracking ---


def test_trigger_resets_progress(vm):
    """triggerClustering resets clusteringProgress to 0.0."""
    _setup_for_clustering(vm)
    vm._clusteringProgress = 0.5
    vm.triggerClustering()
    assert vm.clusteringProgress == 0.0


def test_progress_callback_fires(raw_holder):
    """Progress callback is registered and fires on extractor call."""
    from le_beta_vis.common.GeneralClusterExtractor import (
        GeneralClusterExtractor,
    )

    physics = MockPhysicsManager(factor=0.01, ped_width=100)
    config = MockConfigurationService()
    extractor = GeneralClusterExtractor(
        sigma_multiplier=4.0,
        physics_manager=physics,
    )

    data = np.zeros((20, 20), dtype=float)
    for i in range(5):
        data[10, 10 + i] = 500
    raw_holder[0] = data

    vm = ClusterAnalysisViewModel(config, physics, lambda: raw_holder[0])
    vm.addRoi(0, 0, 20, 20)
    vm.setClusterExtractor(extractor)

    progress_fired = threading.Event()
    vm.add_clustering_progress_callback(lambda: progress_fired.set())

    done = threading.Event()
    vm.add_clustering_completed_callback(lambda: done.set())
    vm.triggerClustering()
    done.wait(timeout=5.0)

    assert progress_fired.is_set()
    assert vm.clusteringProgress > 0.0


def test_progress_passes_callback_to_extractor(vm):
    """triggerClustering passes progress_callback to the extractor."""
    _setup_for_clustering(vm)

    extract_kwargs = {}
    original_extract = vm._clusterExtractor.extract

    def spy_extract(*args, **kwargs):
        extract_kwargs.update(kwargs)
        return original_extract(*args, **kwargs)

    vm._clusterExtractor.extract = spy_extract

    done = threading.Event()
    vm.add_clustering_completed_callback(lambda: done.set())
    vm.triggerClustering()
    done.wait(timeout=2.0)

    assert "progress_callback" in extract_kwargs
    assert extract_kwargs["progress_callback"] is not None
