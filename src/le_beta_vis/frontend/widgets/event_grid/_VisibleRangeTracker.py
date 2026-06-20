import math
from typing import TYPE_CHECKING, Callable, List

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtWidgets import QScrollArea, QWidget

if TYPE_CHECKING:
    from le_beta_vis.frontend.widgets.event_grid.EventGridWidget import _SectionRow

_DEBOUNCE_INTERVAL_MS = 50


class _VisibleRangeTracker:
    """Debounces scroll/resize/show/paint events into a single
    ``visibleRangeChanged`` emission, and maps scroll offsets to flat
    cluster indices.

    Holds a live reference to the owning widget's ``_sections`` list
    rather than a copy, so flat-index lookups always reflect sections
    appended, inserted, or evicted after construction.
    """

    def __init__(
        self,
        parent: QObject,
        sections: List["_SectionRow"],
        content_widget: QWidget,
        scroll_area: QScrollArea,
        item_width_getter: Callable[[], int],
        item_height_getter: Callable[[], int],
        max_cols_getter: Callable[[], int],
        header_height_getter: Callable[[], int],
        on_range_changed: Callable[[int, int], None],
    ) -> None:
        self._sections = sections
        self._content_widget = content_widget
        self._scroll_area = scroll_area
        self._item_width_getter = item_width_getter
        self._item_height_getter = item_height_getter
        self._max_cols_getter = max_cols_getter
        self._header_height_getter = header_height_getter
        self._on_range_changed = on_range_changed

        self._leadingTimer = QTimer(parent)
        self._leadingTimer.setSingleShot(True)
        self._leadingTimer.setInterval(_DEBOUNCE_INTERVAL_MS)
        self._leadingTimer.timeout.connect(self._emitVisibleRange)

        self._trailingTimer = QTimer(parent)
        self._trailingTimer.setSingleShot(True)
        self._trailingTimer.setInterval(_DEBOUNCE_INTERVAL_MS)
        self._trailingTimer.timeout.connect(self._emitVisibleRange)

    def scheduleCheck(self) -> None:
        """Schedule visible-range emission with leading + trailing edge debounce."""
        if not self._leadingTimer.isActive():
            self._leadingTimer.start()
        self._trailingTimer.start()

    def _emitVisibleRange(self) -> None:
        """Calculate the visible item range and emit it via the callback."""
        if not self._sections:
            return
        vp_h = self._scroll_area.viewport().height()
        if vp_h <= 0:
            return

        scroll_y = self._scroll_area.verticalScrollBar().value()
        first = self._flatIndexAtY(scroll_y)
        last = self._flatIndexAtY(scroll_y + vp_h)
        self._on_range_changed(first, last)

    def _flatIndexAtY(self, y: int) -> int:
        """Map a content-widget Y coordinate to the closest flat event index."""
        if not self._sections:
            return 0

        grid_w = self._item_width_getter()
        grid_h = self._item_height_getter()
        max_cols = self._max_cols_getter()
        header_height = self._header_height_getter()
        content_w = self._content_widget.width()
        cols = min(max(1, content_w // grid_w), max_cols) if content_w > 0 else 1
        total = self._sections[-1].info.start_index + self._sections[-1].info.count

        for row in self._sections:
            header_y = row.header_widget.mapTo(
                self._content_widget, QPoint(0, 0),
            ).y()
            section_top = header_y + header_height
            section_h = row.list_view.height()
            section_bottom = section_top + section_h

            if y < section_top:
                return row.info.start_index
            if y < section_bottom:
                local_y = y - section_top
                local_row = min(local_y // grid_h, math.ceil(row.info.count / cols) - 1)
                local_idx = min(int(local_row * cols), row.info.count - 1)
                return row.info.start_index + local_idx

        return max(0, total - 1)
