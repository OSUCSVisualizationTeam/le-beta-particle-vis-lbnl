import decimal
from typing import Any, Callable, Optional

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QIntValidator, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.filter_pipeline import (
    ParameterSpec,
    ParameterType,
    UIHint,
)
from le_beta_vis.frontend.theme import FilterPipelinePanelColors as _Colors


_DEFAULT_SLIDER_STEPS = 1000


class _FilterParameterPopover(QFrame):
    """Modeless popover for editing one filter parameter.

    Parented to the host top-level window (intentionally NOT a
    ``Qt.Popup`` top-level) so dismissal behaviour is predictable on
    macOS — Spaces, focus loss, and the Dock won't interact with it
    the way they do with native popups. Dismisses on Esc, click
    outside its own bounds, or focus loss to a different top-level.

    Emits :attr:`valueChanged` continuously while the user edits — the
    panel routes this to :meth:`FilterStackViewModel.set_filter_parameter`
    so the render fires live as the user drags.
    """

    valueChanged = Signal(object)
    dismissed = Signal()

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__(parent_window)
        self.setVisible(False)
        self.setObjectName("filterParameterPopover")
        self.setFrameShape(QFrame.StyledPanel)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "#filterParameterPopover {"
            f"  background-color: {_Colors.POPOVER_BACKGROUND};"
            f"  border: 1px solid {_Colors.POPOVER_BORDER};"
            "  border-radius: 6px;"
            "}"
            f"QSlider::groove:horizontal {{"
            f"  background: {_Colors.POPOVER_CONTROL_BACKGROUND};"
            "  height: 4px; border-radius: 2px;"
            "}}"
            f"QSlider::handle:horizontal {{"
            f"  background: {_Colors.POPOVER_CONTROL_FOREGROUND};"
            "  width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;"
            "}}"
            f"QDoubleSpinBox, QSpinBox, QLineEdit {{"
            f"  background-color: {_Colors.POPOVER_CONTROL_BACKGROUND};"
            f"  color: {_Colors.POPOVER_CONTROL_FOREGROUND};"
            f"  border: 1px solid {_Colors.POPOVER_BORDER};"
            "  border-radius: 3px; padding: 2px;"
            "}}"
            f"QComboBox {{"
            f"  background-color: {_Colors.POPOVER_CONTROL_BACKGROUND};"
            f"  color: {_Colors.POPOVER_CONTROL_FOREGROUND};"
            f"  border: 1px solid {_Colors.POPOVER_BORDER}; border-radius: 3px;"
            "}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: {_Colors.ADD_FILTER_MENU_BACKGROUND};"
            f"  color: {_Colors.POPOVER_CONTROL_FOREGROUND};"
            "}}"
        )
        self._spec: Optional[ParameterSpec] = None
        self._editor_widget: Optional[QWidget] = None
        self._external_setter: Optional[Callable[[Any], None]] = None
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(10, 8, 10, 8)
        self._outer.setSpacing(6)

    # --- Public API ---

    def show_for(
        self,
        spec: ParameterSpec,
        current_value: Any,
        anchor: QWidget,
    ) -> None:
        """Build the editor for *spec*, anchor next to *anchor*, show.

        The anchor widget is used only for position calculation; the
        popover does not hold a reference to it (so rebuilds of the
        anchor are safe while the popover is open).
        """
        self._spec = spec
        self._buildEditor(spec, current_value)
        self.adjustSize()
        self._positionNear(anchor)
        self.show()
        self.raise_()
        self.setFocus(Qt.PopupFocusReason)
        QApplication.instance().installEventFilter(self)

    def hide_popover(self) -> None:
        """Dismiss the popover. Idempotent."""
        if not self.isVisible():
            return
        QApplication.instance().removeEventFilter(self)
        self.hide()
        self.dismissed.emit()

    def set_external_value(self, value: Any) -> None:
        """Update the open editor in response to an out-of-band change.

        Used when another control (e.g. VerticalRangeControl) edits the
        same underlying parameter while the popover is open. Writes to
        the editor widget with signals blocked so the change does not
        re-emit ``valueChanged`` and create a feedback loop.

        No-op when the popover isn't currently showing an editor.
        """
        if self._external_setter is None:
            return
        self._external_setter(value)

    # --- Editor construction ---

    def _buildEditor(
        self, spec: ParameterSpec, current_value: Any
    ) -> None:
        self._clearLayout()
        self._external_setter = None
        header = QLabel(f"<b>{spec.label}</b>")
        header.setStyleSheet(
            f"color: {_Colors.POPOVER_HEADER_TEXT}; font-size: 13px;"
        )
        self._outer.addWidget(header)

        editor = self._pickEditor(spec, current_value)
        self._editor_widget = editor
        self._outer.addWidget(editor)

    def _clearLayout(self) -> None:
        while self._outer.count():
            item = self._outer.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _pickEditor(
        self, spec: ParameterSpec, value: Any
    ) -> QWidget:
        if spec.type == ParameterType.ENUM:
            return self._buildEnumEditor(spec, value)
        if spec.type == ParameterType.INT:
            return self._buildIntEditor(spec, value)
        # FLOAT
        bounded = spec.min_value is not None and spec.max_value is not None
        hint = spec.ui_hint
        if hint == UIHint.SPINBOX_ONLY or (hint == UIHint.AUTO and not bounded):
            return self._buildUnboundedFloatEditor(spec, value)
        if hint == UIHint.SLIDER_ONLY:
            return self._buildSliderOnlyFloatEditor(spec, value)
        # AUTO bounded or COMPOSE
        return self._buildBoundedFloatEditor(spec, value)

    # --- Bounded float (slider + spinbox composite) ---

    def _buildBoundedFloatEditor(
        self, spec: ParameterSpec, value: float
    ) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(_DEFAULT_SLIDER_STEPS)
        slider.setMinimumWidth(180)

        spinbox = QDoubleSpinBox()
        spinbox.setRange(spec.min_value, spec.max_value)
        spinbox.setSingleStep(spec.step or 0.1)
        spinbox.setDecimals(self._decimalsForStep(spec.step))
        spinbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        clamped = spec.clamp(value)
        spinbox.setValue(clamped)
        slider.setValue(self._toSliderValue(clamped, spec))

        def on_slider_changed(s_value: int) -> None:
            new_value = self._fromSliderValue(s_value, spec)
            spinbox.blockSignals(True)
            spinbox.setValue(new_value)
            spinbox.blockSignals(False)
            self.valueChanged.emit(spec.clamp(new_value))

        def on_spinbox_changed(v: float) -> None:
            slider.blockSignals(True)
            slider.setValue(self._toSliderValue(v, spec))
            slider.blockSignals(False)
            self.valueChanged.emit(spec.clamp(v))

        slider.valueChanged.connect(on_slider_changed)
        spinbox.valueChanged.connect(on_spinbox_changed)

        def set_external(v: Any) -> None:
            try:
                clamped = spec.clamp(float(v))
            except (TypeError, ValueError):
                return
            spinbox.blockSignals(True)
            spinbox.setValue(clamped)
            spinbox.blockSignals(False)
            slider.blockSignals(True)
            slider.setValue(self._toSliderValue(clamped, spec))
            slider.blockSignals(False)

        self._external_setter = set_external

        row.addWidget(slider, 1)
        row.addWidget(spinbox)
        return container

    def _buildSliderOnlyFloatEditor(
        self, spec: ParameterSpec, value: float
    ) -> QWidget:
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(_DEFAULT_SLIDER_STEPS)
        slider.setMinimumWidth(220)
        slider.setValue(self._toSliderValue(spec.clamp(value), spec))

        def on_changed(s_value: int) -> None:
            v = self._fromSliderValue(s_value, spec)
            self.valueChanged.emit(spec.clamp(v))

        slider.valueChanged.connect(on_changed)

        def set_external(v: Any) -> None:
            try:
                clamped = spec.clamp(float(v))
            except (TypeError, ValueError):
                return
            slider.blockSignals(True)
            slider.setValue(self._toSliderValue(clamped, spec))
            slider.blockSignals(False)

        self._external_setter = set_external
        return slider

    # --- Unbounded float (spinbox with wide practical range) ---

    def _buildUnboundedFloatEditor(
        self, spec: ParameterSpec, value: float
    ) -> QWidget:
        spinbox = QDoubleSpinBox()
        lo = float(spec.min_value) if spec.min_value is not None else -1e15
        hi = float(spec.max_value) if spec.max_value is not None else 1e15
        spinbox.setRange(lo, hi)
        spinbox.setSingleStep(spec.step if spec.step is not None else 0.1)
        spinbox.setDecimals(self._decimalsForStep(spec.step))
        spinbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        spinbox.setValue(float(value))

        spinbox.valueChanged.connect(lambda v: self.valueChanged.emit(v))

        def set_external(v: Any) -> None:
            try:
                spinbox.blockSignals(True)
                spinbox.setValue(float(v))
            except (TypeError, ValueError):
                pass
            finally:
                spinbox.blockSignals(False)

        self._external_setter = set_external
        return spinbox

    # --- Int / Enum ---

    def _buildIntEditor(
        self, spec: ParameterSpec, value: int
    ) -> QWidget:
        if spec.min_value is not None and spec.max_value is not None:
            return self._buildBoundedIntEditor(spec, value)
        return self._buildUnboundedIntEditor(spec, value)

    def _buildBoundedIntEditor(
        self, spec: ParameterSpec, value: int
    ) -> QWidget:
        spinbox = QSpinBox()
        spinbox.setRange(int(spec.min_value), int(spec.max_value))
        if spec.step is not None:
            spinbox.setSingleStep(int(spec.step))
        spinbox.setValue(int(spec.clamp(value)))
        spinbox.valueChanged.connect(
            lambda v: self.valueChanged.emit(spec.clamp(v))
        )

        def set_external(v: Any) -> None:
            try:
                spinbox.blockSignals(True)
                spinbox.setValue(int(spec.clamp(v)))
            except (TypeError, ValueError):
                pass
            finally:
                spinbox.blockSignals(False)

        self._external_setter = set_external
        return spinbox

    def _buildUnboundedIntEditor(
        self, spec: ParameterSpec, value: int
    ) -> QWidget:
        edit = QLineEdit()
        edit.setText(str(int(value)))
        edit.setValidator(QIntValidator())
        edit.setMinimumWidth(120)

        def on_edited(text: str) -> None:
            try:
                v = int(text)
            except ValueError:
                return
            self.valueChanged.emit(spec.clamp(v))

        edit.textEdited.connect(on_edited)

        def set_external(v: Any) -> None:
            try:
                edit.blockSignals(True)
                edit.setText(str(int(v)))
            except (TypeError, ValueError):
                pass
            finally:
                edit.blockSignals(False)

        self._external_setter = set_external
        return edit

    def _buildEnumEditor(
        self, spec: ParameterSpec, value: Any
    ) -> QWidget:
        combo = QComboBox()
        values = list(spec.enum_values or [])
        combo.addItems(values)
        # Enum members compare equal to their `.value` string under
        # str-Enum, but str(member) renders as "ClassName.MEMBER" which
        # isn't in the items list — write the .value when present.
        current_text = value.value if hasattr(value, "value") else str(value)
        if current_text in values:
            combo.setCurrentText(current_text)
        combo.currentTextChanged.connect(
            lambda text: self.valueChanged.emit(text)
        )

        def set_external(v: Any) -> None:
            text = v.value if hasattr(v, "value") else str(v)
            if text in values:
                combo.blockSignals(True)
                combo.setCurrentText(text)
                combo.blockSignals(False)

        self._external_setter = set_external
        return combo

    # --- Slider <-> value helpers ---

    @staticmethod
    def _toSliderValue(value: float, spec: ParameterSpec) -> int:
        denom = (spec.max_value or 0) - (spec.min_value or 0)
        if denom <= 0:
            return 0
        ratio = (value - spec.min_value) / denom
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * _DEFAULT_SLIDER_STEPS))

    @staticmethod
    def _fromSliderValue(s_value: int, spec: ParameterSpec) -> float:
        denom = (spec.max_value or 0) - (spec.min_value or 0)
        if denom <= 0:
            return spec.min_value if spec.min_value is not None else 0.0
        return spec.min_value + (s_value / _DEFAULT_SLIDER_STEPS) * denom

    @staticmethod
    def _decimalsForStep(step: Optional[float]) -> int:
        if step is None or step >= 1:
            return 2
        try:
            exponent = decimal.Decimal(str(step)).as_tuple().exponent
        except (decimal.InvalidOperation, TypeError):
            return 2
        return max(-int(exponent), 0)

    # --- Dismissal ---

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide_popover()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if not self.isVisible():
            return super().eventFilter(obj, event)
        if event.type() == QEvent.MouseButtonPress:
            # An open Qt.Popup top-level (e.g. a QComboBox dropdown
            # belonging to one of our own editors) consumes mouse
            # presses outside our QFrame's rect. Without this guard,
            # picking an item from the combo would dismiss the popover
            # before the combo could register the selection.
            active_popup = QApplication.activePopupWidget()
            if active_popup is not None and active_popup is not self:
                return super().eventFilter(obj, event)
            global_pos = self._globalPosOf(event)
            if global_pos is None:
                return super().eventFilter(obj, event)
            local = self.mapFromGlobal(global_pos)
            if not self.rect().contains(local):
                self.hide_popover()
                # Don't consume — let the click reach its target
        return super().eventFilter(obj, event)

    @staticmethod
    def _globalPosOf(event) -> Optional[QPoint]:
        # Qt6: globalPosition().toPoint(); Qt5: globalPos()
        gp = getattr(event, "globalPosition", None)
        if gp is not None:
            try:
                return gp().toPoint()
            except TypeError:
                pass
        return getattr(event, "globalPos", lambda: None)()

    # --- Positioning ---

    def _positionNear(self, anchor: QWidget) -> None:
        """Anchor below the pill by default, flipping to fit the screen.

        Coordinates: anchor → global → parent-local. The popover is
        a child of the top-level window, so its position is in window
        coordinates."""
        anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(anchor_top_left, anchor.size())
        popover_size = self.sizeHint()

        target = QPoint(anchor_rect.left(), anchor_rect.bottom() + 4)

        screen = self.window().screen() if self.window() is not None else None
        if screen is not None:
            screen_rect = screen.availableGeometry()
            if target.x() + popover_size.width() > screen_rect.right():
                target.setX(
                    max(
                        screen_rect.left(),
                        anchor_rect.right() - popover_size.width(),
                    )
                )
            if target.y() + popover_size.height() > screen_rect.bottom():
                flipped_top = anchor_rect.top() - popover_size.height() - 4
                target.setY(max(screen_rect.top(), flipped_top))

        parent = self.parentWidget()
        if parent is not None:
            target = parent.mapFromGlobal(target)
        self.move(target)
