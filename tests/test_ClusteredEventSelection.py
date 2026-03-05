# Citation for Unit Tests: Verifies RawDataViewModel cluster selection logic, results management,
# and clustering tool state.
# Date: 28/02/2026
# Adapted from Claude Code:
# Write headless PyTest unit tests for RawDataViewModel covering cluster selection state changes,
# clearing results on ROI clearing, and cluster thumbnail configuration without Qt dependencies.

from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl
from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
    ActiveTool,
    RawDataViewModel,
)


@pytest.fixture
def view_model():
    config = MockConfigurationService()
    physics_manager = PhysicsConversionManagerImpl(config)
    vm = RawDataViewModel(config, physics_manager)
    vm._converter = MagicMock()
    vm._converter.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)

    def mock_request():
        vm._render_worker_logic()

    vm._request_render = mock_request
    return vm


def _setup_for_clustering(vm):
    """Helper: load mock data, set tool, add ROI, set extractor."""
    mock_capture = MagicMock()
    mock_capture.rawData.return_value = np.arange(100, dtype=float).reshape(10, 10)
    mock_capture.info.return_value = MagicMock(rows=10, cols=10, min=0, max=99)
    vm._captures = [mock_capture]
    vm._activeIndex = 0
    vm._image_bounds = (10, 10)

    vm.setClusterExtractor(MockClusterExtractor(delay_seconds=0.01))
    vm.setActiveTool(ActiveTool.BOX_SELECT)
    vm.addRoi(0, 0, 5, 5)


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


def test_initial_selection_is_negative_one(view_model):
    """selectedClusterIndex starts at -1."""
    assert view_model.selectedClusterIndex == -1


def test_selected_cluster_returns_none_when_empty(view_model):
    """selectedCluster returns None when no results exist."""
    assert view_model.selectedCluster is None


# --- selectCluster ---


def test_select_cluster_valid_index(view_model):
    """selectCluster with a valid index updates selectedClusterIndex."""
    view_model._clusteringResults = [_make_cluster(), _make_cluster()]
    view_model.selectCluster(1)
    assert view_model.selectedClusterIndex == 1


def test_select_cluster_fires_callback(view_model):
    """selectCluster fires selected_cluster_changed callback."""
    view_model._clusteringResults = [_make_cluster()]
    cb = MagicMock()
    view_model.add_selected_cluster_changed_callback(cb)
    view_model.selectCluster(0)
    cb.assert_called_once()


def test_select_cluster_no_double_fire(view_model):
    """selectCluster with same index does not fire callback."""
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(0)
    cb = MagicMock()
    view_model.add_selected_cluster_changed_callback(cb)
    view_model.selectCluster(0)
    cb.assert_not_called()


def test_select_cluster_invalid_index_ignored(view_model):
    """selectCluster with out-of-range index is a no-op."""
    view_model._clusteringResults = [_make_cluster()]
    cb = MagicMock()
    view_model.add_selected_cluster_changed_callback(cb)
    view_model.selectCluster(5)
    assert view_model.selectedClusterIndex == -1
    cb.assert_not_called()


def test_select_cluster_negative_below_minus_one_ignored(view_model):
    """selectCluster with index < -1 is a no-op."""
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(-2)
    assert view_model.selectedClusterIndex == -1


def test_select_cluster_deselect(view_model):
    """selectCluster(-1) deselects."""
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(0)
    view_model.selectCluster(-1)
    assert view_model.selectedClusterIndex == -1


# --- selectedCluster property ---


def test_selected_cluster_returns_correct_info(view_model):
    """selectedCluster returns the correct ClusteredEventInfo."""
    c1 = _make_cluster(cx=1, cy=2, energy=50.0)
    c2 = _make_cluster(cx=3, cy=4, energy=200.0)
    view_model._clusteringResults = [c1, c2]
    view_model.selectCluster(1)
    assert view_model.selectedCluster is c2


# --- clearClusteringResults ---


def test_clear_clustering_results(view_model):
    """clearClusteringResults empties results and resets selection."""
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(0)
    view_model.clearClusteringResults()
    assert view_model.clusteringResults == []
    assert view_model.selectedClusterIndex == -1


def test_clear_clustering_results_fires_callbacks(view_model):
    """clearClusteringResults fires completed and selection callbacks."""
    view_model._clusteringResults = [_make_cluster()]
    completed_cb = MagicMock()
    selection_cb = MagicMock()
    view_model.add_clustering_completed_callback(completed_cb)
    view_model.add_selected_cluster_changed_callback(selection_cb)

    view_model.clearClusteringResults()
    completed_cb.assert_called_once()
    selection_cb.assert_called_once()


def test_clear_clustering_noop_when_already_empty(view_model):
    """clearClusteringResults is a no-op when already empty."""
    cb = MagicMock()
    view_model.add_clustering_completed_callback(cb)
    view_model.clearClusteringResults()
    cb.assert_not_called()


# --- clearRois clears clustering ---


def test_clear_rois_clears_clustering_results(view_model):
    """clearRois also clears clustering results."""
    _setup_for_clustering(view_model)
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(0)
    view_model.clearRois()
    assert view_model.clusteringResults == []
    assert view_model.selectedClusterIndex == -1


# --- triggerClustering clears previous results ---


def test_trigger_clustering_clears_previous_results(view_model):
    """New triggerClustering clears old results and selection."""
    _setup_for_clustering(view_model)
    view_model._clusteringResults = [_make_cluster()]
    view_model._selectedClusterIndex = 0

    view_model.triggerClustering()
    assert view_model._clusteringResults == []
    assert view_model._selectedClusterIndex == -1

    # Clean up: cancel so the background thread doesn't fire
    view_model.cancelClustering()


# --- Placeholder methods ---


def test_classify_selected_cluster_no_error(view_model):
    """classifySelectedCluster runs without error when cluster selected."""
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(0)
    view_model.classifySelectedCluster()


def test_classify_no_selection_no_error(view_model):
    """classifySelectedCluster is safe when nothing selected."""
    view_model.classifySelectedCluster()


def test_export_selected_cluster_no_error(view_model):
    """exportSelectedCluster runs without error when cluster selected."""
    view_model._clusteringResults = [_make_cluster()]
    view_model.selectCluster(0)
    view_model.exportSelectedCluster()


def test_export_no_selection_no_error(view_model):
    """exportSelectedCluster is safe when nothing selected."""
    view_model.exportSelectedCluster()


# --- Cluster display properties ---


def test_cluster_thumbnail_colormap_enabled_by_default(view_model):
    """clusterThumbnailColormap returns active colormap with default config."""
    assert view_model.clusterThumbnailColormap is not None


def test_cluster_thumbnail_colormap_enabled(view_model):
    """clusterThumbnailColormap returns active colormap when enabled."""
    view_model._config.set("gui:raw_analysis:cluster_thumbnail_use_colormap", True)
    result = view_model.clusterThumbnailColormap
    assert result is not None
    assert result.value == "viridis"


def test_display_energy_in_kev_default_true(view_model):
    """displayEnergyInKev defaults to True."""
    assert view_model.displayEnergyInKev is True


def test_display_energy_in_kev_disabled(view_model):
    """displayEnergyInKev returns False when config is set."""
    view_model._config.set("gui:raw_analysis:display_energy_in_kev", False)
    assert view_model.displayEnergyInKev is False


def test_kev_conversion_from_config(view_model):
    """kevConversion reads from config."""
    assert view_model.kevConversion == pytest.approx(1.02857e-5)
