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
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter


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


# -------------------------------------------------------------------
# query_clusters filtering
# -------------------------------------------------------------------

def test_query_clusters_none_returns_all():
    """query_clusters(None) should return the same as fetch_events."""
    repo = MockEventRepository()
    assert len(repo.query_clusters(None)) == len(repo.fetch_events())


def test_query_clusters_by_fits_id():
    """Filtering by fits_id should only return matching clusters."""
    repo = MockEventRepository()
    qf = ClusterQueryFilter(fits_id=1)
    results = repo.query_clusters(qf)
    assert len(results) > 0
    for c in results:
        assert c.fitsId == 1


def test_query_clusters_by_cluster_id():
    """Filtering by cluster_id should return exactly one cluster."""
    repo = MockEventRepository()
    qf = ClusterQueryFilter(cluster_id=1)
    results = repo.query_clusters(qf)
    assert len(results) == 1
    assert results[0].clusterId == 1


def test_query_clusters_by_min_energy():
    """Filtering by min_total_energy should exclude low-energy clusters."""
    repo = MockEventRepository()
    threshold = 5000.0
    qf = ClusterQueryFilter(min_total_energy=threshold)
    results = repo.query_clusters(qf)
    assert len(results) > 0
    for c in results:
        assert c.energy >= threshold


def test_query_clusters_by_min_pixels():
    """Filtering by min_total_pixels should exclude small clusters."""
    repo = MockEventRepository()
    qf = ClusterQueryFilter(min_total_pixels=50)
    results = repo.query_clusters(qf)
    assert len(results) > 0
    for c in results:
        assert c.pixelCount >= 50


def test_query_clusters_multiple_filters():
    """Multiple filters should be AND-combined."""
    repo = MockEventRepository()
    qf = ClusterQueryFilter(fits_id=1, min_total_energy=2000.0)
    results = repo.query_clusters(qf)
    for c in results:
        assert c.fitsId == 1
        assert c.energy >= 2000.0


def test_query_clusters_no_match_returns_empty():
    """A filter that matches nothing should return an empty list."""
    repo = MockEventRepository()
    qf = ClusterQueryFilter(cluster_id=9999)
    assert repo.query_clusters(qf) == []
