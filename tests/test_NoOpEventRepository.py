"""Tests for NoOpEventRepository.

Verifies that all methods return safe defaults and emit warnings.
"""
import logging

from le_beta_vis.common.NoOpEventRepository import NoOpEventRepository
from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
)


def _make_repo() -> NoOpEventRepository:
    return NoOpEventRepository()


def test_fetch_events_returns_empty(caplog):
    repo = _make_repo()
    with caplog.at_level(logging.WARNING):
        result = repo.fetch_events()
    assert result == []
    assert "fetch_events" in caplog.text


def test_query_clusters_returns_empty(caplog):
    repo = _make_repo()
    qf = ClusterQueryFilter(fits_id=1)
    with caplog.at_level(logging.WARNING):
        result = repo.query_clusters(qf)
    assert result == []
    assert "query_clusters" in caplog.text


def test_query_clusters_none_filter(caplog):
    repo = _make_repo()
    with caplog.at_level(logging.WARNING):
        result = repo.query_clusters(None)
    assert result == []


def test_store_cluster_returns_none(caplog):
    repo = _make_repo()
    req = ClusterStoreRequest(
        data=[], hdu_id=0, bounding_box={},
        sigma_x=0.0, sigma_y=0.0,
        total_energy=0.0, total_pixels=0, fits_id=0,
    )
    with caplog.at_level(logging.WARNING):
        result = repo.store_cluster(req)
    assert result is None
    assert "store_cluster" in caplog.text


def test_update_classification_returns_false(caplog):
    repo = _make_repo()
    req = ClassificationUpdateRequest(cluster_id=1, classification="x")
    with caplog.at_level(logging.WARNING):
        result = repo.update_classification(req)
    assert result is False
    assert "update_classification" in caplog.text


def test_query_fits_returns_empty(caplog):
    repo = _make_repo()
    with caplog.at_level(logging.WARNING):
        result = repo.query_fits(fits_id=1)
    assert result == []
    assert "query_fits" in caplog.text
