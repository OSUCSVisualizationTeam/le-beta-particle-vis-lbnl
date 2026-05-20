"""Pin / details mini toolbar for the FeaturedClusterWidget top row.

Shows a single pin icon when no cluster is pinned; expands to show
Details and active-pin when a cluster is pinned.  Clicking the active-pin
unpins; clicking Details dismisses Live Mode and navigates to Historical.
"""

from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.icons import load_icon
from le_beta_vis.frontend.theme import FeaturedClusterMiniToolbarColors

from ..LiveModeViewModel import LiveModeViewModel
from ._utils import livemode_icon_size

_PADDING_PX = 4


class _PinningMiniToolbar(QWidget):
    """Two-state toolbar embedded in the FeaturedClusterWidget top row.

    Not-pinned state: shows pin icon only.
    Pinned state: shows Details (ℹ) and active-pin (📌●); clicking
    the active-pin unpins.
    """

    def __init__(self, vm: LiveModeViewModel, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._icon_size = self._compute_icon_size()
        self._build_ui()
        self._update_state(None)
        vm.add_pinned_changed_callback(self._on_pinned_changed)

    # --- Build ---

    def _compute_icon_size(self) -> int:
        return livemode_icon_size(self._vm)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(_PADDING_PX, _PADDING_PX, _PADDING_PX, _PADDING_PX)
        layout.setSpacing(_PADDING_PX)

        icon_size = QSize(self._icon_size, self._icon_size)
        btn_style = "QToolButton { border: none; background: transparent; }"

        self._pin_btn = QToolButton(self)
        self._pin_btn.setIcon(
            load_icon("keep", FeaturedClusterMiniToolbarColors.ICON_DEFAULT),
        )
        self._pin_btn.setIconSize(icon_size)
        self._pin_btn.setToolTip(self.tr("Pin this cluster"))
        self._pin_btn.setAutoRaise(True)
        self._pin_btn.setStyleSheet(btn_style)
        self._pin_btn.clicked.connect(self._on_pin_clicked)

        self._details_btn = QToolButton(self)
        self._details_btn.setIcon(
            load_icon("info", FeaturedClusterMiniToolbarColors.ICON_DEFAULT),
        )
        self._details_btn.setIconSize(icon_size)
        self._details_btn.setToolTip(self.tr("Open in Historical inspector"))
        self._details_btn.setAutoRaise(True)
        self._details_btn.setStyleSheet(btn_style)
        self._details_btn.clicked.connect(self._on_details_clicked)

        self._active_pin_btn = QToolButton(self)
        self._active_pin_btn.setIcon(
            load_icon("keep", FeaturedClusterMiniToolbarColors.ICON_ACTIVE),
        )
        self._active_pin_btn.setIconSize(icon_size)
        self._active_pin_btn.setToolTip(self.tr("Unpin cluster"))
        self._active_pin_btn.setAutoRaise(True)
        self._active_pin_btn.setStyleSheet(btn_style)
        self._active_pin_btn.clicked.connect(self._vm.unpin)

        layout.addWidget(self._details_btn)
        layout.addWidget(self._active_pin_btn)
        layout.addWidget(self._pin_btn)

    # --- State ---

    def _update_state(self, pinned: Optional[Cluster]) -> None:
        is_pinned = pinned is not None
        self._pin_btn.setVisible(not is_pinned)
        self._details_btn.setVisible(is_pinned)
        self._active_pin_btn.setVisible(is_pinned)
        self.adjustSize()

    # --- Slots ---

    def _on_pinned_changed(self, pinned: Optional[Cluster]) -> None:
        self._update_state(pinned)

    def _on_pin_clicked(self) -> None:
        cluster: Optional[Cluster] = getattr(self.parent(), "current_cluster", None)
        if cluster is not None:
            self._vm.pin_cluster(cluster)

    def _on_details_clicked(self) -> None:
        cluster = self._vm.pinned_cluster
        if cluster is None:
            return
        self._vm.request_open_in_historical(cluster)
        window = self.window()
        if window is not None:
            window.reject()
