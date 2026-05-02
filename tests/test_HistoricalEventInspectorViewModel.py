# Citation for Unit Tests: HistoricalEventInspectorViewModel formatting, properties, and observer logic
# Date: 26/02/2026
# Adapted from Claude Code:
# Write comprehensive pure Python unit tests for HistoricalEventInspectorViewModel
# covering formatting, physics conversion, and observer notifications.

"""Tests for HistoricalEventInspectorViewModel.

Pure Python tests — no QApplication instantiation.
"""
import pytest
from unittest.mock import MagicMock

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    ClusterDisplayData,
    HistoricalEventInspectorViewModel,
    _score_css,
)


def _make_cluster(
    cnn: float = 0.9,
    nrg: float = 0.3,
    bdt: float = 0.6,
    energy: float = 5000.0,
    sigma_x: float = 1.5,
    sigma_y: float = 2.0,
    pixel_count: int = 42,
    cluster_id: int = 7,
) -> Cluster:
    """Creates a deterministic Cluster for testing."""
    bb = BoundingBox(top=10, left=20, bottom=20, right=32)
    data = np.ones((10, 12), dtype=float) * 100.0
    return Cluster(
        boundingBox=bb,
        data=data,
        centerX=26,
        centerY=15,
        sigmaX=sigma_x,
        sigmaY=sigma_y,
        energy=energy,
        pixelCount=pixel_count,
        clusterId=cluster_id,
        cnnClassification=cnn,
        nrgClassification=nrg,
        bdtClassification=bdt,
    )


def _make_physics_mock(factor: float = 1.02857e-5):
    mock = MagicMock()
    mock.kev_conversion_factor = factor
    mock.adu_to_kev.side_effect = lambda v: v * factor
    return mock


@pytest.fixture
def physics():
    return _make_physics_mock()


@pytest.fixture
def vm(physics):
    return HistoricalEventInspectorViewModel(
        physics=physics,
        threshold=0.75,
        displayKeV=True,
    )


@pytest.fixture
def cluster():
    return _make_cluster()


# --- _score_css ---


def test_score_css_green_at_threshold():
    """Score exactly at threshold should be green."""
    css = _score_css(0.75, 0.75)
    assert "#27ae60" in css


def test_score_css_green_above_threshold():
    """Score above threshold should be green."""
    css = _score_css(0.9, 0.75)
    assert "#27ae60" in css


def test_score_css_yellow_above_half():
    """Score >= 0.5 but below threshold should be yellow."""
    css = _score_css(0.6, 0.75)
    assert "#f39c12" in css


def test_score_css_gray_below_half():
    """Score below 0.5 should be gray."""
    css = _score_css(0.3, 0.75)
    assert "#7f8c8d" in css


# --- formatClusterData: returns ClusterDisplayData ---


def test_format_cluster_data_returns_dataclass(vm, cluster):
    """formatClusterData should return a ClusterDisplayData instance."""
    data = vm.formatClusterData(cluster)
    assert isinstance(data, ClusterDisplayData)


# --- formatClusterData: particle info ---


def test_data_contains_particle_symbol(vm, cluster):
    """Data should include the particle type symbol."""
    data = vm.formatClusterData(cluster)
    # CNN=0.9 >= 0.75 → Tritium → symbol ³H
    assert "\u00b3H" in data.particle_symbol


def test_data_contains_particle_name(vm, cluster):
    """Data should include the particle display name."""
    data = vm.formatClusterData(cluster)
    assert "Tritium" in data.particle_name


def test_data_unclassified_particle():
    """Low scores should yield Unclassified / '?' symbol."""
    vm = HistoricalEventInspectorViewModel(threshold=0.75)
    c = _make_cluster(cnn=0.1, nrg=0.2, bdt=0.1)
    data = vm.formatClusterData(c)
    assert "?" in data.particle_symbol
    assert "Unknown" in data.particle_name


# --- formatClusterData: confidence percentages ---


def test_data_contains_cnn_percentage(vm, cluster):
    """Data should show CNN score as percentage."""
    data = vm.formatClusterData(cluster)
    assert data.cnn_pct == "90.0%"


def test_data_contains_nrg_percentage(vm, cluster):
    """Data should show NRG score as percentage."""
    data = vm.formatClusterData(cluster)
    assert data.nrg_pct == "30.0%"


def test_data_contains_bdt_percentage(vm, cluster):
    """Data should show BDT score as percentage."""
    data = vm.formatClusterData(cluster)
    assert data.bdt_pct == "60.0%"


# --- formatClusterData: cluster ID ---


def test_data_contains_cluster_id(vm, cluster):
    """Data should display the cluster ID."""
    data = vm.formatClusterData(cluster)
    assert data.cluster_id == "7"


def test_data_cluster_id_none(vm):
    """Data should show N/A when clusterId is None."""
    c = _make_cluster(cluster_id=None)
    data = vm.formatClusterData(c)
    assert data.cluster_id == "N/A"


# --- formatClusterData: energy ---


def test_data_energy_kev(vm, cluster):
    """When displayKeV is True, energy shows keV + ADU."""
    data = vm.formatClusterData(cluster)
    assert "keV" in data.energy
    assert "ADU" in data.energy


def test_data_energy_adu_only():
    """When no physics manager, energy shows ADU only."""
    vm = HistoricalEventInspectorViewModel(physics=None, displayKeV=True)
    c = _make_cluster(energy=5000.0)
    data = vm.formatClusterData(c)
    assert data.energy == "5000.00 ADU"
    assert "keV" not in data.energy


def test_data_energy_adu_when_kev_disabled(physics):
    """When displayKeV is False, energy shows ADU even with physics."""
    vm = HistoricalEventInspectorViewModel(physics=physics, displayKeV=False)
    c = _make_cluster(energy=5000.0)
    data = vm.formatClusterData(c)
    assert "ADU" in data.energy
    assert "keV" not in data.energy


# --- formatClusterData: geometry ---


def test_data_geometry(vm, cluster):
    """Data should show W×H from bounding box."""
    data = vm.formatClusterData(cluster)
    # bb: left=20, right=32 → w=12; top=10, bottom=20 → h=10
    assert data.geometry == "12\u00d710"


# --- formatClusterData: center ---


def test_data_center_relative(vm, cluster):
    """Center should be relative to bounding box origin."""
    data = vm.formatClusterData(cluster)
    # centerX=26 - left=20 = 6; centerY=15 - top=10 = 5
    assert data.center == "(6, 5)"


# --- formatClusterData: sigma ---


def test_data_sigma_values(vm, cluster):
    """Data should include sigma X and Y values."""
    data = vm.formatClusterData(cluster)
    assert data.sigma_x == 1.5
    assert data.sigma_y == 2.0


# --- formatClusterData: pixels ---


def test_data_pixel_count(vm, cluster):
    """Data should include the pixel count."""
    data = vm.formatClusterData(cluster)
    assert data.pixels == 42


# --- formatHistogramXLabel ---


def test_histogram_label_kev(vm, cluster):
    """With physics + keV enabled, label should be keV."""
    label = vm.formatHistogramXLabel(cluster)
    assert label == "Energy (keV)"


def test_histogram_label_adu_no_physics(cluster):
    """Without physics manager, label should be ADU."""
    vm = HistoricalEventInspectorViewModel(physics=None)
    label = vm.formatHistogramXLabel(cluster)
    assert label == "Energy (ADU)"


def test_histogram_label_adu_disabled(physics, cluster):
    """With keV disabled, label should be ADU."""
    vm = HistoricalEventInspectorViewModel(physics=physics, displayKeV=False)
    label = vm.formatHistogramXLabel(cluster)
    assert label == "Energy (ADU)"


# --- Observer pattern ---


def test_set_event_fires_callback(vm, cluster):
    """setEvent should notify observers with the cluster."""
    received = []
    vm.add_event_changed_callback(lambda c: received.append(c))
    vm.setEvent(cluster)
    assert len(received) == 1
    assert received[0] is cluster


def test_set_event_none_fires_callback(vm, cluster):
    """setEvent(None) should notify observers with None."""
    vm.setEvent(cluster)
    received = []
    vm.add_event_changed_callback(lambda c: received.append(c))
    vm.setEvent(None)
    assert received == [None]


# --- Properties and setters ---


def test_initial_cluster_is_none(vm):
    """Cluster should be None before setEvent."""
    assert vm.cluster is None


def test_set_event_updates_cluster(vm, cluster):
    """setEvent should update the cluster property."""
    vm.setEvent(cluster)
    assert vm.cluster is cluster


def test_threshold_property(vm):
    """threshold should reflect constructor value."""
    assert vm.threshold == 0.75


def test_set_threshold(vm):
    """setThreshold should update the threshold."""
    vm.setThreshold(0.5)
    assert vm.threshold == 0.5


def test_display_kev_property(vm):
    """displayKeV should reflect constructor value."""
    assert vm.displayKeV is True


def test_set_display_kev(vm):
    """setDisplayKeV should update the flag."""
    vm.setDisplayKeV(False)
    assert vm.displayKeV is False


def test_physics_property(vm, physics):
    """physics property should return injected manager."""
    assert vm.physics is physics


# --- openInRawData handler ---


def test_open_in_raw_data_invokes_handler_with_cluster(vm, cluster):
    """openInRawData should invoke the registered handler with the current cluster."""
    handler = MagicMock()
    vm.setOpenInRawDataHandler(handler)
    vm.setEvent(cluster)
    vm.openInRawData()
    handler.assert_called_once_with(cluster)


def test_open_in_raw_data_no_op_without_handler(vm, cluster):
    """openInRawData should silently no-op when no handler is wired."""
    vm.setEvent(cluster)
    vm.openInRawData()  # must not raise


def test_open_in_raw_data_no_op_without_cluster(vm):
    """openInRawData should not call the handler when no cluster is set."""
    handler = MagicMock()
    vm.setOpenInRawDataHandler(handler)
    vm.openInRawData()
    handler.assert_not_called()


def test_can_open_in_raw_data_false_when_no_cluster(vm):
    assert vm.canOpenInRawData is False


def test_can_open_in_raw_data_false_when_no_filename(vm, cluster):
    cluster.fitsFilename = None
    vm.setEvent(cluster)
    assert vm.canOpenInRawData is False


def test_can_open_in_raw_data_true_with_filename(vm, cluster):
    cluster.fitsFilename = "/data/run42.fits"
    vm.setEvent(cluster)
    assert vm.canOpenInRawData is True


def test_clear_handler_via_none(vm, cluster):
    handler = MagicMock()
    vm.setOpenInRawDataHandler(handler)
    vm.setOpenInRawDataHandler(None)
    vm.setEvent(cluster)
    vm.openInRawData()
    handler.assert_not_called()
