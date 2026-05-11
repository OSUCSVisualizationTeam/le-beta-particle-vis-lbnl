from typing import List, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.FilterRegistry import BUILTIN_FILTERS
from le_beta_vis.common.FilterSpec import FilterSpec, ParameterSpec
from le_beta_vis.frontend.theme import FilterPipelinePanelColors as _Colors
from le_beta_vis.frontend.viewmodels.FilterStackViewModel import (
    FilterStackViewModel,
)

from ._FilterParameterPopover import _FilterParameterPopover
from ._FilterStackEntryView import (
    MIME_ENTRY_ID,
    _FilterStackEntryView,
)


_DROP_INDICATOR_COLOR = "#4FC3F7"


class FilterPipelinePanelView(QFrame):
    """Interactive Filter Stack UI hosted in the right sidebar's Vis tab.

    Renders the active :class:`FilterStackViewModel` as a vertical list
    of filter cards inside a scrollable area, with an Add Filter menu
    and a counter showing enabled vs total filters.

    The panel rebuilds the list of entry views on every stack change.
    Per-entry parameter changes also fire the callback today; the panel
    rebuild is cheap and re-renders pill labels with current values.
    When the parameter popover lands (Phase G) the popover is owned by
    this panel, not by individual entry views, so rebuilds don't kill
    in-flight edits.
    """

    def __init__(
        self,
        viewModel: FilterStackViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._popover: Optional[_FilterParameterPopover] = None
        self._active_entry_id: Optional[str] = None
        self._active_param_name: Optional[str] = None
        self._initUI()
        self._bindViewModel()
        self._rebuild()

    # --- Setup ---

    def _initUI(self) -> None:
        self.setStyleSheet(
            f"FilterPipelinePanelView {{"
            f" background-color: {_Colors.PANEL_BACKGROUND};"
            f" border: 1px solid {_Colors.PANEL_BORDER};"
            f"}}"
            f"QToolTip {{"
            f" background-color: {_Colors.PILL_TOOLTIP_BACKGROUND};"
            f" color: {_Colors.PILL_TOOLTIP_TEXT};"
            f" border: 1px solid {_Colors.PILL_TOOLTIP_BORDER};"
            f" padding: 2px 4px;"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._buildTitle())
        layout.addWidget(self._buildScrollArea(), 1)
        layout.addWidget(self._buildBottomBar())

    def _buildTitle(self) -> QLabel:
        title = QLabel(self.tr("Filtering Pipeline"))
        title.setStyleSheet(
            f"color: {_Colors.TITLE_TEXT}; font-weight: bold;"
            " font-size: 14px; padding: 2px 4px;"
        )
        return title

    def _buildScrollArea(self) -> QScrollArea:
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {_Colors.SCROLL_AREA_BACKGROUND};"
            f" border: none; border-radius: 4px; }}"
            f"QWidget#filterPipelineScrollInner {{"
            f" background-color: {_Colors.SCROLL_AREA_BACKGROUND}; }}"
        )

        self._scroll_inner = _DropTargetContainer(self)
        self._scroll_inner.setObjectName("filterPipelineScrollInner")
        self._entries_layout = QVBoxLayout(self._scroll_inner)
        self._entries_layout.setContentsMargins(8, 8, 8, 8)
        self._entries_layout.setSpacing(8)

        self._empty_state = QLabel(
            self.tr("Pipeline is empty — filters are optional modifiers")
        )
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setWordWrap(True)
        self._empty_state.setStyleSheet(
            f"color: {_Colors.COUNTER_TEXT}; padding: 24px 8px;"
            " font-style: italic;"
        )
        self._entries_layout.addWidget(self._empty_state)
        self._entries_layout.addStretch(1)

        self._drop_indicator = QFrame(self._scroll_inner)
        self._drop_indicator.setFrameShape(QFrame.HLine)
        self._drop_indicator.setStyleSheet(
            f"background-color: {_DROP_INDICATOR_COLOR}; border: none;"
        )
        self._drop_indicator.setFixedHeight(2)
        self._drop_indicator.hide()

        self._scroll_area.setWidget(self._scroll_inner)
        return self._scroll_area

    def _buildBottomBar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(8)

        self._add_button = QPushButton(self.tr("Add Filter"))
        self._add_button.setCursor(Qt.PointingHandCursor)
        self._add_button.setStyleSheet(
            "QPushButton {"
            f" background-color: {_Colors.ADD_FILTER_BUTTON_BACKGROUND};"
            "  border: none; border-radius: 4px;"
            "  padding: 4px 12px; font-weight: bold; font-size: 11px;"
            "  color: black; }"
            "QPushButton::menu-indicator { image: none; width: 0; }"
        )
        self._add_button.setMenu(self._buildAddFilterMenu())
        row.addWidget(self._add_button)

        row.addStretch(1)

        self._counter = QLabel()
        self._counter.setStyleSheet(
            f"color: {_Colors.COUNTER_TEXT}; font-size: 10px;"
            " font-weight: bold;"
        )
        row.addWidget(self._counter)

        return bar

    def _buildAddFilterMenu(self) -> QMenu:
        menu = QMenu(self._add_button)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {_Colors.ADD_FILTER_MENU_BACKGROUND};"
            f" color: {_Colors.ADD_FILTER_MENU_TEXT};"
            f" border: 1px solid {_Colors.ADD_FILTER_MENU_BORDER}; }}"
            f"QMenu::item:selected {{ background-color: {_Colors.ADD_FILTER_MENU_HOVER}; }}"
            f"QMenu::item:disabled {{ color: {_Colors.ADD_FILTER_MENU_DISABLED_TEXT}; }}"
        )
        for spec in BUILTIN_FILTERS:
            self._addSpecAction(menu, spec)
        menu.addSeparator()
        coming_soon = QAction(self.tr("More filters coming soon"), menu)
        coming_soon.setEnabled(False)
        menu.addAction(coming_soon)
        return menu

    def _addSpecAction(self, menu: QMenu, spec: FilterSpec) -> None:
        action = QAction(spec.display_name, menu)
        action.triggered.connect(lambda _checked=False, s=spec: self._addFilter(s))
        menu.addAction(action)

    # --- ViewModel binding ---

    def _bindViewModel(self) -> None:
        self._vm.add_stack_changed_callback(self._rebuild)

    def _addFilter(self, spec: FilterSpec) -> None:
        if spec.filter_class is None:
            return
        self._vm.add_filter(spec.filter_class())

    # --- Rebuild ---

    def _rebuild(self) -> None:
        # Strip entry widgets (everything between empty_state at index 0
        # and the trailing stretch). takeAt(1) shifts the remaining
        # items down so the loop drains correctly.
        while self._entries_layout.count() > 2:
            item = self._entries_layout.takeAt(1)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        entries = self._vm.entries
        self._empty_state.setVisible(len(entries) == 0)

        for index, entry in enumerate(entries):
            view = _FilterStackEntryView(
                self._vm, entry, index, parent=self._scroll_inner
            )
            view.parameterClicked.connect(self._onParameterClicked)
            # Insert before the trailing stretch.
            self._entries_layout.insertWidget(
                self._entries_layout.count() - 1, view
            )

        self._updateCounter()

    def _updateCounter(self) -> None:
        total = len(self._vm.entries)
        enabled = len(self._vm.active_filters)
        if total == 0:
            self._counter.hide()
            return
        self._counter.setText(
            self.tr("{enabled}/{total} filters applied").format(
                enabled=enabled, total=total
            )
        )
        self._counter.show()

    # --- Parameter popover routing ---

    def _ensurePopover(self) -> _FilterParameterPopover:
        if self._popover is None:
            top_window = self.window()
            self._popover = _FilterParameterPopover(top_window)
            self._popover.valueChanged.connect(self._onPopoverValueChanged)
            self._popover.dismissed.connect(self._onPopoverDismissed)
        return self._popover

    def _onParameterClicked(
        self, entry_id: str, param_name: str, anchor: QWidget
    ) -> None:
        entries = self._vm.entries
        for entry in entries:
            if entry.id != entry_id:
                continue
            spec = self._findParameterSpec(entry.filter, param_name)
            if spec is None:
                return
            current_value = getattr(entry.filter, param_name, spec.default)
            self._active_entry_id = entry_id
            self._active_param_name = param_name
            popover = self._ensurePopover()
            popover.show_for(spec, current_value, anchor)
            return

    def _onPopoverValueChanged(self, value) -> None:
        if self._active_entry_id is None or self._active_param_name is None:
            return
        for index, entry in enumerate(self._vm.entries):
            if entry.id == self._active_entry_id:
                self._vm.set_filter_parameter(
                    index, self._active_param_name, value
                )
                return

    def _onPopoverDismissed(self) -> None:
        self._active_entry_id = None
        self._active_param_name = None

    @staticmethod
    def _findParameterSpec(
        filter_obj, param_name: str
    ) -> Optional[ParameterSpec]:
        spec = getattr(filter_obj, "SPEC", None)
        if spec is None:
            return None
        for param in spec.parameters:
            if param.name == param_name:
                return param
        return None

    # --- Drag-and-drop reorder ---

    def _entryWidgets(self) -> List[_FilterStackEntryView]:
        result: List[_FilterStackEntryView] = []
        for i in range(self._entries_layout.count()):
            item = self._entries_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, _FilterStackEntryView):
                result.append(widget)
        return result

    def _gapAtY(self, y: int) -> int:
        """Return the insertion gap index for cursor Y in scroll-inner coords.

        Gap 0 = before the first entry; gap N = after the last entry.
        """
        widgets = self._entryWidgets()
        for i, w in enumerate(widgets):
            mid = w.geometry().top() + w.height() // 2
            if y < mid:
                return i
        return len(widgets)

    def _showDropIndicatorAtGap(self, gap: int) -> None:
        widgets = self._entryWidgets()
        if not widgets:
            return
        if gap == 0:
            y = max(0, widgets[0].geometry().top() - 2)
        elif gap >= len(widgets):
            y = widgets[-1].geometry().bottom() + 1
        else:
            y = (
                widgets[gap - 1].geometry().bottom()
                + widgets[gap].geometry().top()
            ) // 2
        inner_width = self._scroll_inner.width()
        self._drop_indicator.setGeometry(
            8, y - 1, max(0, inner_width - 16), 2
        )
        self._drop_indicator.show()
        self._drop_indicator.raise_()

    def _hideDropIndicator(self) -> None:
        self._drop_indicator.hide()

    def _onDragMove(self, pos: QPoint) -> None:
        gap = self._gapAtY(pos.y())
        self._showDropIndicatorAtGap(gap)

    def _onDrop(self, entry_id: str, pos: QPoint) -> None:
        try:
            gap = self._gapAtY(pos.y())
            from_index: Optional[int] = None
            for i, entry in enumerate(self._vm.entries):
                if entry.id == entry_id:
                    from_index = i
                    break
            if from_index is None:
                return
            # Translate visual gap to a post-removal insertion index.
            # When dragging down (from < gap) the source row is removed
            # before the destination is computed, so the target shifts
            # left by one. When dragging up (from >= gap) no shift.
            to_index = gap - 1 if from_index < gap else gap
            self._vm.move_filter_by_id(entry_id, to_index)
        finally:
            self._hideDropIndicator()

    def _onDragLeave(self) -> None:
        self._hideDropIndicator()


class _DropTargetContainer(QWidget):
    """Inner widget for the scroll area that accepts entry-id drops.

    Delegates the actual reorder logic back to the host
    :class:`FilterPipelinePanelView` so the drag callbacks live next
    to the rest of the panel state.
    """

    def __init__(
        self,
        panel: FilterPipelinePanelView,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._panel = panel
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(MIME_ENTRY_ID):
            event.setDropAction(Qt.MoveAction)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if not event.mimeData().hasFormat(MIME_ENTRY_ID):
            event.ignore()
            return
        event.setDropAction(Qt.MoveAction)
        event.acceptProposedAction()
        self._panel._onDragMove(event.position().toPoint())

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._panel._onDragLeave()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(MIME_ENTRY_ID):
            event.ignore()
            return
        raw = bytes(event.mimeData().data(MIME_ENTRY_ID).data())
        entry_id = raw.decode("utf-8", errors="replace")
        event.setDropAction(Qt.MoveAction)
        event.acceptProposedAction()
        self._panel._onDrop(entry_id, event.position().toPoint())
