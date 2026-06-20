from typing import TYPE_CHECKING, Callable, List, Optional

from PySide6.QtCore import QMetaObject, QPoint
from PySide6.QtWidgets import QScrollArea, QWidget

from le_beta_vis.frontend.widgets.event_grid._EventGridSectionHeaderWidget import (
    EventGridSectionHeaderWidget,
)

if TYPE_CHECKING:
    from le_beta_vis.frontend.widgets.event_grid.EventGridWidget import _SectionRow


class _StickyHeaderOverlay:
    """Owns the floating section header that pins above the scroll area.

    Holds a live reference to the owning widget's ``_sections`` list
    rather than a copy, so it always reflects sections appended,
    inserted, or evicted after construction.
    """

    def __init__(
        self,
        parent: QWidget,
        sections: List["_SectionRow"],
        content_widget: QWidget,
        scroll_area: QScrollArea,
        header_height_getter: Callable[[], int],
        on_navigate: Callable[[int], None],
    ) -> None:
        self._parent = parent
        self._sections = sections
        self._content_widget = content_widget
        self._scroll_area = scroll_area
        self._header_height_getter = header_height_getter
        self._on_navigate = on_navigate

        self._widget = EventGridSectionHeaderWidget(parent=parent)
        self._widget.hide()
        self._widget.raise_()

        self._prev_conn: Optional[QMetaObject.Connection] = None
        self._next_conn: Optional[QMetaObject.Connection] = None
        self._self_conn: Optional[QMetaObject.Connection] = None

    def hide(self) -> None:
        self._widget.hide()

    def setFixedWidth(self, width: int) -> None:
        self._widget.setFixedWidth(width)

    def setFixedHeight(self, height: int) -> None:
        self._widget.setFixedHeight(height)

    def update(self) -> None:
        """Position the overlay based on the current scroll offset."""
        if not self._sections:
            self._widget.hide()
            return

        vp_h = self._scroll_area.viewport().height()
        content_h = self._content_widget.height()
        if content_h <= vp_h:
            self._widget.hide()
            return

        scroll_y = self._scroll_area.verticalScrollBar().value()
        active_idx = self._findActiveSectionIndex(scroll_y)
        if active_idx < 0:
            self._widget.hide()
            return

        self._position(active_idx, scroll_y)

    def _findActiveSectionIndex(self, scroll_y: int) -> int:
        """Return the index of the section whose header has scrolled past the top."""
        active = -1
        for i, row in enumerate(self._sections):
            header_y = row.header_widget.mapTo(self._content_widget, QPoint(0, 0)).y()
            if header_y <= scroll_y:
                active = i
            else:
                break
        return active

    def _position(self, active_idx: int, scroll_y: int) -> None:
        """Set the overlay text, geometry, navigation state, and visibility."""
        row = self._sections[active_idx]
        date = row.info.date_part if row.info.date_part else self._parent.tr("Unknown Date")
        file = row.info.file_part if row.info.file_part else self._parent.tr("Unknown File")
        self._widget.setDateText(date)
        self._widget.setFileText(file)
        self._widget.setFixedWidth(self._parent.width())

        self._reconnectSignals(active_idx)
        self._widget.setNavigationState(
            has_previous=active_idx > 0,
            has_next=active_idx < len(self._sections) - 1,
        )

        header_height = self._header_height_getter()
        y_pos = 0
        if active_idx + 1 < len(self._sections):
            next_header = self._sections[active_idx + 1].header_widget
            next_y = next_header.mapTo(self._content_widget, QPoint(0, 0)).y()
            push = next_y - scroll_y - header_height
            if push < 0:
                y_pos = push

        self._widget.move(0, max(-header_height, y_pos))
        self._widget.raise_()
        self._widget.show()

    def _reconnectSignals(self, active_idx: int) -> None:
        """Disconnect and reconnect overlay navigation signals."""
        if self._prev_conn is not None:
            self._widget.navigatePrevious.disconnect(self._prev_conn)
        if self._next_conn is not None:
            self._widget.navigateNext.disconnect(self._next_conn)
        if self._self_conn is not None:
            self._widget.navigateToSelf.disconnect(self._self_conn)

        self._prev_conn = self._widget.navigatePrevious.connect(
            lambda: self._on_navigate(active_idx - 1),
        )
        self._next_conn = self._widget.navigateNext.connect(
            lambda: self._on_navigate(active_idx + 1),
        )
        self._self_conn = self._widget.navigateToSelf.connect(
            lambda: self._on_navigate(active_idx),
        )
