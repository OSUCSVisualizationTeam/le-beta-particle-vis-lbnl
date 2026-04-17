"""Tests for NoOpEventRepository.

Verifies that all methods return safe defaults and emit warnings.
"""
import logging

from le_beta_vis.common.NoOpEventRepository import NoOpEventRepository
from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    FitsClusterQueryFilter,
)


def _make_repo() -> NoOpEventRepository:
    return NoOpEventRepository()


def test_fetch_events_returns_empty(caplog):
    repo = _make_repo()
    got = {"events": None, "error": None}
    with caplog.at_level(logging.WARNING):
        repo.fetch_events(
            callback=lambda events: got.__setitem__("events", events),
            on_error=lambda error: got.__setitem__("error", error),
        )
    assert got["events"] == []
    assert got["error"] is None
    assert "fetch_events" in caplog.text


def test_query_clusters_returns_empty(caplog):
    repo = _make_repo()
    qf = ClusterQueryFilter(fits_id=1)
    got = {"events": None, "error": None}
    with caplog.at_level(logging.WARNING):
        repo.query_clusters(
            qf,
            callback=lambda events: got.__setitem__("events", events),
            on_error=lambda error: got.__setitem__("error", error),
        )
    assert got["events"] == []
    assert got["error"] is None
    assert "query_clusters" in caplog.text


def test_query_clusters_none_filter(caplog):
    repo = _make_repo()
    got = {"events": None, "error": None}
    with caplog.at_level(logging.WARNING):
        repo.query_clusters(
            None,
            callback=lambda events: got.__setitem__("events", events),
            on_error=lambda error: got.__setitem__("error", error),
        )
    assert got["events"] == []
    assert got["error"] is None


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
    got = {"updated": None, "error": None}
    with caplog.at_level(logging.WARNING):
        repo.update_classification(
            req,
            callback=lambda updated: got.__setitem__("updated", updated),
            on_error=lambda error: got.__setitem__("error", error),
        )
    assert got["updated"] is None
    assert isinstance(got["error"], str)
    assert "update_classification" in caplog.text


def test_query_fits_returns_empty(caplog):
    repo = _make_repo()
    got = {"fits": None, "error": None}
    with caplog.at_level(logging.WARNING):
        repo.query_fits(
            fits_id=1,
            callback=lambda fits: got.__setitem__("fits", fits),
            on_error=lambda error: got.__setitem__("error", error),
        )
    assert got["fits"] == []
    assert got["error"] is None
    assert "query_fits" in caplog.text


def test_query_fits_clusters_returns_empty(caplog):
    repo = _make_repo()
    qf = FitsClusterQueryFilter(fits_id=1)
    got = {"events": None, "error": None}
    with caplog.at_level(logging.WARNING):
        repo.query_fits_clusters(
            qf,
            callback=lambda events: got.__setitem__("events", events),
            on_error=lambda error: got.__setitem__("error", error),
        )
    assert got["events"] == []
    assert got["error"] is None
    assert "query_fits_clusters" in caplog.text
