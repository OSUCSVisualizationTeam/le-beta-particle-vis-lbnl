from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.VizFilter import (
    ScalingFunction,
    UniformFilter,
    UniformVizFilter,
)
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


def _user_index(vm: FilterStackViewModel, filt: UniformVizFilter) -> int:
    """Index of *filt* in ``vm.entries`` by identity (-1 when missing)."""
    for i, entry in enumerate(vm.entries):
        if entry.filter is filt:
            return i
    return -1


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
# Initial state: pinned entries are seeded; user region is empty
# ---------------------------------------------------------------------------


def test_initial_state_has_pinned_filters_only(vm):
    """The ViewModel seeds ADU→keV, ScalePreset, and Window at construction.
    user_active_filters is the slice that contains no pinned entries."""
    assert vm.user_active_filters == []
    assert len(vm.entries) == 3
    assert all(e.pinned for e in vm.entries)


def test_pinned_entries_are_in_canonical_order(vm):
    """ADU→keV at index 0; ScalePreset second-to-last; Window last."""
    type_ids = [e.filter.SPEC.type_id for e in vm.entries]
    assert type_ids == ["adu_to_kev", "scale_preset", "window"]


def test_find_pinned_index_locates_each(vm):
    assert vm.find_pinned_index("adu_to_kev") == 0
    assert vm.find_pinned_index("scale_preset") == 1
    assert vm.find_pinned_index("window") == 2
    assert vm.find_pinned_index("does_not_exist") is None


def test_is_pinned_at_matches_seeded_positions(vm):
    assert vm.is_pinned_at(0) is True
    assert vm.is_pinned_at(1) is True
    assert vm.is_pinned_at(2) is True
    assert vm.is_pinned_at(99) is False


def test_entries_returns_defensive_copy(vm, filter_a):
    vm.add_filter(filter_a)
    snapshot = vm.entries
    snapshot.clear()
    # original stack still has 3 pinned + 1 user = 4 entries
    assert len(vm.entries) == 4


# ---------------------------------------------------------------------------
# add_filter inserts into the user-movable middle region
# ---------------------------------------------------------------------------


def test_add_filter_inserts_before_trailing_pinned(vm, filter_a):
    """New user filters land between ADU→keV and ScalePreset."""
    vm.add_filter(filter_a)
    assert _user_index(vm, filter_a) == 1
    assert vm.entries[1].filter is filter_a
    assert vm.entries[1].enabled is True
    # surrounding pinned entries unchanged
    assert vm.entries[0].filter.SPEC.type_id == "adu_to_kev"
    assert vm.entries[-2].filter.SPEC.type_id == "scale_preset"
    assert vm.entries[-1].filter.SPEC.type_id == "window"


def test_add_filter_disabled_kept_out_of_user_active(vm, filter_a):
    vm.add_filter(filter_a, enabled=False)
    assert vm.user_active_filters == []
    assert filter_a in [e.filter for e in vm.entries]


def test_add_filter_fires_callback(vm, filter_a):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.add_filter(filter_a)
    cb.assert_called_once()


def test_add_multiple_filters_keeps_pinned_at_ends(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    type_ids = [e.filter.SPEC.type_id if e.pinned else "user"
                for e in vm.entries]
    assert type_ids == [
        "adu_to_kev", "user", "user", "scale_preset", "window",
    ]


# ---------------------------------------------------------------------------
# remove_filter
# ---------------------------------------------------------------------------


def test_remove_filter_removes_user_entry(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    a_idx = _user_index(vm, filter_a)
    vm.remove_filter(a_idx)
    assert filter_a not in [e.filter for e in vm.entries]
    assert filter_b in [e.filter for e in vm.entries]


def test_remove_filter_on_pinned_is_noop(vm):
    """Pinned entries are structural and cannot be deleted."""
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    starting_count = len(vm.entries)
    vm.remove_filter(0)   # ADU→keV
    vm.remove_filter(1)   # ScalePreset
    vm.remove_filter(2)   # Window
    cb.assert_not_called()
    assert len(vm.entries) == starting_count


def test_remove_filter_out_of_range_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.remove_filter(99)
    vm.remove_filter(-1)
    cb.assert_not_called()


def test_remove_filter_fires_callback(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.remove_filter(_user_index(vm, filter_a))
    cb.assert_called_once()


# ---------------------------------------------------------------------------
# move_filter — clamped to user-movable range; pinned cannot move
# ---------------------------------------------------------------------------


def test_move_filter_reorders_within_user_region(
    vm, filter_a, filter_b, filter_c
):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.add_filter(filter_c)
    # initial user order: a, b, c at indices 1, 2, 3
    vm.move_filter(_user_index(vm, filter_a), 3)
    user_filters = [
        e.filter for e in vm.entries if not e.pinned
    ]
    assert user_filters == [filter_b, filter_c, filter_a]


def test_move_filter_cannot_displace_pinned(vm, filter_a):
    vm.add_filter(filter_a)
    # trying to move into the trailing pinned block should clamp into
    # the user range
    vm.move_filter(_user_index(vm, filter_a), 99)
    # filter_a still lives in the user region, never overlaps Window
    assert vm.entries[-1].filter.SPEC.type_id == "window"
    assert vm.entries[-2].filter.SPEC.type_id == "scale_preset"


def test_move_filter_on_pinned_is_noop(vm):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.move_filter(0, 1)  # try to move ADU→keV
    vm.move_filter(2, 0)  # try to move Window to head
    cb.assert_not_called()


def test_move_filter_to_same_position_is_noop(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    a_idx = _user_index(vm, filter_a)
    vm.move_filter(a_idx, a_idx)
    cb.assert_not_called()


def test_move_filter_invalid_from_index_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.move_filter(99, 0)
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# set_filter_enabled
# ---------------------------------------------------------------------------


def test_set_filter_enabled_toggles_user_filter(vm, filter_a):
    vm.add_filter(filter_a)
    a_idx = _user_index(vm, filter_a)
    vm.set_filter_enabled(a_idx, False)
    assert vm.entries[a_idx].enabled is False
    assert vm.user_active_filters == []


def test_set_filter_enabled_on_pinned_is_noop(vm):
    """Pinned filters cannot be toggled off — pipeline assumes them."""
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_enabled(0, False)
    cb.assert_not_called()
    assert vm.entries[0].enabled is True


def test_set_filter_enabled_no_change_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_enabled(_user_index(vm, filter_a), True)  # already enabled
    cb.assert_not_called()


def test_set_filter_enabled_preserves_position(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    a_idx = _user_index(vm, filter_a)
    vm.set_filter_enabled(a_idx, False)
    vm.set_filter_enabled(a_idx, True)
    user_filters = [e.filter for e in vm.entries if not e.pinned]
    assert user_filters == [filter_a, filter_b]


def test_set_filter_enabled_out_of_range_is_noop(vm):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_enabled(99, False)
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# clear — preserves pinned entries
# ---------------------------------------------------------------------------


def test_clear_removes_user_filters_only(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.clear()
    assert vm.user_active_filters == []
    assert len(vm.entries) == 3
    assert all(e.pinned for e in vm.entries)


def test_clear_with_no_user_filters_is_noop(vm):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.clear()  # only pinned present, nothing to clear
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


def test_user_active_filters_reflects_enabled_state(
    vm, filter_a, filter_b, filter_c
):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b, enabled=False)
    vm.add_filter(filter_c)
    assert vm.user_active_filters == [filter_a, filter_c]


def test_filter_stack_entry_dataclass_defaults():
    entry = FilterStackEntry(filter=_IdentityFilter("X"))
    assert entry.enabled is True
    assert entry.pinned is False
    assert isinstance(entry.id, str)
    assert len(entry.id) > 0


# ---------------------------------------------------------------------------
# Stable entry IDs
# ---------------------------------------------------------------------------


def test_entry_ids_are_unique(vm, filter_a, filter_b, filter_c):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.add_filter(filter_c)
    ids = [e.id for e in vm.entries]
    assert len(set(ids)) == len(ids)


def test_entry_id_survives_reorder(vm, filter_a, filter_b, filter_c):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.add_filter(filter_c)
    b_idx = _user_index(vm, filter_b)
    b_id = vm.entries[b_idx].id
    vm.move_filter(b_idx, b_idx - 1)  # move b before a
    new_idx = _user_index(vm, filter_b)
    assert vm.entries[new_idx].id == b_id


# ---------------------------------------------------------------------------
# move_filter_by_id
# ---------------------------------------------------------------------------


def test_move_filter_by_id_resolves_position(
    vm, filter_a, filter_b, filter_c
):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    vm.add_filter(filter_c)
    c_id = vm.entries[_user_index(vm, filter_c)].id
    # move c to the head of the user region (index 1)
    vm.move_filter_by_id(c_id, 1)
    user_filters = [e.filter for e in vm.entries if not e.pinned]
    assert user_filters == [filter_c, filter_a, filter_b]


def test_move_filter_by_id_unknown_id_is_noop(vm, filter_a):
    vm.add_filter(filter_a)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.move_filter_by_id("does-not-exist", 0)
    cb.assert_not_called()


def test_move_filter_by_id_fires_callback(vm, filter_a, filter_b):
    vm.add_filter(filter_a)
    vm.add_filter(filter_b)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    b_id = vm.entries[_user_index(vm, filter_b)].id
    vm.move_filter_by_id(b_id, 1)
    cb.assert_called_once()


# ---------------------------------------------------------------------------
# set_filter_parameter and set_pinned_parameter
# ---------------------------------------------------------------------------


class _ConfigurableFilter(UniformVizFilter):
    """Test fixture with a public ``sigma`` attribute (like Gaussian)."""

    def __init__(self, sigma: float = 1.0) -> None:
        self.sigma = sigma

    def filter(self, matrix):
        return matrix * self.sigma


def test_set_filter_parameter_mutates_user_filter(vm):
    f = _ConfigurableFilter(sigma=1.0)
    vm.add_filter(f)
    vm.set_filter_parameter(_user_index(vm, f), "sigma", 3.5)
    assert f.sigma == 3.5


def test_set_filter_parameter_fires_callback(vm):
    f = _ConfigurableFilter(sigma=1.0)
    vm.add_filter(f)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_parameter(_user_index(vm, f), "sigma", 2.0)
    cb.assert_called_once()


def test_set_filter_parameter_out_of_range_index_is_noop(vm):
    f = _ConfigurableFilter(sigma=1.0)
    vm.add_filter(f)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_parameter(99, "sigma", 2.0)
    cb.assert_not_called()
    assert f.sigma == 1.0


def test_set_filter_parameter_unknown_attribute_is_noop(vm):
    f = _ConfigurableFilter(sigma=1.0)
    vm.add_filter(f)
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_filter_parameter(_user_index(vm, f), "bogus_attr", 2.0)
    cb.assert_not_called()
    assert f.sigma == 1.0


def test_set_filter_parameter_works_on_pinned_window(vm):
    """VerticalRangeControl edits land on the pinned Window via this API."""
    vm.set_pinned_parameter("window", "vmin", 0.05)
    vm.set_pinned_parameter("window", "vmax", 0.5)
    window_idx = vm.find_pinned_index("window")
    window = vm.entries[window_idx].filter
    assert window.vmin == 0.05
    assert window.vmax == 0.5


def test_set_pinned_parameter_mutates_scale_preset_mode(vm):
    vm.set_pinned_parameter("scale_preset", "mode", ScalingFunction.LOG)
    sp_idx = vm.find_pinned_index("scale_preset")
    assert vm.entries[sp_idx].filter.mode == ScalingFunction.LOG


def test_set_pinned_parameter_unknown_type_id_is_noop(vm):
    cb = MagicMock()
    vm.add_stack_changed_callback(cb)
    vm.set_pinned_parameter("not_a_real_type", "x", 1.0)
    cb.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: numpy arrays through user_active_filters
# ---------------------------------------------------------------------------


class _AddOneFilter(UniformVizFilter):
    def filter(self, matrix):
        return matrix + 1


def test_user_active_filters_can_be_chained_through_data(vm):
    """Sanity: render path can compose the user-filter snapshot."""
    vm.add_filter(_AddOneFilter())
    vm.add_filter(_AddOneFilter())
    arr = np.zeros((2, 2))
    for f in vm.user_active_filters:
        arr = f.filter(arr)
    assert np.all(arr == 2)


def test_full_pinned_chain_normalizes_keV_to_unit_interval(vm):
    """End-to-end: pinned chain converts ADU input to [0, 1] output.

    With Window seeded at [0, 1] keV and Linear ScalePreset, an input
    spanning 0–100000 ADU produces values in [0, 1]."""
    # Seed Window range matching what _seed_pinned_filter_state does
    vm.set_pinned_parameter("window", "vmin", 0.0)
    vm.set_pinned_parameter("window", "vmax", 1.0)
    vm.set_pinned_parameter(
        "adu_to_kev", "factor", UniformFilter.ADUtoKeV().factor,
    )
    adu = np.array([0.0, 50000.0, 100000.0])
    out = adu.copy()
    for f in vm.active_filters:
        out = f.filter(out)
    assert out.min() >= 0.0
    assert out.max() <= 1.0
