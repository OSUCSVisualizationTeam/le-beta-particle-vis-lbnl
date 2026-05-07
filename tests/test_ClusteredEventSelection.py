"""Tests for cluster selection state, result management,
and thumbnail config properties on ClusterAnalysisViewModel."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.RawDataViewModel import RawDataViewModel


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


def _setup_for_clustering(rdvm: RawDataViewModel) -> None:
    """Load mock data into RDVM and configure CAVM for clustering."""
    mock_capture = MagicMock()
    mock_capture.rawData.return_value = (
        np.arange(100, dtype=float).reshape(10, 10)
    )
    mock_capture.info.return_value = MagicMock(
        rows=10, cols=10, min=0, max=99
    )
    rdvm._captures = [mock_capture]
    rdvm._activeIndex = 0
    rdvm._image_bounds = (10, 10)

    cavm = rdvm.clusterAnalysisViewModel
    cavm.setClusterExtractor(MockClusterExtractor(delay_seconds=0.01))
    cavm.addRoi(0, 0, 5, 5)


def _make_cluster(
    cx: int = 5,
    cy: int = 5,
    energy: float = 100.0,
    pixels: int = 10,
) -> ClusteredEventInfo:
    """Create a minimal ClusteredEventInfo for testing."""
    return ClusteredEventInfo(
        boundingBox=BoundingBox(0, 0, 10, 10),
        data=np.ones((3, 3), dtype=float),
        centerX=cx,
        centerY=cy,
        energy=energy,
        pixelCount=pixels,
    )


# --- Initial state ---


def test_initial_selection_is_negative_one(cavm):
    """selectedClusterIndex starts at -1."""
    assert cavm.selectedClusterIndex == -1


def test_selected_cluster_returns_none_when_empty(cavm):
    """selectedCluster returns None when no results exist."""
    assert cavm.selectedCluster is None


# --- selectCluster ---


def test_select_cluster_valid_index(cavm):
    """selectCluster with a valid index updates selectedClusterIndex."""
    cavm._clusteringResults = [_make_cluster(), _make_cluster()]
    cavm.selectCluster(1)
    assert cavm.selectedClusterIndex == 1


def test_select_cluster_fires_callback(cavm):
    """selectCluster fires selected_cluster_changed callback."""
    cavm._clusteringResults = [_make_cluster()]
    cb = MagicMock()
    cavm.add_selected_cluster_changed_callback(cb)
    cavm.selectCluster(0)
    cb.assert_called_once()


def test_select_cluster_no_double_fire(cavm):
    """selectCluster with same index does not fire callback."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(0)
    cb = MagicMock()
    cavm.add_selected_cluster_changed_callback(cb)
    cavm.selectCluster(0)
    cb.assert_not_called()


def test_select_cluster_invalid_index_ignored(cavm):
    """selectCluster with out-of-range index is a no-op."""
    cavm._clusteringResults = [_make_cluster()]
    cb = MagicMock()
    cavm.add_selected_cluster_changed_callback(cb)
    cavm.selectCluster(5)
    assert cavm.selectedClusterIndex == -1
    cb.assert_not_called()


def test_select_cluster_negative_below_minus_one_ignored(cavm):
    """selectCluster with index < -1 is a no-op."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(-2)
    assert cavm.selectedClusterIndex == -1


def test_select_cluster_deselect(cavm):
    """selectCluster(-1) deselects."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(0)
    cavm.selectCluster(-1)
    assert cavm.selectedClusterIndex == -1


# --- selectedCluster property ---


def test_selected_cluster_returns_correct_info(cavm):
    """selectedCluster returns the correct ClusteredEventInfo."""
    c1 = _make_cluster(cx=1, cy=2, energy=50.0)
    c2 = _make_cluster(cx=3, cy=4, energy=200.0)
    cavm._clusteringResults = [c1, c2]
    cavm.selectCluster(1)
    assert cavm.selectedCluster is c2


# --- clearClusteringResults ---


def test_clear_clustering_results(cavm):
    """clearClusteringResults empties results and resets selection."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(0)
    cavm.clearClusteringResults()
    assert cavm.clusteringResults == []
    assert cavm.selectedClusterIndex == -1


def test_clear_clustering_results_fires_callbacks(cavm):
    """clearClusteringResults fires completed and selection callbacks."""
    cavm._clusteringResults = [_make_cluster()]
    completed_cb = MagicMock()
    selection_cb = MagicMock()
    cavm.add_clustering_completed_callback(completed_cb)
    cavm.add_selected_cluster_changed_callback(selection_cb)

    cavm.clearClusteringResults()
    completed_cb.assert_called_once()
    selection_cb.assert_called_once()


def test_clear_clustering_noop_when_already_empty(cavm):
    """clearClusteringResults is a no-op when already empty."""
    cb = MagicMock()
    cavm.add_clustering_completed_callback(cb)
    cavm.clearClusteringResults()
    cb.assert_not_called()


# --- clearRois clears clustering ---


def test_clear_rois_clears_clustering_results(rdvm, cavm):
    """clearRois also clears clustering results."""
    _setup_for_clustering(rdvm)
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(0)
    cavm.clearRois()
    assert cavm.clusteringResults == []
    assert cavm.selectedClusterIndex == -1


# --- triggerClustering clears previous results ---


def test_trigger_clustering_clears_previous_results(rdvm, cavm):
    """New triggerClustering clears old results and selection."""
    _setup_for_clustering(rdvm)
    cavm._clusteringResults = [_make_cluster()]
    cavm._selectedClusterIndices = frozenset([0])

    cavm.triggerClustering()
    assert cavm._clusteringResults == []
    assert cavm.selectedClusterIndices == []

    cavm.cancelClustering()


# --- Placeholder methods ---


def test_classify_selected_cluster_no_error(cavm):
    """classifySelectedCluster runs without error when cluster selected."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(0)
    cavm.classifySelectedCluster()


def test_classify_no_selection_no_error(cavm):
    """classifySelectedCluster is safe when nothing selected."""
    cavm.classifySelectedCluster()


def test_export_selected_cluster_no_error(cavm):
    """exportSelectedCluster runs without error when cluster selected."""
    cavm._clusteringResults = [_make_cluster()]
    cavm.selectCluster(0)
    cavm.exportSelectedCluster()


def test_export_no_selection_no_error(cavm):
    """exportSelectedCluster is safe when nothing selected."""
    cavm.exportSelectedCluster()


# --- Cluster display properties ---


def test_cluster_thumbnail_colormap_enabled_by_default(cavm):
    """clusterThumbnailColormap returns colormap with default config."""
    assert cavm.clusterThumbnailColormap is not None


def test_cluster_thumbnail_colormap_enabled(rdvm, cavm):
    """clusterThumbnailColormap returns active colormap when enabled."""
    rdvm._config.set(
        "gui:raw_analysis:cluster_thumbnail_use_colormap", True
    )
    result = cavm.clusterThumbnailColormap
    assert result is not None
    assert result.value == "viridis"


def test_display_energy_in_kev_default_true(cavm):
    """displayEnergyInKev defaults to True."""
    assert cavm.displayEnergyInKev is True


def test_display_energy_in_kev_disabled(rdvm, cavm):
    """displayEnergyInKev returns False when config is set."""
    rdvm._config.set("gui:raw_analysis:display_energy_in_kev", False)
    assert cavm.displayEnergyInKev is False


def test_kev_conversion_from_config(cavm):
    """kevConversion reads from physics manager."""
    assert cavm.kevConversion == pytest.approx(1.02857e-5)
