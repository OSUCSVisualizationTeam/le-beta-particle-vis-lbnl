from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.VizFilter import UniformVizFilter
from le_beta_vis.frontend.viewmodels.FilterStackViewModel import (
    FilterStackEntry,
    FilterStackViewModel,
)


class _IdentityFilter(UniformVizFilter):
    """Minimal UniformVizFilter for stack-mechanics tests."""

    def __init__(self, label: str) -> None:
        self.label = label

    def filter(self, matrix):
        return matrix


@pytest.fixture
def vm():
    return FilterStackViewModel()


@pytest.fixture
def filter_a():
    return _IdentityFilter("A")


@pytest.fixture
def filter_b():
    return _IdentityFilter("B")


@pytest.fixture
def filter_c():
    return _IdentityFilter("C")


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_state_is_empty(vm):
    assert vm.entries == []
    assert vm.active_filters == []


def test_entries_returns_defensive_copy(vm, filter_a):
    vm.add_filter(filter_a)
    snapshot = vm.entries
    snapshot.clear()
    assert len(vm.entries) == 1


# ---------------------------------------------------------------------------
# add_filter
# ---------------------------------------------------------------------------


def test_add_filter_appends_entry(vm, filter_a):
    vm.add_filter(filter_a)
    assert len(vm.entries) == 1
    assert vm.entries[0].filter is filter_a
    assert vm.entries[0].enabled is True


def test_add_filter_disabled_kept_out_of_active(vm, filter_a):
    vm.add_filter(filter_a, enabled=False)
    assert len(vm.entries) == 1
    assert vm.active_filters == []


def test_add_filter_fires_callback(vm, filter_a):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.add_filter(filter_a)
    cb.assert_called_once()


# ---------------------------------------------------------------------------
# remove_filter
# ---------------------------------------------------------------------------


def test_remove_filter_removes_entry(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.remove_filter(0)
    assert len(vm.entries) == 1
    assert vm.entries[0].filter is filter_b


def test_remove_filter_out_of_range_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.remove_filter(99)
    vm.remove_filter(-1)
    cb.assert_not_called()
    assert len(vm.entries) == 1


def test_remove_filter_fires_callback(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.remove_filter(0)
    cb.assert_called_once()


# ---------------------------------------------------------------------------
# move_filter
# ---------------------------------------------------------------------------


def test_move_filter_reorders(vm, filter_a, filter_b, filter_c):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.add_filter(filter_c)
    vm.move_filter(0, 2)
    assert [e.filter for e in vm.entries] == [filter_b, filter_c, filter_a]


def test_move_filter_to_same_position_is_noop(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.move_filter(0, 0)
    cb.assert_not_called()


def test_move_filter_clamps_to_valid_range(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.move_filter(0, 99)
    assert [e.filter for e in vm.entries] == [filter_b, filter_a]


def test_move_filter_invalid_from_index_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.move_filter(5, 0)
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# set_filter_enabled
# ---------------------------------------------------------------------------


def test_set_filter_enabled_toggles(vm, filter_a):
    vm.add_filter(filter_a)
    vm.set_filter_enabled(0, False)
    assert vm.entries[0].enabled is False
    assert vm.active_filters == []


def test_set_filter_enabled_no_change_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_enabled(0, True)  # already enabled
    cb.assert_not_called()


def test_set_filter_enabled_preserves_position(vm, filter_a, filter_b):
    """Toggling must not perturb order — that's the whole point of
    not removing the entry on disable."""
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.set_filter_enabled(0, False)
    vm.set_filter_enabled(0, True)
    assert [e.filter for e in vm.entries] == [filter_a, filter_b]


def test_set_filter_enabled_out_of_range_is_noop(vm):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_enabled(99, False)
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_empties_stack(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.clear()
    assert vm.entries == []
    assert vm.active_filters == []


def test_clear_when_empty_is_noop(vm):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.clear()
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def test_multiple_callbacks_all_fire(vm, filter_a):
    cb1 = MagicMock()
    cb2 = MagicMock()
    vm.add_stack_changed_callback(cb1)
    vm.add_stack_changed_callback(cb2)
    vm.add_filter(filter_a)
    cb1.assert_called_once()
    cb2.assert_called_once()


def test_active_filters_reflects_enabled_state(vm, filter_a, filter_b, filter_c):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b, enabled=False)
    vm.add_filter(filter_c)
    assert vm.active_filters == [filter_a, filter_c]


def test_filter_stack_entry_dataclass_defaults():
    entry = FilterStackEntry(filter=_IdentityFilter("X"))
    assert entry.enabled is True


# ---------------------------------------------------------------------------
# Integration: numpy arrays through active_filters
# ---------------------------------------------------------------------------


class _AddOneFilter(UniformVizFilter):
    def filter(self, matrix):
        return matrix + 1


def test_active_filters_can_be_chained_through_data(vm):
    """Smoke-test that the snapshot the render pipeline consumes is
    actually applicable to ndarrays."""
    vm.add_filter(_AddOneFilter())
    vm.add_filter(_AddOneFilter())
    arr = np.zeros((2, 2))
    for f in vm.active_filters:
        arr = f.filter(arr)
    assert np.all(arr == 2)
