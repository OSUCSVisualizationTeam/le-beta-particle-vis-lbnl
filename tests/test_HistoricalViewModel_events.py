# Citation for Unit Tests: HistoricalViewModel event loading, selection, and repository integration
# Date: 26/02/2026
# Adapted from Claude Code:
# Write pure Python unit tests for HistoricalViewModel event loading functionality and selection logic using a mock repository.

"""Tests for HistoricalViewModel event loading and selection.

Pure Python tests — no QApplication instantiation.
"""
import pytest
from unittest.mock import MagicMock

from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.MockEventRepository import (
    MockEventRepository,
)
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
)


def _make_physics_mock():
    mock = MagicMock()
    mock.kev_conversion_factor = 1.02857e-5
    return mock


@pytest.fixture
def config():
    return MockConfigurationService()


@pytest.fixture
def physics():
    return _make_physics_mock()


@pytest.fixture
def mock_repo():
    return MockEventRepository()


@pytest.fixture
def vm(config, physics, mock_repo):
    return HistoricalViewModel(config, physics, mock_repo)


# --- loadEvents ---

def test_load_events_populates_list(vm):
    """loadEvents should populate the events list."""
    vm.loadEvents()
    assert len(vm.events) > 0


def test_load_events_all_clusters(vm):
    """All returned events should be Cluster instances."""
    vm.loadEvents()
    for event in vm.events:
        assert isinstance(event, Cluster)


def test_load_events_fires_events_changed(vm):
    """loadEvents should notify events_changed observers."""
    cb = MagicMock()
    vm.add_events_changed_callback(cb)
    vm.loadEvents()
    cb.assert_called_once()


def test_load_events_fires_selected_event_changed(vm):
    """loadEvents should clear selection and notify."""
    cb = MagicMock()
    vm.add_selected_event_changed_callback(cb)
    vm.loadEvents()
    cb.assert_called_once()


def test_load_events_resets_to_first(vm):
    """After loadEvents, selectedIndex should auto-select index 0."""
    vm.loadEvents()
    vm.selectEvent(2)
    vm.loadEvents()
    assert vm.selectedIndex == 0
    assert vm.selectedEvent is vm.events[0]


def test_load_events_auto_selects_first(vm):
    """loadEvents should auto-select the first event."""
    vm.loadEvents()
    assert vm.selectedIndex == 0
    assert vm.selectedEvent is not None
    assert vm.selectedEvent is vm.events[0]


def test_load_events_loading_flag(vm):
    """loadEvents should toggle isLoading true then false."""
    states = []
    vm.add_loading_changed_callback(
        lambda loading: states.append(loading)
    )
    vm.loadEvents()
    assert states == [True, False]


# --- selectEvent ---

def test_select_event_valid(vm):
    """selectEvent(0) should set selectedIndex and selectedEvent."""
    vm.loadEvents()
    vm.selectEvent(0)
    assert vm.selectedIndex == 0
    assert vm.selectedEvent is vm.events[0]


def test_select_event_fires_callback(vm):
    """selectEvent should notify selected_event_changed."""
    vm.loadEvents()
    cb = MagicMock()
    vm.add_selected_event_changed_callback(cb)
    vm.selectEvent(1)
    cb.assert_called_once()


def test_select_event_no_double_fire(vm):
    """Selecting the same index twice should not re-fire."""
    vm.loadEvents()
    vm.selectEvent(0)
    cb = MagicMock()
    vm.add_selected_event_changed_callback(cb)
    vm.selectEvent(0)
    cb.assert_not_called()


def test_select_event_deselect(vm):
    """selectEvent(-1) should clear the selection."""
    vm.loadEvents()
    vm.selectEvent(0)
    vm.selectEvent(-1)
    assert vm.selectedIndex == -1
    assert vm.selectedEvent is None


def test_select_event_out_of_range(vm):
    """Out-of-range index should be treated as deselect."""
    vm.loadEvents()
    vm.selectEvent(0)
    vm.selectEvent(9999)
    assert vm.selectedIndex == -1


def test_select_event_negative_below_minus_one(vm):
    """Index < -1 should be treated as deselect."""
    vm.loadEvents()
    vm.selectEvent(-5)
    assert vm.selectedIndex == -1


# --- Properties ---

def test_initial_state(vm):
    """ViewModel starts with empty events and no selection."""
    assert vm.events == []
    assert vm.selectedIndex == -1
    assert vm.selectedEvent is None
    assert vm.isLoading is False


def test_physics_manager_exposed(vm, physics):
    """physicsManager property should return the injected manager."""
    assert vm.physicsManager is physics


# --- Empty repository ---

def test_empty_repository():
    """An empty repository should produce an empty events list."""
    class EmptyRepo(EventRepository):
        def fetch_events(self):
            return []

    config = MockConfigurationService()
    vm = HistoricalViewModel(
        config, _make_physics_mock(), EmptyRepo()
    )
    vm.loadEvents()
    assert vm.events == []
    assert vm.selectedIndex == -1
