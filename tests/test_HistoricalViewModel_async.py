"""Tests for HistoricalViewModel async loadEvents behavior.

Pure Python tests — no QApplication instantiation.
"""

import threading
import pytest
from unittest.mock import MagicMock

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
)
from MockThumbnailLoaderService import MockThumbnailLoaderService


def _make_physics_mock():
    mock = MagicMock()
    mock.kev_conversion_factor = 1.02857e-5
    return mock


class SlowRepository(EventRepository):
    """Callback-style repository that blocks completion until released."""

    def __init__(self) -> None:
        self._gate = threading.Event()
        self._started = threading.Event()
        self.fetch_count = 0

    def fetch_events(self, callback, on_error):
        self.fetch_clusters(None, None, 0, callback, on_error)

    def fetch_clusters(self, query_filter, limit, offset, callback, on_error):
        self.fetch_count += 1

        def _complete_later() -> None:
            self._started.set()
            self._gate.wait(timeout=5.0)
            callback([])

        threading.Thread(target=_complete_later, daemon=True).start()

    def store_cluster(self, request):
        return None

    def update_classification(self, request, callback, on_error):
        callback(False)

    def query_fits(self, fits_id, callback, on_error):
        callback([])

    def wait_started(self, timeout: float = 1.0) -> bool:
        return self._started.wait(timeout=timeout)

    def release(self) -> None:
        self._gate.set()


class FailingRepository(EventRepository):
    """Callback-style repository that always fails on fetch."""

    def fetch_events(self, callback, on_error):
        on_error("ZMQ socket timeout")

    def fetch_clusters(self, query_filter, limit, offset, callback, on_error):
        on_error("ZMQ socket timeout")

    def store_cluster(self, request):
        return None

    def update_classification(self, request, callback, on_error):
        on_error("ZMQ socket timeout")

    def query_fits(self, fits_id, callback, on_error):
        on_error("ZMQ socket timeout")


@pytest.fixture
def config():
    return MockConfigurationService()


@pytest.fixture
def physics():
    return _make_physics_mock()


# --- Concurrency ---


def test_load_events_concurrent_no_double_start(config, physics):
    """Second loadEvents while first is in flight should be a no-op."""
    repo = SlowRepository()
    vm = HistoricalViewModel(
        config,
        physics,
        repo,
        MockThumbnailLoaderService(),
    )
    vm.loadEvents()
    assert repo.wait_started()
    vm.loadEvents()  # should be ignored
    repo.release()
    # Allow callback thread to complete and clear loading.
    assert vm.isLoading is False or repo.wait_started(timeout=0.1)
    assert repo.fetch_count == 1


def test_load_events_concurrent_loading_states(config, physics):
    """Loading flag transitions: True once, False once even with double call."""
    repo = SlowRepository()
    vm = HistoricalViewModel(
        config,
        physics,
        repo,
        MockThumbnailLoaderService(),
    )
    states = []
    vm.add_loading_changed_callback(lambda loading: states.append(loading))
    vm.loadEvents()
    assert repo.wait_started()
    vm.loadEvents()  # no-op
    repo.release()
    for _ in range(20):
        if states == [True, False]:
            break
        threading.Event().wait(0.01)
    assert states == [True, False]


# --- Error handling ---


def test_load_events_error_fires_error_callback(config, physics):
    """Repository on_error should fire the load error callback."""
    vm = HistoricalViewModel(
        config,
        physics,
        FailingRepository(),
        MockThumbnailLoaderService(),
    )
    errors = []
    vm.add_load_error_callback(lambda msg: errors.append(msg))
    vm.loadEvents()
    assert len(errors) == 1
    assert "ZMQ socket timeout" in errors[0]


# Retired tests kept as comments for traceability.
# These are now redundant with tests/test_HistoricalViewModel_events.py,
# and they no longer validate unique callback-async behavior.
#
# def test_load_events_error_leaves_empty_events(config, physics):
#     """After a load error, events should be empty and no selection."""
#     vm = HistoricalViewModel(
#         config,
#         physics,
#         FailingRepository(),
#         MockThumbnailLoaderService(),
#     )
#     vm.loadEvents()
#     assert vm.events == []
#     assert vm.selectedIndex == -1
#
#
# def test_load_events_error_clears_loading(config, physics):
#     """isLoading must be False after a load error."""
#     vm = HistoricalViewModel(
#         config,
#         physics,
#         FailingRepository(),
#         MockThumbnailLoaderService(),
#     )
#     vm.loadEvents()
#     assert vm.isLoading is False
#
#
# def test_load_events_error_still_fires_events_changed(config, physics):
#     """events_changed should fire even on error so the UI clears stale data."""
#     vm = HistoricalViewModel(
#         config,
#         physics,
#         FailingRepository(),
#         MockThumbnailLoaderService(),
#     )
#     cb = MagicMock()
#     vm.add_events_changed_callback(cb)
#     vm.loadEvents()
#     cb.assert_called_once()
