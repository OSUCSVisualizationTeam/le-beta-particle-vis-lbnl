import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from le_beta_vis.common.filter_pipeline import UniformFilter, UniformVizFilter


@dataclass
class FilterStackEntry:
    """One slot in the Interactive Filter Stack.

    Pairs a :class:`UniformVizFilter` with a UI-toggleable ``enabled``
    flag and a stable ``id``. When disabled the filter is skipped at
    render time without leaving the stack — so toggling preserves
    position.

    ``pinned`` marks structural filters that are seeded by the
    ViewModel (ADU→keV at the head; ScalePreset and Window at the
    tail). Pinned entries cannot be removed by the user and cannot be
    moved past one another; they also cannot be reordered into the
    user-movable middle section. Use :meth:`FilterStackViewModel.is_pinned_at`
    to query.

    The ``id`` is a UUID hex string that survives reordering and is
    used by drag-and-drop to identify which entry is being moved
    (index-based identity breaks mid-drag when other rows shift).
    """

    filter: UniformVizFilter
    enabled: bool = True
    pinned: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


class FilterStackViewModel:
    """ViewModel for the Interactive Filter Stack (issue #31).

    Owns the ordered list of :class:`UniformVizFilter` instances that
    drive the render pipeline. Pure Python (no Qt) so it runs in
    headless CI.

    Pinned structural filters are seeded at construction in canonical
    pipeline order:

    - index 0: ``UniformFilter.ADUtoKeV`` (converts raw ADU to keV).
    - index -2: ``UniformFilter.ScalePreset`` (Linear/Log/Sqrt).
    - index -1: ``UniformFilter.Window`` (clip + normalize to [0, 1]).

    User filters live in the open middle region ``[1, len-2)``.

    Observers register via :meth:`add_stack_changed_callback`; the
    callback fires after any mutation (add / remove / move / toggle /
    parameter change / clear). The host ViewModel typically wires this
    to a render-request method so visual updates follow filter edits
    automatically.
    """

    def __init__(self) -> None:
        self._entries: List[FilterStackEntry] = []
        self._stack_changed_callbacks: List[Callable[[], None]] = []
        self._seed_pinned_entries()

    def _seed_pinned_entries(self) -> None:
        """Populate the canonical pinned filters in pipeline order.

        Called once at construction. Values come from each filter
        class's constructor defaults; the host ViewModel may update
        them post-construction (e.g. ADU→keV factor from
        PhysicsConversionManager) via :meth:`set_pinned_parameter` or
        :meth:`find_pinned_index` + :meth:`set_filter_parameter`.
        """
        self._entries.append(
            FilterStackEntry(filter=UniformFilter.ADUtoKeV(), pinned=True)
        )
        self._entries.append(
            FilterStackEntry(filter=UniformFilter.ScalePreset(), pinned=True)
        )
        self._entries.append(
            FilterStackEntry(filter=UniformFilter.Window(), pinned=True)
        )

    @property
    def entries(self) -> List[FilterStackEntry]:
        """Snapshot of the full stack (defensive copy).

        Use this from UI code that needs both the filter object and
        its enabled flag for each slot.
        """
        return list(self._entries)

    @property
    def active_filters(self) -> List[UniformVizFilter]:
        """Snapshot of enabled filters in render order.

        The render pipeline reads this at render time. Disabled
        entries are skipped without removing them from the stack.
        Includes pinned entries — once the pipeline collapses into a
        single chain (Phase 3), this is the authoritative ordering.
        """
        return [entry.filter for entry in self._entries if entry.enabled]

    @property
    def user_active_filters(self) -> List[UniformVizFilter]:
        """Enabled user filters (non-pinned) in render order.

        Interim accessor used while the render pipeline still has a
        separate ScaleStage/ColormapStage; the pinned ADU→keV /
        ScalePreset / Window filters are read out-of-band by the host
        ViewModel during this transition.
        """
        return [
            entry.filter
            for entry in self._entries
            if entry.enabled and not entry.pinned
        ]

    def is_pinned_at(self, index: int) -> bool:
        """True when the entry at *index* is pinned (or index is OOB)."""
        if not (0 <= index < len(self._entries)):
            return False
        return self._entries[index].pinned

    def find_pinned_index(self, type_id: str) -> Optional[int]:
        """Index of the pinned entry whose filter SPEC matches *type_id*.

        Returns ``None`` if no pinned entry matches. Use this from the
        host ViewModel to locate ADU→keV / ScalePreset / Window without
        relying on hard-coded positions.
        """
        for i, entry in enumerate(self._entries):
            if not entry.pinned:
                continue
            spec = getattr(entry.filter, "SPEC", None)
            if spec is not None and spec.type_id == type_id:
                return i
        return None

    def _first_trailing_pinned_index(self) -> int:
        """Index of the first pinned entry in the trailing pinned run.

        New user filters are inserted *before* this index so they land
        between ADU→keV and the ScalePreset/Window block.
        """
        for i, entry in enumerate(self._entries):
            if entry.pinned and i > 0:
                return i
        return len(self._entries)

    def add_filter(
        self, filt: UniformVizFilter, enabled: bool = True
    ) -> None:
        """Insert *filt* into the user-movable middle region.

        Lands just before the trailing pinned block (ScalePreset),
        which keeps user filters in keV domain ahead of any scaling
        and windowing.
        """
        insert_at = self._first_trailing_pinned_index()
        self._entries.insert(
            insert_at, FilterStackEntry(filter=filt, enabled=enabled)
        )
        self._notify_stack_changed()

    def remove_filter(self, index: int) -> None:
        """Remove the filter at *index*.

        Out-of-range indices and pinned entries are silently ignored so
        UI flows that race with stack mutations don't have to guard
        every call.
        """
        if not (0 <= index < len(self._entries)):
            return
        if self._entries[index].pinned:
            return
        del self._entries[index]
        self._notify_stack_changed()

    def _movable_range(self) -> tuple:
        """Half-open ``[lo, hi)`` index range where user filters live.

        Excludes any leading pinned entries and the trailing pinned
        block. Empty when the stack contains only pinned filters.
        """
        lo = 0
        for i, entry in enumerate(self._entries):
            if not entry.pinned:
                lo = i
                break
            lo = i + 1
        hi = self._first_trailing_pinned_index()
        return lo, hi

    def move_filter(self, from_index: int, to_index: int) -> None:
        """Move the filter at *from_index* to *to_index*.

        Pinned entries cannot move and cannot be displaced. ``to_index``
        is clamped to the user-movable range so a drag never lands a
        user filter in a pinned slot.
        """
        if not (0 <= from_index < len(self._entries)):
            return
        if self._entries[from_index].pinned:
            return
        lo, hi = self._movable_range()
        clamped_to = max(lo, min(to_index, hi - 1))
        if from_index == clamped_to:
            return
        entry = self._entries.pop(from_index)
        self._entries.insert(clamped_to, entry)
        self._notify_stack_changed()

    def set_filter_enabled(self, index: int, enabled: bool) -> None:
        """Toggle the enabled flag on the filter at *index*.

        Pinned filters cannot be disabled — they are structural and
        the pipeline assumes their presence (e.g. Window owns the
        [0, 1] LUT contract).
        """
        if not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
        if entry.pinned:
            return
        if entry.enabled == enabled:
            return
        entry.enabled = enabled
        self._notify_stack_changed()

    def set_filter_parameter(
        self, index: int, name: str, value: Any
    ) -> None:
        """Mutate parameter *name* on the filter at *index*.

        The IFS parameter popover drives this on every value change
        for live preview. Mutation goes through :func:`setattr`, so
        filter classes must expose their parameters as public
        attributes. Out-of-range indices and missing attributes are
        no-ops to keep UI flows simple.

        Works on both pinned and unpinned entries — that is how
        VerticalRangeControl edits land on the pinned Window filter.

        Fires the stack-changed callbacks so observers (typically
        :class:`RawDataViewModel._request_render`) re-render.
        """
        if not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
        if not hasattr(entry.filter, name):
            return
        setattr(entry.filter, name, value)
        self._notify_stack_changed()

    def set_pinned_parameter(
        self, type_id: str, name: str, value: Any
    ) -> None:
        """Convenience: mutate a pinned filter's parameter by SPEC id.

        Equivalent to :meth:`find_pinned_index` + :meth:`set_filter_parameter`.
        Silently no-ops when no pinned entry matches.
        """
        index = self.find_pinned_index(type_id)
        if index is None:
            return
        self.set_filter_parameter(index, name, value)

    def move_filter_by_id(self, entry_id: str, to_index: int) -> None:
        """Move the entry with matching ``id`` to *to_index*.

        Used by drag-and-drop reorder so a moving filter doesn't lose
        track if other rows shift mid-drag. Falls through to
        :meth:`move_filter` once the index is resolved. Unknown ids
        are silently ignored.
        """
        index = self._index_of(entry_id)
        if index is None:
            return
        self.move_filter(index, to_index)

    def _index_of(self, entry_id: str) -> Optional[int]:
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                return i
        return None

    def clear(self) -> None:
        """Remove every user filter from the stack.

        Pinned entries are preserved — the pipeline must always have
        ADU→keV at the head and ScalePreset/Window at the tail.
        """
        new_entries = [e for e in self._entries if e.pinned]
        if len(new_entries) == len(self._entries):
            return
        self._entries = new_entries
        self._notify_stack_changed()

    def add_stack_changed_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Register *callback* to fire after any mutation."""
        self._stack_changed_callbacks.append(callback)

    def _notify_stack_changed(self) -> None:
        for callback in self._stack_changed_callbacks:
            callback()
