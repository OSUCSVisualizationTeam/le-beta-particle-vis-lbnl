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


# --- formatDetailHtml: particle info ---


def test_html_contains_particle_symbol(vm, cluster):
    """HTML should include the particle type symbol."""
    html = vm.formatDetailHtml(cluster)
    # CNN=0.9 >= 0.75 → Tritium → symbol ³H
    assert "\u00b3H" in html


def test_html_contains_particle_name(vm, cluster):
    """HTML should include the particle display name."""
    html = vm.formatDetailHtml(cluster)
    assert "Tritium" in html


def test_html_unclassified_particle():
    """Low scores should yield Unclassified / '?' symbol."""
    vm = HistoricalEventInspectorViewModel(threshold=0.75)
    c = _make_cluster(cnn=0.1, nrg=0.2, bdt=0.1)
    html = vm.formatDetailHtml(c)
    assert "?" in html
    assert "Unknown" in html


# --- formatDetailHtml: confidence percentages ---


def test_html_contains_cnn_percentage(vm, cluster):
    """HTML should show CNN score as percentage."""
    html = vm.formatDetailHtml(cluster)
    assert "90.0%" in html


def test_html_contains_nrg_percentage(vm, cluster):
    """HTML should show NRG score as percentage."""
    html = vm.formatDetailHtml(cluster)
    assert "30.0%" in html


def test_html_contains_bdt_percentage(vm, cluster):
    """HTML should show BDT score as percentage."""
    html = vm.formatDetailHtml(cluster)
    assert "60.0%" in html


# --- formatDetailHtml: cluster ID ---


def test_html_contains_cluster_id(vm, cluster):
    """HTML should display the cluster ID."""
    html = vm.formatDetailHtml(cluster)
    assert "7" in html


def test_html_cluster_id_none(vm):
    """HTML should show N/A when clusterId is None."""
    c = _make_cluster(cluster_id=None)
    html = vm.formatDetailHtml(c)
    assert "N/A" in html


# --- formatDetailHtml: energy ---


def test_html_energy_kev(vm, cluster):
    """When displayKeV is True, energy shows keV + ADU."""
    html = vm.formatDetailHtml(cluster)
    assert "keV" in html
    assert "ADU" in html


def test_html_energy_adu_only():
    """When no physics manager, energy shows ADU only."""
    vm = HistoricalEventInspectorViewModel(physics=None, displayKeV=True)
    c = _make_cluster(energy=5000.0)
    html = vm.formatDetailHtml(c)
    assert "5000.00 ADU" in html
    assert "keV" not in html


def test_html_energy_adu_when_kev_disabled(physics):
    """When displayKeV is False, energy shows ADU even with physics."""
    vm = HistoricalEventInspectorViewModel(physics=physics, displayKeV=False)
    c = _make_cluster(energy=5000.0)
    html = vm.formatDetailHtml(c)
    assert "ADU" in html
    assert "keV" not in html


# --- formatDetailHtml: geometry ---


def test_html_geometry(vm, cluster):
    """HTML should show W×H from bounding box."""
    html = vm.formatDetailHtml(cluster)
    # bb: left=20, right=32 → w=12; top=10, bottom=20 → h=10
    assert "12\u00d710" in html


# --- formatDetailHtml: center ---


def test_html_center_relative(vm, cluster):
    """Center should be relative to bounding box origin."""
    html = vm.formatDetailHtml(cluster)
    # centerX=26 - left=20 = 6; centerY=15 - top=10 = 5
    assert "(6, 5)" in html


# --- formatDetailHtml: sigma ---


def test_html_sigma_values(vm, cluster):
    """HTML should include sigma X and Y values."""
    html = vm.formatDetailHtml(cluster)
    assert "1.50" in html
    assert "2.00" in html


# --- formatDetailHtml: pixels ---


def test_html_pixel_count(vm, cluster):
    """HTML should include the pixel count."""
    html = vm.formatDetailHtml(cluster)
    assert "42" in html


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
