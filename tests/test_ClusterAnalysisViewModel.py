# Citation for Unit Tests: Verifies ClusterAnalysisViewModel delegation to parent RawDataViewModel.
# Date: 28/02/2026
# Adapted from Claude Code:
# Write headless PyTest unit tests for ClusterAnalysisViewModel verifying properties and callbacks
# are correctly forwarded to its parent RawDataViewModel.

"""Tests for ClusterAnalysisViewModel delegation.

Verifies that ClusterAnalysisViewModel correctly forwards
all properties, methods, and callback registrations to the
parent RawDataViewModel.

Pure Python tests — no QApplication instantiation.
"""
from unittest.mock import MagicMock

import pytest

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    RawDataViewModel,
)


@pytest.fixture
def parent_vm():
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics)
    vm._converter = MagicMock()
    vm._request_render = lambda: vm._render_worker_logic()
    return vm


@pytest.fixture
def facade(parent_vm):
    return parent_vm.clusterAnalysisViewModel


# --- Property delegation ---


def test_clustering_threshold(facade, parent_vm):
    """clusteringThreshold delegates to parent."""
    assert facade.clusteringThreshold == parent_vm.clusteringThreshold


def test_is_clustering_available(facade, parent_vm):
    """isClusteringAvailable delegates to parent."""
    assert facade.isClusteringAvailable == parent_vm.isClusteringAvailable


def test_clustering_state(facade, parent_vm):
    """clusteringState delegates to parent."""
    assert facade.clusteringState == parent_vm.clusteringState


def test_clustering_results(facade, parent_vm):
    """clusteringResults delegates to parent."""
    assert facade.clusteringResults == parent_vm.clusteringResults


def test_clustering_progress(facade, parent_vm):
    """clusteringProgress delegates to parent."""
    assert facade.clusteringProgress == parent_vm.clusteringProgress


def test_clustering_error(facade, parent_vm):
    """clusteringError delegates to parent."""
    assert facade.clusteringError == parent_vm.clusteringError


def test_cluster_thumbnail_colormap(facade, parent_vm):
    """clusterThumbnailColormap delegates to parent."""
    assert facade.clusterThumbnailColormap == parent_vm.clusterThumbnailColormap


def test_display_energy_in_kev(facade, parent_vm):
    """displayEnergyInKev delegates to parent."""
    assert facade.displayEnergyInKev == parent_vm.displayEnergyInKev


def test_kev_conversion(facade, parent_vm):
    """kevConversion delegates to parent."""
    assert facade.kevConversion == parent_vm.kevConversion


def test_selected_cluster_index(facade, parent_vm):
    """selectedClusterIndex delegates to parent."""
    assert facade.selectedClusterIndex == parent_vm.selectedClusterIndex


# --- Method delegation ---


def test_trigger_clustering(facade, parent_vm):
    """triggerClustering delegates to parent (no-op when unavailable)."""
    facade.triggerClustering()
    # No error — clustering not available so it's a safe no-op


def test_cancel_clustering(facade, parent_vm):
    """cancelClustering delegates to parent."""
    facade.cancelClustering()


def test_select_cluster(facade, parent_vm):
    """selectCluster delegates to parent."""
    facade.selectCluster(-1)
    assert parent_vm.selectedClusterIndex == -1


def test_classify_selected_cluster(facade):
    """classifySelectedCluster delegates without error."""
    facade.classifySelectedCluster()


def test_export_selected_cluster(facade):
    """exportSelectedCluster delegates without error."""
    facade.exportSelectedCluster()


# --- Callback delegation ---


def test_add_clustering_state_changed_callback(facade, parent_vm):
    """Callback registered via facade fires on parent state change."""
    called = []
    facade.add_clustering_state_changed_callback(lambda: called.append(True))
    parent_vm._notify_clustering_state_changed()
    assert called


def test_add_clustering_completed_callback(facade, parent_vm):
    """Callback registered via facade fires on parent completion."""
    called = []
    facade.add_clustering_completed_callback(lambda: called.append(True))
    parent_vm._notify_clustering_completed()
    assert called


def test_add_clustering_error_callback(facade, parent_vm):
    """Callback registered via facade fires on parent error."""
    called = []
    facade.add_clustering_error_callback(lambda: called.append(True))
    parent_vm._notify_clustering_error()
    assert called


def test_add_clustering_progress_callback(facade, parent_vm):
    """Callback registered via facade fires on parent progress."""
    called = []
    facade.add_clustering_progress_callback(lambda: called.append(True))
    parent_vm._notify_clustering_progress()
    assert called


def test_add_selected_cluster_changed_callback(facade, parent_vm):
    """Callback registered via facade fires on selection change."""
    called = []
    facade.add_selected_cluster_changed_callback(lambda: called.append(True))
    parent_vm._notify_selected_cluster_changed()
    assert called


def test_add_active_tool_changed_callback(facade, parent_vm):
    """Callback registered via facade fires on tool change."""
    called = []
    facade.add_active_tool_changed_callback(lambda: called.append(True))
    parent_vm._notify_active_tool_changed()
    assert called


def test_add_roi_changed_callback(facade, parent_vm):
    """Callback registered via facade fires on ROI change."""
    called = []
    facade.add_roi_changed_callback(lambda: called.append(True))
    parent_vm._notify_roi_changed()
    assert called
