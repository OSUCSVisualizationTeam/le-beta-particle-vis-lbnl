"""Tests for multi-cluster selection on ClusterAnalysisViewModel."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.RawDataViewModel import RawDataViewModel
from mock_configuration_service import MockConfigurationService


@pytest.fixture
def rdvm():
    config = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics)
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
    vm._request_render = lambda: vm._render_worker_logic()
    return vm


@pytest.fixture
def cavm(rdvm):
    return rdvm.clusterAnalysisViewModel


def _make_cluster(cx: int = 5, cy: int = 5, energy: float = 100.0) -> ClusteredEventInfo:
    return ClusteredEventInfo(
        boundingBox=BoundingBox(0, 0, 10, 10),
        data=np.ones((3, 3), dtype=float),
        centerX=cx,
        centerY=cy,
        energy=energy,
        pixelCount=10,
    )


# --- selectClusters ---


def test_select_clusters_multiple_valid_indices(cavm):
    """selectClusters stores all valid indices."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster(), _make_cluster()]
    cavm.selectClusters([0, 2])
    assert cavm.selectedClusterIndices == [0, 2]


def test_select_clusters_filters_invalid_indices(cavm):
    """selectClusters silently drops out-of-range indices."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectClusters([0, 5])
    assert cavm.selectedClusterIndices == [0]


def test_select_clusters_empty_list_deselects(cavm):
    """selectClusters([]) clears the selection."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectClusters([0])
    cavm.selectClusters([])
    assert cavm.selectedClusterIndices == []


def test_select_clusters_no_double_fire_same_set(cavm):
    """selectClusters is a no-op and fires no callback when set is unchanged."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cavm.selectClusters([0, 1])
    cb = MagicMock()
    cavm.add_selected_cluster_changed_callback(cb)
    cavm.selectClusters([1, 0])
    cb.assert_not_called()


def test_select_clusters_fires_callback(cavm):
    """selectClusters fires selected_cluster_changed callback on change."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cb = MagicMock()
    cavm.add_selected_cluster_changed_callback(cb)
    cavm.selectClusters([0, 1])
    cb.assert_called_once()


def test_select_clusters_all_invalid_deselects(cavm):
    """selectClusters with only out-of-range indices clears selection."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectClusters([0])
    cb = MagicMock()
    cavm.add_selected_cluster_changed_callback(cb)
    cavm.selectClusters([99])
    assert cavm.selectedClusterIndices == []
    cb.assert_called_once()


# --- selectedClusters ---


def test_selected_clusters_returns_correct_infos(cavm):
    """selectedClusters returns the matching ClusteredEventInfo objects."""
    c0 = _make_cluster(cx=1)
    c1 = _make_cluster(cx=2)
    c2 = _make_cluster(cx=3)
    cavm._clusteringResults = [c0, c1, c2]
    cavm.selectClusters([0, 2])
    assert cavm.selectedClusters == [c0, c2]


def test_selected_clusters_empty_when_no_selection(cavm):
    """selectedClusters returns empty list with no selection."""
    cavm._clusteringResults = [_make_cluster()]
    assert cavm.selectedClusters == []


def test_selected_clusters_sorted_by_index(cavm):
    """selectedClusters returns objects in ascending index order."""
    c0 = _make_cluster(cx=1)
    c1 = _make_cluster(cx=2)
    cavm._clusteringResults = [c0, c1]
    cavm.selectClusters([1, 0])
    assert cavm.selectedClusters == [c0, c1]


# --- backward-compat: selectedClusterIndex / selectedCluster ---


def test_selected_cluster_index_compat_single(cavm):
    """selectedClusterIndex returns the index when exactly one is selected."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectClusters([0])
    assert cavm.selectedClusterIndex == 0


def test_selected_cluster_index_compat_multiple_returns_minus_one(cavm):
    """selectedClusterIndex returns -1 when multiple clusters are selected."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cavm.selectClusters([0, 1])
    assert cavm.selectedClusterIndex == -1


def test_selected_cluster_index_compat_empty_returns_minus_one(cavm):
    """selectedClusterIndex returns -1 when nothing is selected."""
    assert cavm.selectedClusterIndex == -1


def test_selected_cluster_compat_single(cavm):
    """selectedCluster returns the cluster when exactly one is selected."""
    c0 = _make_cluster(cx=7)
    cavm._clusteringResults = [c0]
    cavm.selectClusters([0])
    assert cavm.selectedCluster is c0


def test_selected_cluster_compat_multiple_returns_none(cavm):
    """selectedCluster returns None when multiple clusters are selected."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cavm.selectClusters([0, 1])
    assert cavm.selectedCluster is None


# --- clearClusteringResults ---


def test_clear_results_resets_multi_selection(cavm):
    """clearClusteringResults resets a multi-cluster selection."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cavm.selectClusters([0, 1])
    cavm.clearClusteringResults()
    assert cavm.selectedClusterIndices == []


# --- classify ---


def test_classify_selected_cluster_multi_no_error(cavm):
    """classifySelectedCluster runs without error for multiple selected clusters."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cavm.selectClusters([0, 1])
    cavm.classifySelectedCluster()


def test_classify_no_selection_no_error(cavm):
    """classifySelectedCluster is a no-op when nothing is selected."""
    cavm.classifySelectedCluster()


# --- export ---


def test_export_single_calls_handler_with_list(cavm):
    """exportSelectedCluster calls handler with a single-element list."""
    c0 = _make_cluster()
    cavm._clusteringResults = [c0]
    handler = MagicMock()
    cavm.setExportHandler(handler)
    cavm.selectClusters([0])
    cavm.exportSelectedCluster()
    handler.assert_called_once_with([c0])


def test_export_multiple_calls_handler_with_list(cavm):
    """exportSelectedCluster calls handler with all selected clusters."""
    c0 = _make_cluster(cx=1)
    c1 = _make_cluster(cx=2)
    cavm._clusteringResults = [c0, c1]
    handler = MagicMock()
    cavm.setExportHandler(handler)
    cavm.selectClusters([0, 1])
    cavm.exportSelectedCluster()
    handler.assert_called_once_with([c0, c1])


def test_export_empty_no_op(cavm):
    """exportSelectedCluster is a no-op when nothing is selected."""
    handler = MagicMock()
    cavm.setExportHandler(handler)
    cavm.exportSelectedCluster()
    handler.assert_not_called()


def test_export_no_handler_no_error(cavm):
    """exportSelectedCluster is safe when no handler is injected."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectClusters([0])
    cavm.exportSelectedCluster()
