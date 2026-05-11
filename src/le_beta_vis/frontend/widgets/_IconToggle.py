from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class _IconToggle(QWidget):
    """A two-state toggle button rendered from a pair of icons.

    Renders ``off_icon`` when unchecked and ``on_icon`` when checked.
    A left-click toggles state and emits ``toggled(bool)``. Sized to
    *icon_size* in widget space; the icons themselves are SVG-backed
    :class:`QIcon` instances scaled by Qt.

    Built as a custom widget (rather than a styled :class:`QCheckBox`)
    because Cocoa-style checkbox sub-elements render differently on
    macOS than on Linux/Windows even under Fusion. Painting the icons
    ourselves keeps the visual identical across platforms — important
    for the IFS panel that ships to macOS users.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        off_icon: QIcon,
        on_icon: QIcon,
        icon_size: QSize = QSize(40, 24),
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._off_icon = off_icon
        self._on_icon = on_icon
        self._checked = False
        self.setFixedSize(icon_size)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        """Set the toggle state. Emits ``toggled`` only on change."""
        if self._checked == bool(checked):
            return
        self._checked = bool(checked)
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        icon = self._on_icon if self._checked else self._off_icon
        icon.paint(painter, self.rect())
