"""Tests for the ``fetch_all_hdu_clusters_sync`` pagination helper."""

from typing import List, Optional

from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.EventRepository import fetch_all_hdu_clusters_sync


class _FakeEventRepository:
    """Minimal duck-typed fake exposing only ``fetch_clusters_sync``, backed by a fixed item list.

    Records every ``(limit, offset, query_filter)`` it was called with, so tests can assert on the exact paging sequence and
    the filter shape the helper builds.
    """

    def __init__(self, items: List[object]):
        self._items = items
        self.calls: List[tuple] = []

    def fetch_clusters_sync(
        self,
        limit: Optional[int],
        offset: int,
        query_filter: Optional[ClusterQueryFilter] = None,
    ) -> List[object]:
        self.calls.append((limit, offset, query_filter))
        return self._items[offset:offset + limit]


def test_single_short_page_returns_everything():
    repo = _FakeEventRepository(items=["a", "b", "c"])

    result = fetch_all_hdu_clusters_sync(repo, fits_id=1, hdu_id=0, page_limit=10)

    assert result == ["a", "b", "c"]
    assert len(repo.calls) == 1


def test_exact_page_boundary_makes_one_extra_call():
    """A page exactly page_limit long can't tell if more data follows, so one more request happens."""
    repo = _FakeEventRepository(items=["a", "b"])

    result = fetch_all_hdu_clusters_sync(repo, fits_id=1, hdu_id=0, page_limit=2)

    assert result == ["a", "b"]
    assert repo.calls == [(2, 0, ClusterQueryFilter(fits_id=1, hdu_id=0)), (2, 2, ClusterQueryFilter(fits_id=1, hdu_id=0))]


def test_multi_page_loop_concatenates_all_pages():
    repo = _FakeEventRepository(items=list(range(1250)))

    result = fetch_all_hdu_clusters_sync(repo, fits_id=7, hdu_id=2, page_limit=500)

    assert result == list(range(1250))
    assert [c[:2] for c in repo.calls] == [(500, 0), (500, 500), (500, 1000)]


def test_empty_result_set_makes_one_call():
    repo = _FakeEventRepository(items=[])

    result = fetch_all_hdu_clusters_sync(repo, fits_id=1, hdu_id=0, page_limit=500)

    assert result == []
    assert len(repo.calls) == 1


def test_query_filter_scoped_to_single_fits_and_hdu():
    """The helper always builds its own narrow filter -- callers cannot broaden it."""
    repo = _FakeEventRepository(items=["a"])

    fetch_all_hdu_clusters_sync(repo, fits_id=42, hdu_id=3, page_limit=500)

    (_, _, sent_filter), = repo.calls
    assert sent_filter == ClusterQueryFilter(fits_id=42, hdu_id=3)
