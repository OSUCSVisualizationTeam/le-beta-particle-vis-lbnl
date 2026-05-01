"""Tests for ClusterAnalysisViewModel.

Verifies state initialization, property defaults, ROI integration,
clustering integration, and callback forwarding.

Pure Python tests — no QApplication instantiation.
"""
from unittest.mock import MagicMock

import numpy as np
import pytest

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.ClusterAnalysisViewModel import (
    ClusterAnalysisViewModel,
    ClusteringState,
)
from le_beta_vis.frontend.fitsconverters import Colormap

_DEFAULT_RAW = np.arange(100, dtype=float).reshape(10, 10)


@pytest.fixture
def config():
    return MockConfigurationService()


@pytest.fixture
def physics(config):
    return PhysicsConversionManagerImpl(config)


@pytest.fixture
def vm(config, physics):
    return ClusterAnalysisViewModel(
        config, physics, lambda: _DEFAULT_RAW.copy()
    )


@pytest.fixture
def vm_no_data(config, physics):
    return ClusterAnalysisViewModel(config, physics, lambda: None)


# --- Initial state ---


def test_initial_clustering_state(vm):
    """State starts IDLE."""
    assert vm.clusteringState == ClusteringState.IDLE


def test_initial_selected_cluster_index(vm):
    """Selected cluster starts at -1."""
    assert vm.selectedClusterIndex == -1


def test_initial_clustering_results_empty(vm):
    """No results until extraction runs."""
    assert vm.clusteringResults == []


def test_initial_clustering_error_none(vm):
    """No error on construction."""
    assert vm.clusteringError is None


def test_initial_clustering_progress_zero(vm):
    """Progress starts at 0.0."""
    assert vm.clusteringProgress == 0.0


def test_initial_rois_empty(vm):
    """ROI list starts empty."""
    assert vm.rois == []


# --- Config-driven properties ---


def test_clustering_threshold_default(vm):
    """Default threshold is 4.0 σ."""
    assert vm.clusteringThreshold == 4.0


def test_display_energy_in_kev_default(vm):
    """displayEnergyInKev defaults to True."""
    assert vm.displayEnergyInKev is True


def test_kev_conversion_from_physics(vm, physics):
    """kevConversion reads from physics manager."""
    assert vm.kevConversion == physics.kev_conversion_factor


def test_box_select_color_default(vm):
    """boxSelectColor returns the default config value."""
    assert vm.boxSelectColor == "#00BFFF"


def test_box_select_border_width_default(vm):
    """boxSelectBorderWidth returns the default config value."""
    assert vm.boxSelectBorderWidth == 2


def test_cluster_thumbnail_colormap_no_provider(vm):
    """Returns None when no colormap_provider is wired."""
    assert vm.clusterThumbnailColormap is None


def test_cluster_thumbnail_colormap_with_provider(config, physics):
    """Returns colormap when provider is wired and config enabled."""
    vm = ClusterAnalysisViewModel(
        config, physics,
        lambda: None,
        colormap_provider=lambda: Colormap.VIRIDIS,
    )
    assert vm.clusterThumbnailColormap == Colormap.VIRIDIS


def test_cluster_thumbnail_colormap_disabled(config, physics):
    """Returns None when feature is disabled in config."""
    config.set("gui:raw_analysis:cluster_thumbnail_use_colormap", False)
    vm = ClusterAnalysisViewModel(
        config, physics,
        lambda: None,
        colormap_provider=lambda: Colormap.VIRIDIS,
    )
    assert vm.clusterThumbnailColormap is None


# --- isClusteringAvailable ---


def test_clustering_available_all_conditions(vm):
    """True when extractor, ROI, idle state, and data are present."""
    vm.setClusterExtractor(MockClusterExtractor(delay_seconds=0.0))
    vm.addRoi(0, 0, 5, 5)
    assert vm.isClusteringAvailable is True


def test_clustering_unavailable_no_extractor(vm):
    """False without an extractor."""
    vm.addRoi(0, 0, 5, 5)
    assert vm.isClusteringAvailable is False


def test_clustering_unavailable_no_roi(vm):
    """False without an ROI."""
    vm.setClusterExtractor(MockClusterExtractor(delay_seconds=0.0))
    assert vm.isClusteringAvailable is False


def test_clustering_unavailable_no_data(vm_no_data):
    """False when no raw data is available."""
    vm_no_data.setClusterExtractor(MockClusterExtractor(delay_seconds=0.0))
    vm_no_data.addRoi(0, 0, 5, 5)
    assert vm_no_data.isClusteringAvailable is False


# --- selectedRoiRawData / selectedRoiBoundingBox ---


def test_selected_roi_raw_data_no_roi(vm):
    """None when no ROI exists."""
    assert vm.selectedRoiRawData is None


def test_selected_roi_raw_data_with_roi(vm):
    """Crops data to ROI bounding box."""
    vm.addRoi(0, 0, 5, 5)
    result = vm.selectedRoiRawData
    assert result is not None
    assert result.shape == (5, 5)


def test_selected_roi_raw_data_no_raw_data(vm_no_data):
    """None when raw data callable returns None."""
    vm_no_data.addRoi(0, 0, 5, 5)
    assert vm_no_data.selectedRoiRawData is None


def test_selected_roi_bounding_box_no_roi(vm):
    """None when no ROI exists."""
    assert vm.selectedRoiBoundingBox is None


def test_selected_roi_bounding_box_with_roi(vm):
    """Returns the correct bounding box after addRoi."""
    from le_beta_vis.common.BoundingBox import BoundingBox
    vm.addRoi(2, 3, 8, 9)
    bbox = vm.selectedRoiBoundingBox
    assert bbox == BoundingBox(2, 3, 8, 9)


# --- Callback forwarding ---


def test_roi_changed_callback_on_add(vm):
    """add_roi_changed_callback fires when ROI is added."""
    called = []
    vm.add_roi_changed_callback(lambda: called.append(True))
    vm.addRoi(0, 0, 5, 5)
    assert called


def test_box_selection_completed_callback_on_add(vm):
    """add_box_selection_completed_callback fires when ROI is added."""
    called = []
    vm.add_box_selection_completed_callback(lambda: called.append(True))
    vm.addRoi(0, 0, 5, 5)
    assert called


def test_clustering_state_callback_fires(vm):
    """add_clustering_state_changed_callback fires on state change."""
    called = []
    vm.add_clustering_state_changed_callback(lambda: called.append(True))
    vm._notify_clustering_state_changed()
    assert called


def test_clustering_completed_callback_fires(vm):
    """add_clustering_completed_callback fires on completion."""
    called = []
    vm.add_clustering_completed_callback(lambda: called.append(True))
    vm._notify_clustering_completed()
    assert called


def test_clustering_error_callback_fires(vm):
    """add_clustering_error_callback fires on error."""
    called = []
    vm.add_clustering_error_callback(lambda: called.append(True))
    vm._notify_clustering_error()
    assert called


def test_clustering_progress_callback_fires(vm):
    """add_clustering_progress_callback fires on progress update."""
    called = []
    vm.add_clustering_progress_callback(lambda: called.append(True))
    vm._notify_clustering_progress()
    assert called


def test_selected_cluster_callback_fires(vm):
    """add_selected_cluster_changed_callback fires on selection change."""
    called = []
    vm.add_selected_cluster_changed_callback(lambda: called.append(True))
    vm._notify_selected_cluster_changed()
    assert called


def test_active_tool_callback_fires(vm):
    """add_active_tool_changed_callback fires when notified."""
    called = []
    vm.add_active_tool_changed_callback(lambda: called.append(True))
    vm._notify_active_tool_changed()
    assert called


# --- active_tool forwarding from RawDataViewModel ---


def test_rdvm_tool_change_reaches_cavm():
    """Tool-change from RDVM propagates to CAVM listeners."""
    from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
        RawDataViewModel,
    )
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    rdvm = RawDataViewModel(config, physics)
    rdvm._converter = MagicMock()

    called = []
    rdvm.clusterAnalysisViewModel.add_active_tool_changed_callback(
        lambda: called.append(True)
    )
    rdvm._notify_active_tool_changed()
    assert called
