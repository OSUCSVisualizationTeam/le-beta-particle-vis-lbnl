from typing import Dict, Optional

from shiboken6 import isValid
from PySide6.QtCore import QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.FilterSpec import ParameterSpec
from le_beta_vis.frontend.icons import load_icon
from le_beta_vis.frontend.theme import FilterPipelinePanelColors as _Colors
from le_beta_vis.frontend.viewmodels.FilterStackViewModel import (
    FilterStackEntry,
    FilterStackViewModel,
)
from le_beta_vis.frontend.widgets._IconToggle import _IconToggle


MIME_ENTRY_ID = "application/x-lbnlvis-filter-entry-id"


class _FilterStackEntryView(QWidget):
    """One filter card inside the Filter Pipeline Panel.

    Composed of a dark caption strip (grabber + filter name +
    enabled toggle + delete button) and a light parameters body
    that flows read-only parameter pills.

    The view's *index* is the position passed at construction; the
    panel rebuilds entry views on every stack-shape change so the
    index stays fresh between mutations. Drag-reorder (Phase H)
    will use ``entry.id`` instead.

    Emits :attr:`parameterClicked(entry_id, param_name, anchor)` when
    the user clicks a parameter pill. The panel routes this to the
    shared :class:`_FilterParameterPopover` for live editing.
    """

    parameterClicked = Signal(str, str, QWidget)

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
        self._pills: Dict[str, "_ClickableLabel"] = {}
        self._initUI()

    @property
    def entry_id(self) -> str:
        return self._entry.id

    @property
    def enabled(self) -> bool:
        return self._entry.enabled

    def refresh_pills(self, entry: FilterStackEntry) -> None:
        """Update pill text in place against the latest entry state.

        Called by :class:`FilterPipelinePanelView` when only parameter
        values changed (no add / remove / move), so dragging the
        VerticalRangeControl can update vmin/vmax labels at slider
        cadence without tearing down and rebuilding the whole card
        tree on every tick.
        """
        self._entry = entry
        spec = getattr(self._entry.filter, "SPEC", None)
        if spec is None:
            return
        for param in spec.parameters:
            pill = self._pills.get(param.name)
            if pill is not None:
                pill.setText(self._pillText(param))

    def _initUI(self) -> None:
        self.setStyleSheet(
            f"_FilterStackEntryView {{ background-color: {_Colors.SCROLL_AREA_BACKGROUND}; }}"
        )
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
            " border-top-left-radius: 6px; border-top-right-radius: 6px;"
        )
        row = QHBoxLayout(caption)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        row.addWidget(self._buildHandle())

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

        if not self._entry.pinned:
            self._toggle = _IconToggle(
                off_icon=load_icon("toggle_off", _Colors.TOGGLE_OFF),
                on_icon=load_icon("toggle_on", _Colors.TOGGLE_ON),
                icon_size=QSize(40, 24),
            )
            self._toggle.setChecked(self._entry.enabled)
            self._toggle.toggled.connect(self._onToggleChanged)
            row.addWidget(self._toggle)

            self._delete_button = QToolButton()
            self._delete_button.setIcon(
                load_icon("delete", _Colors.DELETE_ICON)
            )
            self._delete_button.setIconSize(QSize(18, 18))
            self._delete_button.setAutoRaise(True)
            self._delete_button.setCursor(Qt.PointingHandCursor)
            self._delete_button.setToolTip(self.tr("Remove filter"))
            self._delete_button.clicked.connect(self._onDeleteClicked)
            row.addWidget(self._delete_button)

        return caption

    def _buildHandle(self) -> QWidget:
        """Drag grabber for user filters; static pin marker for pinned.

        Pinned cards cannot be reordered or removed, so the handle is a
        non-interactive label — no drag start, no pointer cursor — and
        uses the disabled grabber color to read as "fixed in place".
        """
        if self._entry.pinned:
            handle = QLabel()
            handle.setPixmap(
                load_icon("grabber", _Colors.GRABBER_DISABLED)
                .pixmap(QSize(16, 16))
            )
            handle.setToolTip(self.tr("Pinned — required by the pipeline"))
            return handle

        grabber_color = (
            _Colors.GRABBER_ENABLED
            if self._entry.enabled
            else _Colors.GRABBER_DISABLED
        )
        self._grabber = _DragHandle(self._entry.id)
        self._grabber.setPixmap(
            load_icon("grabber", grabber_color).pixmap(QSize(16, 16))
        )
        return self._grabber

    # --- Parameters body ---

    def _buildParametersBody(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet(
            f"background-color: {_Colors.CARD_BODY_BACKGROUND};"
            " border-bottom-left-radius: 6px; border-bottom-right-radius: 6px;"
        )
        flow = _FlowLayout(body, margin=10, spacing=8)
        spec = getattr(self._entry.filter, "SPEC", None)
        text_color = (
            _Colors.PARAMETER_PILL_TEXT_ENABLED
            if self._entry.enabled
            else _Colors.PARAMETER_PILL_TEXT_DISABLED
        )
        if spec is not None:
            for param in spec.parameters:
                pill = self._buildParameterPill(param, text_color)
                self._pills[param.name] = pill
                flow.addWidget(pill)
        return body

    def _buildParameterPill(
        self, param: ParameterSpec, text_color: str
    ) -> QWidget:
        pill = _ClickableLabel(self._pillText(param))
        pill.setStyleSheet(
            "QLabel {"
            f" background-color: {_Colors.PARAMETER_PILL_BACKGROUND};"
            f" color: {text_color};"
            " margin: 4px;"
            " padding: 3px 8px;"
            f" border: 1px solid {_Colors.PARAMETER_PILL_BORDER};"
            " border-radius: 4px;"
            " font-size: 11px;"
            " font-family: Menlo, Consolas, \"DejaVu Sans Mono\","
            " monospace;"
            "}"
            "QLabel:hover {"
            f" background-color: {_Colors.PARAMETER_PILL_HOVER_BACKGROUND};"
            "}"
        )
        pill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pill.setCursor(Qt.PointingHandCursor)
        pill.setToolTip(self.tr("Click to edit"))
        pill.clicked.connect(
            lambda p=pill, name=param.name: self.parameterClicked.emit(
                self._entry.id, name, p
            )
        )
        return pill

    def _pillText(self, param) -> str:
        value = getattr(self._entry.filter, param.name, None)
        if isinstance(value, float):
            value_text = f"{value:g}"
        elif hasattr(value, "value"):
            # Enum members: render the underlying value, not the
            # "ClassName.MEMBER" repr that str() produces in Py3.10.
            value_text = str(value.value)
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


class _ClickableLabel(QLabel):
    """A QLabel that emits ``clicked`` on a left mouse press.

    Used for parameter pills — QLabel doesn't expose a click signal,
    and a QPushButton brings unwanted chrome at the pill density we
    want. A small subclass is cleaner than installing event filters.
    """

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class _DragHandle(QLabel):
    """The grabber icon at the left of each filter card.

    On a left-click-and-drag, starts a :class:`QDrag` carrying the
    parent entry's ``id`` via the :data:`MIME_ENTRY_ID` mime type.
    Uses :data:`Qt.MoveAction` explicitly so macOS doesn't render a
    green ``+`` "copy" badge during the drag.
    """

    def __init__(self, entry_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._entry_id = entry_id
        self._press_pos: Optional[QPoint] = None
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is None:
            return
        if (event.buttons() & Qt.LeftButton) == 0:
            return
        delta = (event.pos() - self._press_pos).manhattanLength()
        if delta < QApplication.startDragDistance():
            return
        self._beginDrag()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._press_pos = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def _beginDrag(self) -> None:
        mime = QMimeData()
        mime.setData(MIME_ENTRY_ID, self._entry_id.encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        # Render the parent card as the drag preview so the user sees
        # what they're moving — falls back to a default cursor if the
        # parent geometry isn't available yet.
        parent = self.parent()
        while parent is not None and not isinstance(parent, QWidget):
            parent = parent.parent()
        card = self._findCard(parent)
        if card is not None:
            preview = card.grab()
            drag.setPixmap(preview)
            drag.setHotSpot(self.mapTo(card, self.rect().center()))
        QApplication.setOverrideCursor(Qt.ClosedHandCursor)
        # Qt.MoveAction explicitly — no green-plus copy badge on macOS.
        drag.exec(Qt.MoveAction)
        QApplication.restoreOverrideCursor()
        # The reorder drop handler may have deleted this widget's C++ object
        # before exec() returns — guard before touching self.
        if not isValid(self):
            return
        self._press_pos = None
        self.setCursor(Qt.OpenHandCursor)

    @staticmethod
    def _findCard(widget: Optional[QWidget]) -> Optional[QWidget]:
        node = widget
        while node is not None:
            if isinstance(node, _FilterStackEntryView):
                return node
            node = node.parent() if isinstance(node, QWidget) else None
        return None
