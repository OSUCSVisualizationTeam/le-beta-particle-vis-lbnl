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


def _wait_for_load(vm) -> None:
    """Joins the background load thread to wait for completion."""
    if vm._load_thread is not None:
        vm._load_thread.join(timeout=2.0)


class SlowRepository(EventRepository):
    """Repository that blocks until released, for concurrency tests."""

    def __init__(self) -> None:
        self._gate = threading.Event()
        self.fetch_count = 0

    def fetch_events(self):
        self.fetch_count += 1
        self._gate.wait(timeout=5.0)
        return []

    def release(self) -> None:
        self._gate.set()


class FailingRepository(EventRepository):
    """Repository that always raises on fetch."""

    def fetch_events(self):
        raise ConnectionError("ZMQ socket timeout")


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
    vm.loadEvents()  # should be ignored
    repo.release()
    _wait_for_load(vm)
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
    vm.loadEvents()  # no-op
    repo.release()
    _wait_for_load(vm)
    assert states == [True, False]


# --- Error handling ---


def test_load_events_error_fires_error_callback(config, physics):
    """Repository exception should fire the error callback."""
    vm = HistoricalViewModel(
        config,
        physics,
        FailingRepository(),
        MockThumbnailLoaderService(),
    )
    errors = []
    vm.add_load_error_callback(lambda msg: errors.append(msg))
    vm.loadEvents()
    _wait_for_load(vm)
    assert len(errors) == 1
    assert "ZMQ socket timeout" in errors[0]


def test_load_events_error_leaves_empty_events(config, physics):
    """After a load error, events should be empty and no selection."""
    vm = HistoricalViewModel(
        config,
        physics,
        FailingRepository(),
        MockThumbnailLoaderService(),
    )
    vm.loadEvents()
    _wait_for_load(vm)
    assert vm.events == []
    assert vm.selectedIndex == -1


def test_load_events_error_clears_loading(config, physics):
    """isLoading must be False after a load error."""
    vm = HistoricalViewModel(
        config,
        physics,
        FailingRepository(),
        MockThumbnailLoaderService(),
    )
    vm.loadEvents()
    _wait_for_load(vm)
    assert vm.isLoading is False


def test_load_events_error_still_fires_events_changed(config, physics):
    """events_changed should fire even on error so the UI clears stale data."""
    vm = HistoricalViewModel(
        config,
        physics,
        FailingRepository(),
        MockThumbnailLoaderService(),
    )
    cb = MagicMock()
    vm.add_events_changed_callback(cb)
    vm.loadEvents()
    _wait_for_load(vm)
    cb.assert_called_once()
