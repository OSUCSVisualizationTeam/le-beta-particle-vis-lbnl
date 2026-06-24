"""Tests for HistoricalViewModel's bidirectional sliding window over paging.

Pure Python tests — no QApplication instantiation.
"""

import threading
from typing import List, Optional

import numpy as np
import pytest
from unittest.mock import MagicMock

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
)
from MockThumbnailLoaderService import MockThumbnailLoaderService


def _make_physics_mock():
    mock = MagicMock()
    mock.kev_conversion_factor = 1.02857e-5
    return mock


def _make_cluster(cluster_id: int) -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(top=0, left=0, bottom=1, right=1),
        data=np.zeros((1, 1), dtype=np.float64),
        centerX=0,
        centerY=0,
        clusterId=cluster_id,
    )


class PagedRepository(EventRepository):
    """Synthetic repository with a configurable total cluster count.

    Supports both forward and backward fetch_clusters calls, gated
    by an optional threading.Event so tests can hold a fetch in
    flight before releasing it.
    """

    def __init__(self, total: int) -> None:
        self.total = total
        self.calls: List[tuple] = []
        self._gate: Optional[threading.Event] = None
        self._started = threading.Event()

    def gate(self) -> threading.Event:
        self._gate = threading.Event()
        return self._gate

    def wait_started(self, timeout: float = 1.0) -> bool:
        return self._started.wait(timeout=timeout)

    def fetch_events(self, callback, on_error):
        self.fetch_clusters(None, None, 0, callback, on_error)

    def fetch_clusters(self, query_filter, limit, offset, callback, on_error):
        self.calls.append((limit, offset))
        end = self.total if limit is None else min(self.total, offset + limit)
        events = [_make_cluster(i) for i in range(offset, max(offset, end))]

        if self._gate is None:
            callback(events)
            return

        def _complete_later() -> None:
            self._started.set()
            self._gate.wait(timeout=5.0)
            callback(events)

        threading.Thread(target=_complete_later, daemon=True).start()

    def store_cluster(self, request):
        return None

    def update_classification(self, request, callback, on_error):
        callback(False)

    def query_fits(self, fits_id, callback, on_error):
        callback([])


class FailingPageRepository(PagedRepository):
    """Forward/backward page fetches beyond the first always fail."""

    def fetch_clusters(self, query_filter, limit, offset, callback, on_error):
        self.calls.append((limit, offset))
        if offset == 0:
            super().fetch_clusters(query_filter, limit, offset, callback, on_error)
            return
        on_error("ZMQ socket timeout")


@pytest.fixture
def config():
    cfg = MockConfigurationService()
    cfg.set("eps:retrieval_limit_default", 10)
    cfg.set("gui:historical:scroll_prefetch_buffer", 3)
    cfg.set("gui:historical:eviction_distance", 3)
    return cfg


def _wait_for_load(vm) -> None:
    if vm._load_thread is not None:
        vm._load_thread.join(timeout=2.0)


# --- Forward paging ---


def test_request_next_page_triggers_fetch_near_window_end(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()

    vm.request_next_page_if_needed(first=5, last=8)  # last=8, window_end=10, buf=3 -> triggers

    assert repo.calls[-1] == (10, 10)
    assert len(vm.events) == 20


def test_request_next_page_no_fetch_when_far_from_end(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    call_count = len(repo.calls)

    vm.request_next_page_if_needed(first=0, last=2)  # far from window_end=10

    assert len(repo.calls) == call_count
    assert len(vm.events) == 10


def test_request_next_page_no_duplicate_fetch_while_in_flight(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()  # ungated — completes synchronously

    gate = repo.gate()
    vm.request_next_page_if_needed(first=5, last=8)
    assert repo.wait_started()
    vm.request_next_page_if_needed(first=5, last=8)  # should be ignored, still in flight
    gate.set()

    assert repo.calls.count((10, 10)) == 1


def test_request_next_page_noop_once_exhausted(config):
    repo = PagedRepository(total=9)  # short of the page_limit(10) -> exhausted immediately
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    assert vm._has_more_forward is False
    call_count = len(repo.calls)

    vm.request_next_page_if_needed(first=5, last=8)

    assert len(repo.calls) == call_count


def test_request_next_page_noop_during_full_reload(config):
    repo = PagedRepository(total=30)
    gate = repo.gate()
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    assert repo.wait_started()  # first load still in flight

    vm.request_next_page_if_needed(first=5, last=8)

    gate.set()
    _wait_for_load(vm)
    assert all(call != (10, 10) for call in repo.calls)


# --- Backward paging ---


def test_request_previous_page_triggers_fetch_near_window_start(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    vm.request_next_page_if_needed(first=5, last=8)  # window becomes [0,20)

    vm.request_previous_page_if_needed(first=1, last=5)  # near window_start=0

    # window_start is already 0 — nothing earlier exists, so no backward fetch.
    assert vm._has_more_backward is False


def test_backward_fetch_after_eviction_refetches_evicted_range(config):
    repo = PagedRepository(total=100)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()  # page [0,10)
    vm.request_next_page_if_needed(first=5, last=8)  # page [10,20), window [0,20)
    vm.request_next_page_if_needed(first=15, last=18)  # page [20,30), window [0,30)
    vm.request_next_page_if_needed(first=25, last=28)  # page [30,40); evicts [0,10), window [10,40)

    assert vm._window_start == 10
    assert vm._has_more_backward is True

    vm.request_previous_page_if_needed(first=11, last=15)  # near window_start=10

    assert repo.calls[-1] == (10, 0)
    assert vm._window_start == 0
    assert len(vm.events) == 30  # back page evicted to make room for the re-fetched front page


# --- Eviction ---


def test_eviction_fires_after_exceeding_max_window_pages(config):
    repo = PagedRepository(total=100)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    evicted: List[tuple] = []
    vm.add_events_evicted_callback(lambda offset, count: evicted.append((offset, count)))
    vm.loadEvents()  # page [0,10)

    vm.request_next_page_if_needed(first=5, last=8)  # page [10,20)
    assert evicted == []
    vm.request_next_page_if_needed(first=15, last=18)  # page [20,30) — still within 3-page cap
    assert evicted == []
    vm.request_next_page_if_needed(first=25, last=28)  # page [30,40) — exceeds cap, evicts [0,10)

    assert evicted == [(0, 10)]
    assert vm._window_start == 10


def test_appended_callback_fires_without_full_reset(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    appended: List[list] = []
    changed_calls = []
    vm.add_events_appended_callback(lambda events: appended.append(events))
    vm.add_events_changed_callback(lambda: changed_calls.append(1))
    vm.loadEvents()
    assert len(changed_calls) == 1

    vm.request_next_page_if_needed(first=5, last=8)

    assert len(appended) == 1
    assert len(appended[0]) == 10
    assert len(changed_calls) == 1  # not re-fired on append


def test_selected_index_unchanged_across_page_append(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    vm.selectEvent(3)

    vm.request_next_page_if_needed(first=5, last=8)

    assert vm.selectedIndex == 3


def test_selected_event_none_once_its_page_is_evicted(config):
    repo = PagedRepository(total=100)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()  # page [0,10)
    vm.selectEvent(3)

    vm.request_next_page_if_needed(first=5, last=8)   # page [10,20)
    vm.request_next_page_if_needed(first=15, last=18)  # page [20,30)
    vm.request_next_page_if_needed(first=25, last=28)  # page [30,40) — evicts [0,10)

    assert vm.selectedEvent is None


# --- Stale fetch rejection ---


def test_stale_page_fetch_ignored_after_loadEvents_supersedes(config):
    repo = PagedRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    gate = repo.gate()
    vm.request_next_page_if_needed(first=5, last=8)
    assert repo.wait_started()

    vm.loadEvents()  # supersedes the in-flight page fetch
    gate.set()
    _wait_for_load(vm)

    assert len(vm.events) == 10  # only the fresh reload's page, not page1+stale-page2


def test_page_fetch_offset_advances_across_multiple_pages(config):
    repo = PagedRepository(total=40)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()

    vm.request_next_page_if_needed(first=5, last=8)
    vm.request_next_page_if_needed(first=15, last=18)
    vm.request_next_page_if_needed(first=25, last=28)

    assert repo.calls == [(10, 0), (10, 10), (10, 20), (10, 30)]


# --- Thrash guard ---


def test_safe_max_window_pages_widens_for_small_page_size():
    cfg = MockConfigurationService()
    cfg.set("eps:retrieval_limit_default", 10)
    cfg.set("gui:historical:scroll_prefetch_buffer", 30)  # buffer > page_limit/2
    repo = PagedRepository(total=200)
    vm = HistoricalViewModel(cfg, _make_physics_mock(), repo, MockThumbnailLoaderService())
    assert vm._safe_max_window_pages() == 5


def test_safe_max_window_pages_unchanged_at_realistic_config(config):
    repo = PagedRepository(total=200)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    assert vm._safe_max_window_pages() == 3


# --- loadEvents(offset=...) / jump_to_page ---


def test_load_events_with_offset_anchors_window(config):
    repo = PagedRepository(total=40)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())

    vm.loadEvents(offset=20)

    assert repo.calls[-1] == (10, 20)
    assert vm._window_start == 20
    assert vm.selectedIndex == 20
    assert vm.hasMoreBackward is True
    assert vm.hasMoreForward is True


def test_load_events_offset_zero_has_no_backward(config):
    repo = PagedRepository(total=40)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())

    vm.loadEvents()

    assert vm.hasMoreBackward is False
    assert vm.hasMoreForward is True


def test_load_events_offset_short_page_has_no_forward(config):
    repo = PagedRepository(total=25)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())

    vm.loadEvents(offset=20)  # only 5 clusters remain -> short page

    assert vm.hasMoreForward is False
    assert len(vm.events) == 5


def test_jump_to_page_next_advances_one_page_width(config):
    repo = PagedRepository(total=40)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()  # page [0,10)

    vm.jump_to_page(anchor_global_index=3, direction=1)

    assert repo.calls[-1] == (10, 10)
    assert vm._window_start == 10


def test_jump_to_page_previous_returns_one_page_width(config):
    repo = PagedRepository(total=40)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents(offset=20)

    vm.jump_to_page(anchor_global_index=23, direction=-1)

    assert repo.calls[-1] == (10, 10)
    assert vm._window_start == 10


def test_jump_to_page_previous_noop_at_first_page(config):
    repo = PagedRepository(total=40)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()  # page [0,10)
    call_count = len(repo.calls)

    vm.jump_to_page(anchor_global_index=3, direction=-1)

    assert len(repo.calls) == call_count
    assert vm._window_start == 0


# --- Page errors ---


def test_page_fetch_error_fires_error_callback_without_toggling_loading(config):
    repo = FailingPageRepository(total=30)
    vm = HistoricalViewModel(config, _make_physics_mock(), repo, MockThumbnailLoaderService())
    vm.loadEvents()
    states = []
    errors = []
    vm.add_loading_changed_callback(lambda loading: states.append(loading))
    vm.add_load_error_callback(lambda msg: errors.append(msg))

    vm.request_next_page_if_needed(first=5, last=8)

    assert errors == ["ZMQ socket timeout"]
    assert states == []  # isLoading never toggled by a page-fetch failure
    assert vm.isLoading is False
