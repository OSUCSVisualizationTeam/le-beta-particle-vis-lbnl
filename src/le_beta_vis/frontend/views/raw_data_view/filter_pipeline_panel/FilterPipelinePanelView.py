from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
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
from le_beta_vis.common.FilterSpec import FilterSpec
from le_beta_vis.frontend.theme import FilterPipelinePanelColors as _Colors
from le_beta_vis.frontend.viewmodels.FilterStackViewModel import (
    FilterStackViewModel,
)

from ._FilterStackEntryView import _FilterStackEntryView


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
            f" border-radius: 4px; }}"
            f"QWidget#filterPipelineScrollInner {{"
            f" background-color: {_Colors.SCROLL_AREA_BACKGROUND}; }}"
        )

        self._scroll_inner = QWidget()
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
