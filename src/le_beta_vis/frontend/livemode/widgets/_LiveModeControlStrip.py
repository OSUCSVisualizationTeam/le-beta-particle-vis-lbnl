"""Control strip embedded in the FeaturedClusterWidget top row.

Contains Exit, Pause/Play, and Save Frame buttons.  Permanently visible
as part of the layout — no floating window, no auto-hide.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QToolButton,
    QWidget,
)

from le_beta_vis.frontend.icons import load_icon
from le_beta_vis.frontend.theme import LiveModeControlStripColors

from ..LiveModeViewModel import LiveModeViewModel
from ._utils import livemode_icon_size

_BUTTON_PADDING_PX = 8
_BORDER_RADIUS_PX = 8


class _LiveModeControlStrip(QWidget):
    """Compact icon-only control strip for the Live Mode top row."""

    _pausedChanged = Signal(bool)

    def __init__(self, vm: LiveModeViewModel, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._icon_size = self._compute_icon_size()
        self._build_ui()
        self._pausedChanged.connect(self._on_paused_changed)
        vm.add_paused_changed_callback(self._pausedChanged.emit)

    # --- Build ---

    def _compute_icon_size(self) -> int:
        return livemode_icon_size(self._vm)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            _BUTTON_PADDING_PX * 2,
            _BUTTON_PADDING_PX,
            _BUTTON_PADDING_PX * 2,
            _BUTTON_PADDING_PX,
        )
        layout.setSpacing(_BUTTON_PADDING_PX)

        self._exit_btn = self._make_button(
            "cancel",
            self.tr("Exit Live Mode"),
            self._on_exit_clicked,
        )
        self._pause_btn = self._make_button(
            "pause_circle",
            self.tr("Pause"),
            self._on_pause_clicked,
        )
        self._save_btn = self._make_button(
            "save",
            self.tr("Save frame to file"),
            self._on_save_clicked,
        )

        layout.addWidget(self._pause_btn)
        layout.addWidget(self._save_btn)
        layout.addWidget(self._exit_btn)

    def _make_button(self, icon_name: str, tooltip: str, slot) -> QToolButton:
        btn = QToolButton(self)
        btn.setIcon(load_icon(icon_name, LiveModeControlStripColors.ICON_DEFAULT))
        btn.setIconSize(QSize(self._icon_size, self._icon_size))
        btn.setToolTip(tooltip)
        btn.setAutoRaise(True)
        btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
        btn.clicked.connect(slot)
        return btn

    # --- Slots ---

    def _on_paused_changed(self, paused: bool) -> None:
        icon_name = "play_circle" if paused else "pause_circle"
        tooltip = self.tr("Resume") if paused else self.tr("Pause")
        self._pause_btn.setIcon(
            load_icon(icon_name, LiveModeControlStripColors.ICON_DEFAULT),
        )
        self._pause_btn.setToolTip(tooltip)

    def _on_pause_clicked(self) -> None:
        self._vm.toggle_paused()

    def _on_save_clicked(self) -> None:
        cluster = self._vm.pinned_cluster
        if cluster is None:
            grid = self._vm.grid
            cluster = next((c for c in grid if c is not None), None)
        if cluster is None:
            return

        timestamp = datetime.now().strftime("%y%m%d-%H%M%S")
        suggested = f"mlccd_livemode_{timestamp}.h5"
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Live Mode Frame"),
            suggested,
            self.tr("HDF5 Files (*.h5)"),
        )
        if not path:
            return

        self._vm.request_save_frame(cluster, Path(path))
        self.window().reject()

    def _on_exit_clicked(self) -> None:
        self.window().reject()
