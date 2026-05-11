from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.frontend.icons import load_icon
from le_beta_vis.frontend.theme import FilterPipelinePanelColors as _Colors
from le_beta_vis.frontend.viewmodels.FilterStackViewModel import (
    FilterStackEntry,
    FilterStackViewModel,
)
from le_beta_vis.frontend.widgets._IconToggle import _IconToggle


class _FilterStackEntryView(QWidget):
    """One filter card inside the Filter Pipeline Panel.

    Composed of a dark caption strip (grabber + filter name +
    enabled toggle + delete button) and a light parameters body
    that flows read-only parameter pills.

    The view's *index* is the position passed at construction; the
    panel rebuilds entry views on every stack-shape change so the
    index stays fresh between mutations. Drag-reorder (Phase H)
    will use ``entry.id`` instead.
    """

    def __init__(
        self,
        vm: FilterStackViewModel,
        entry: FilterStackEntry,
        index: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        self._entry = entry
        self._index = index
        self._initUI()

    @property
    def entry_id(self) -> str:
        return self._entry.id

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._buildCaption())
        layout.addWidget(self._buildParametersBody())

    # --- Caption ---

    def _buildCaption(self) -> QWidget:
        caption = QWidget()
        caption.setStyleSheet(
            f"background-color: {_Colors.CARD_HEADER_BACKGROUND};"
        )
        row = QHBoxLayout(caption)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        grabber_color = (
            _Colors.GRABBER_ENABLED
            if self._entry.enabled
            else _Colors.GRABBER_DISABLED
        )
        self._grabber = QLabel()
        self._grabber.setPixmap(
            load_icon("grabber", grabber_color).pixmap(QSize(16, 16))
        )
        self._grabber.setCursor(Qt.OpenHandCursor)
        row.addWidget(self._grabber)

        name_color = (
            _Colors.FILTER_NAME_ENABLED
            if self._entry.enabled
            else _Colors.FILTER_NAME_DISABLED
        )
        spec = getattr(self._entry.filter, "SPEC", None)
        name_text = spec.display_name if spec is not None else type(
            self._entry.filter
        ).__name__
        name = QLabel(name_text)
        name.setStyleSheet(
            f"color: {name_color}; font-weight: bold; font-size: 14px;"
        )
        row.addWidget(name, 1)

        self._toggle = _IconToggle(
            off_icon=load_icon("toggle_off", _Colors.TOGGLE_OFF),
            on_icon=load_icon("toggle_on", _Colors.TOGGLE_ON),
            icon_size=QSize(40, 24),
        )
        self._toggle.setChecked(self._entry.enabled)
        self._toggle.toggled.connect(self._onToggleChanged)
        row.addWidget(self._toggle)

        self._delete_button = QToolButton()
        self._delete_button.setIcon(load_icon("delete", _Colors.DELETE_ICON))
        self._delete_button.setIconSize(QSize(18, 18))
        self._delete_button.setAutoRaise(True)
        self._delete_button.setCursor(Qt.PointingHandCursor)
        self._delete_button.setToolTip(self.tr("Remove filter"))
        self._delete_button.clicked.connect(self._onDeleteClicked)
        row.addWidget(self._delete_button)

        return caption

    # --- Parameters body ---

    def _buildParametersBody(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet(
            f"background-color: {_Colors.CARD_BODY_BACKGROUND};"
        )
        flow = _FlowLayout(body, margin=8, spacing=6)
        spec = getattr(self._entry.filter, "SPEC", None)
        text_color = (
            _Colors.PARAMETER_PILL_TEXT_ENABLED
            if self._entry.enabled
            else _Colors.PARAMETER_PILL_TEXT_DISABLED
        )
        if spec is not None:
            for param in spec.parameters:
                pill_text = self._pillText(param)
                pill = QLabel(pill_text)
                pill.setStyleSheet(
                    "QLabel {"
                    f" background-color: {_Colors.PARAMETER_PILL_BACKGROUND};"
                    f" color: {text_color};"
                    " padding: 3px 8px;"
                    " border-radius: 4px;"
                    " font-size: 11px;"
                    "}"
                )
                pill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                flow.addWidget(pill)
        return body

    def _pillText(self, param) -> str:
        value = getattr(self._entry.filter, param.name, None)
        if isinstance(value, float):
            value_text = f"{value:g}"
        else:
            value_text = str(value)
        units = f" {param.units}" if param.units else ""
        return f"{param.label}: {value_text}{units}"

    # --- Actions ---

    def _onToggleChanged(self, checked: bool) -> None:
        self._vm.set_filter_enabled(self._index, checked)

    def _onDeleteClicked(self) -> None:
        spec = getattr(self._entry.filter, "SPEC", None)
        display_name = spec.display_name if spec is not None else type(
            self._entry.filter
        ).__name__
        reply = QMessageBox.question(
            self,
            self.tr("Remove filter?"),
            self.tr("Remove '{name}' from the pipeline?").format(
                name=display_name
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vm.remove_filter(self._index)


class _FlowLayout(QLayout):
    """Wrapping horizontal layout — items flow left-to-right and wrap
    to a new row when they would overflow the available width.

    Adapted from the standard Qt FlowLayout example. Used here for the
    parameter-pill grid inside a filter card; extract to
    ``widgets/_FlowLayout.py`` if a second consumer appears.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        margin: int = 0,
        spacing: int = -1,
    ) -> None:
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list = []

    def __del__(self) -> None:
        while self._items:
            self.takeAt(0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._doLayout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _doLayout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        space = max(self.spacing(), 0)
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + space
            if next_x - space > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space
                next_x = x + hint.width() + space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()
