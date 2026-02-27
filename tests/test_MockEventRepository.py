# Citation for Unit Tests: MockEventRepository formatting and mock data constraints
# Date: 26/02/2026
# Adapted from Claude Code:
# Write unit tests for MockEventRepository ensuring returned mock data meets data type, energy, and clustering constraints.

"""Tests for MockEventRepository.

Verifies that mock data is well-formed and exercises all
visual states needed by the Event Grid.
"""
from le_beta_vis.common.MockEventRepository import (
    MockEventRepository,
)
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.BoundingBox import BoundingBox


def test_returns_list_of_clusters():
    """fetch_events should return Cluster instances."""
    repo = MockEventRepository()
    events = repo.fetch_events()
    assert len(events) > 0
    for event in events:
        assert isinstance(event, Cluster)


def test_classification_fields_are_float():
    """Classification scores should be floats in [0, 1]."""
    repo = MockEventRepository()
    for event in repo.fetch_events():
        for score in (
            event.cnnClassification,
            event.nrgClassification,
            event.bdtClassification,
        ):
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0


def test_bounding_box_valid():
    """Every event should have a valid bounding box."""
    repo = MockEventRepository()
    for event in repo.fetch_events():
        bb = event.boundingBox
        assert isinstance(bb, BoundingBox)
        assert bb.right > bb.left
        assert bb.bottom > bb.top


def test_data_shape_matches_bbox():
    """Cluster data shape should match bounding box dimensions."""
    repo = MockEventRepository()
    for event in repo.fetch_events():
        bb = event.boundingBox
        expected_h = bb.bottom - bb.top
        expected_w = bb.right - bb.left
        assert event.data.shape == (expected_h, expected_w)


def test_energy_positive():
    """All events should have positive energy."""
    repo = MockEventRepository()
    for event in repo.fetch_events():
        assert event.energy > 0


def test_varied_confidence():
    """Mock data should include both high and low confidence."""
    repo = MockEventRepository()
    events = repo.fetch_events()
    scores = [
        max(e.cnnClassification, e.nrgClassification,
            e.bdtClassification)
        for e in events
    ]
    has_high = any(s >= 0.75 for s in scores)
    has_low = any(s < 0.75 for s in scores)
    assert has_high, "Need at least one high-confidence event"
    assert has_low, "Need at least one low-confidence event"


def test_fits_id_populated():
    """Every event should have a fitsId."""
    repo = MockEventRepository()
    for event in repo.fetch_events():
        assert event.fitsId is not None


def test_cluster_id_unique():
    """Cluster IDs should be unique."""
    repo = MockEventRepository()
    events = repo.fetch_events()
    ids = [e.clusterId for e in events]
    assert len(ids) == len(set(ids))
