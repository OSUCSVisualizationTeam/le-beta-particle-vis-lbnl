from typing import TYPE_CHECKING, Callable, List

from PySide6.QtGui import QStandardItem

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionGrouping import (
    EvictionResult,
    SectionInfo,
    evict_back_sections,
    evict_front_sections,
    merge_or_append_sections,
    merge_or_prepend_sections,
)

if TYPE_CHECKING:
    from le_beta_vis.frontend.widgets.event_grid.EventGridWidget import _SectionRow


class _SlidingWindowPager:
    """Applies append/prepend/evict diffs to the resident section window.

    Holds a live reference to the owning widget's ``_sections`` list
    rather than a copy, so every operation reflects the current
    window. Section construction/removal is delegated back to the
    owning widget via injected callables, since that logic also
    builds the per-row Qt widgets (``QListView``, header) that this
    pager has no reason to know how to construct.
    """

    def __init__(
        self,
        sections: List["_SectionRow"],
        header_height_getter: Callable[[], int],
        compute_list_view_height: Callable[[int], int],
        build_item: Callable[[Cluster], QStandardItem],
        add_section: Callable[[SectionInfo, List[Cluster], int], None],
        insert_section_at_front: Callable[[SectionInfo, List[Cluster], int], None],
    ) -> None:
        self._sections = sections
        self._header_height_getter = header_height_getter
        self._compute_list_view_height = compute_list_view_height
        self._build_item = build_item
        self._add_section = add_section
        self._insert_section_at_front = insert_section_at_front

    def _windowEnd(self) -> int:
        """Global index one past the last currently-resident cluster."""
        if not self._sections:
            return 0
        last = self._sections[-1].info
        return last.start_index + last.count

    def append(self, new_events: List[Cluster]) -> None:
        """Merges a newly-fetched page into the tail of the window."""
        window_end = self._windowEnd()
        existing_infos = [row.info for row in self._sections]
        merged = merge_or_append_sections(existing_infos, new_events, window_end)
        self._applyAppendDiff(merged, new_events, window_end)

    def _applyAppendDiff(
        self,
        merged: List[SectionInfo],
        new_events: List[Cluster],
        window_end: int,
    ) -> None:
        """Updates widgets/models to match a freshly append-merged section list."""
        old_count = len(self._sections)
        if old_count > 0:
            old_info = self._sections[-1].info
            new_info = merged[old_count - 1]
            if new_info.count > old_info.count:
                added = new_info.count - old_info.count
                row = self._sections[-1]
                for cluster in new_events[:added]:
                    row.model.appendRow(self._build_item(cluster))
                row.info = new_info
                row.list_view.setFixedHeight(
                    self._compute_list_view_height(new_info.count),
                )

        for section_index in range(old_count, len(merged)):
            self._add_section(merged[section_index], new_events, window_end)

    def prepend(self, new_events: List[Cluster]) -> int:
        """Merges a newly-fetched page into the head of the window.

        Returns:
            Total pixel height added above the previously-first
            section, for scrollbar compensation.
        """
        window_start = self._sections[0].info.start_index if self._sections else 0
        chunk_offset = window_start - len(new_events)
        existing_infos = [row.info for row in self._sections]
        merged = merge_or_prepend_sections(existing_infos, new_events, chunk_offset)
        return self._applyPrependDiff(merged, new_events, chunk_offset)

    def _applyPrependDiff(
        self,
        merged: List[SectionInfo],
        new_events: List[Cluster],
        chunk_offset: int,
    ) -> int:
        """Updates widgets/models for a freshly prepend-merged section list."""
        old_count = len(self._sections)
        new_section_count = len(merged) - old_count
        added_height = 0

        if old_count > 0:
            old_info = self._sections[0].info
            new_info = merged[new_section_count]
            if new_info.count > old_info.count:
                added = new_info.count - old_info.count
                row = self._sections[0]
                old_height = row.list_view.height()
                prepended = new_events[len(new_events) - added:]
                for offset, cluster in enumerate(prepended):
                    row.model.insertRow(offset, self._build_item(cluster))
                row.info = new_info
                new_height = self._compute_list_view_height(new_info.count)
                row.list_view.setFixedHeight(new_height)
                added_height += new_height - old_height

        for i in range(new_section_count - 1, -1, -1):
            info = merged[i]
            self._insert_section_at_front(info, new_events, chunk_offset)
            added_height += self._header_height_getter() + \
                self._compute_list_view_height(info.count)

        return added_height

    def evictFront(self, global_count: int) -> int:
        """Removes leading rows; returns removed pixel height."""
        if not self._sections:
            return 0
        existing_infos = [row.info for row in self._sections]
        result = evict_front_sections(existing_infos, global_count)
        return self._removeLeadingRows(result)

    def _removeLeadingRows(self, result: EvictionResult) -> int:
        """Applies a front-eviction result; returns removed pixel height."""
        removed_height = 0
        for _ in range(result.removed_section_count):
            row = self._sections.pop(0)
            removed_height += self._header_height_getter() + row.list_view.height()
            row.header_widget.setParent(None)
            row.list_view.setParent(None)
            row.header_widget.deleteLater()
            row.list_view.deleteLater()

        if result.boundary_partially_trimmed and self._sections:
            row = self._sections[0]
            old_height = row.list_view.height()
            new_info = result.sections[0]
            trimmed = row.info.count - new_info.count
            row.model.removeRows(0, trimmed)
            row.info = new_info
            new_height = self._compute_list_view_height(new_info.count)
            row.list_view.setFixedHeight(new_height)
            removed_height += old_height - new_height

        return removed_height

    def evictBack(self, global_count: int) -> None:
        """Removes trailing rows."""
        if not self._sections:
            return
        existing_infos = [row.info for row in self._sections]
        result = evict_back_sections(existing_infos, global_count)
        self._removeTrailingRows(result)

    def _removeTrailingRows(self, result: EvictionResult) -> None:
        """Applies a back-eviction result."""
        for _ in range(result.removed_section_count):
            row = self._sections.pop()
            row.header_widget.setParent(None)
            row.list_view.setParent(None)
            row.header_widget.deleteLater()
            row.list_view.deleteLater()

        if result.boundary_partially_trimmed and self._sections:
            row = self._sections[-1]
            new_info = result.sections[-1]
            trimmed = row.info.count - new_info.count
            row.model.removeRows(new_info.count, trimmed)
            row.info = new_info
            row.list_view.setFixedHeight(self._compute_list_view_height(new_info.count))
