import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from le_beta_vis.common.VizFilter import UniformVizFilter


@dataclass
class FilterStackEntry:
    """One slot in the Interactive Filter Stack.

    Pairs a :class:`UniformVizFilter` with a UI-toggleable ``enabled``
    flag and a stable ``id``. When disabled the filter is skipped at
    render time without leaving the stack — so toggling preserves
    position.

    The ``id`` is a UUID hex string that survives reordering and is
    used by drag-and-drop to identify which entry is being moved
    (index-based identity breaks mid-drag when other rows shift).
    """

    filter: UniformVizFilter
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


class FilterStackViewModel:
    """ViewModel for the Interactive Filter Stack (issue #31).

    Owns the ordered list of :class:`UniformVizFilter` instances that
    sit between the Scale and Colormap stages of the render pipeline.
    Pure Python (no Qt) so it runs in headless CI.

    Observers register via :meth:`add_stack_changed_callback`; the
    callback fires after any mutation (add / remove / move / toggle /
    clear). The host ViewModel typically wires this to a render-request
    method so visual updates follow filter edits automatically.
    """

    def __init__(self) -> None:
        self._entries: List[FilterStackEntry] = []
        self._stack_changed_callbacks: List[Callable[[], None]] = []

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
        """
        return [entry.filter for entry in self._entries if entry.enabled]

    def add_filter(
        self, filt: UniformVizFilter, enabled: bool = True
    ) -> None:
        """Append *filt* to the end of the stack."""
        self._entries.append(FilterStackEntry(filter=filt, enabled=enabled))
        self._notify_stack_changed()

    def remove_filter(self, index: int) -> None:
        """Remove the filter at *index*.

        Out-of-range indices are silently ignored so UI flows that
        race with stack mutations don't have to guard every call.
        """
        if 0 <= index < len(self._entries):
            del self._entries[index]
            self._notify_stack_changed()

    def move_filter(self, from_index: int, to_index: int) -> None:
        """Move the filter at *from_index* to *to_index*.

        ``to_index`` is clamped to the valid range. Order matters at
        render time, so this is the primary mechanism for reordering
        the chain.
        """
        if not (0 <= from_index < len(self._entries)):
            return
        clamped_to = max(0, min(to_index, len(self._entries) - 1))
        if from_index == clamped_to:
            return
        entry = self._entries.pop(from_index)
        self._entries.insert(clamped_to, entry)
        self._notify_stack_changed()

    def set_filter_enabled(self, index: int, enabled: bool) -> None:
        """Toggle the enabled flag on the filter at *index*.

        The filter remains in the stack at its current position when
        disabled, so toggling does not perturb order.
        """
        if not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
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
        attributes (e.g. ``Gaussian.sigma`` rather than a
        name-mangled private). Out-of-range indices and missing
        attributes are no-ops to keep UI flows simple.

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
        """Remove every filter from the stack. No-op when empty."""
        if not self._entries:
            return
        self._entries.clear()
        self._notify_stack_changed()

    def add_stack_changed_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Register *callback* to fire after any mutation."""
        self._stack_changed_callbacks.append(callback)

    def _notify_stack_changed(self) -> None:
        for callback in self._stack_changed_callbacks:
            callback()
