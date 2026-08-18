"""Fullscreen non-interactive Live Mode screensaver.

Displays incoming classified beta-particle clusters as an animated
snake-path grid (right panel) alongside a featured cluster detail
panel (left panel).  Any keyboard or mouse input dismisses the
dialog.
"""

import logging
from typing import Optional

import numpy as np
from shiboken6 import isValid

from PySide6.QtCore import (
    QMetaObject,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)

from .widgets.DetectedClusterCollectionWidget import (
    DetectedClusterCollectionWidget,
)
from .widgets.FeaturedClusterWidget import FeaturedClusterWidget
from .LiveModeViewModel import LiveModeViewModel

logger = logging.getLogger(__name__)

_LEFT_PANEL_MIN_W_FALLBACK = 300


class LiveModeView(QDialog):
    """Fullscreen screensaver showing live cluster detection.

    Composes a left detail panel (featured image, gradient bar,
    stats, histogram) with a right thumbnail grid.  Dismissed
    by any key press or mouse click.

    Args:
        viewModel: The Live Mode ViewModel instance.
        parent: Optional parent widget.
    """

    _pausedChanged = Signal(bool)

    def __init__(
        self,
        viewModel: LiveModeViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._inspectorVM = HistoricalEventInspectorViewModel(
            physics=viewModel.physics,
            threshold=0.75,
            displayKeV=True,
        )
        self._advance_timer: Optional[QTimer] = None
        self._featured_cluster: Optional[Cluster] = None
        self._pending_featured_data: Optional[np.ndarray] = None
        self._pending_featured_update: Optional[Cluster] = None
        self._initUI()
        self._connectViewModel()

    # --- UI construction ---

    def _initUI(self) -> None:
        """Builds the fullscreen layout with left and right panels."""
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        screen = QApplication.primaryScreen()
        screen_w = screen.availableGeometry().width() if screen else 1920
        panel_w = max(
            _LEFT_PANEL_MIN_W_FALLBACK,
            int(screen_w * self._vm.left_panel_width_pct),
        )

        self._featuredPanel = FeaturedClusterWidget(self._vm, self._inspectorVM)
        self._featuredPanel.setFixedWidth(panel_w)
        layout.addWidget(self._featuredPanel)

        self._clusterCollection = DetectedClusterCollectionWidget(self._vm)
        self._clusterCollection.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self._clusterCollection, stretch=1)

    # --- ViewModel wiring ---

    def _connectViewModel(self) -> None:
        """Registers ViewModel callbacks for cross-thread notification."""
        self._vm.add_grid_changed_callback(self._onGridChangedFromBg)
        self._vm.add_featured_changed_callback(self._onFeaturedChangedFromBg)
        self._pausedChanged.connect(self._onPausedChanged)
        self._vm.add_paused_changed_callback(self._pausedChanged.emit)
        self._clusterCollection.set_cell_click_handler(self._onCellClicked)

    def _onGridChangedFromBg(self) -> None:
        """Callback from ViewModel (may be on a background thread).

        Marshals execution to the main thread via QMetaObject.
        """
        QMetaObject.invokeMethod(
            self,
            "_onGridChanged",
            Qt.AutoConnection,
        )

    @Slot()
    def _onGridChanged(self) -> None:
        """Main-thread slot: repopulates grid on background data arrival.

        Defers the repaint while an advance animation is running so
        mid-slide pixmap restamping cannot cause visible jitter when
        a fallback refill or a FITS data load completes.
        """
        if not isValid(self):
            return
        self._clusterCollection.scheduleRepaint(self._vm.grid)

    def _onFeaturedChangedFromBg(
        self,
        cluster: Optional[Cluster],
    ) -> None:
        """Callback from ViewModel (may be on a background thread)."""
        self._pending_featured_update = cluster
        QMetaObject.invokeMethod(
            self,
            "_onFeaturedChanged",
            Qt.AutoConnection,
        )

    @Slot()
    def _onFeaturedChanged(self) -> None:
        """Main-thread slot: updates left panel with new featured cluster."""
        if not isValid(self):
            return
        cluster = self._pending_featured_update
        self._pending_featured_update = None
        self._updateFeaturedPanel(cluster)

    # --- Lifecycle ---

    def showEvent(self, event) -> None:
        """Activates the ViewModel and starts timers on show."""
        super().showEvent(event)
        self.showFullScreen()
        self._vm.activate()
        self._featuredPanel.refreshFeaturedSize()
        self._featuredPanel.refreshHistogramMinHeight()
        self._initTimers()
        self._clusterCollection.populate(self._vm.grid)

    def hideEvent(self, event) -> None:
        """Deactivates the ViewModel and stops timers on hide."""
        super().hideEvent(event)
        self._stopTimers()
        self._clusterCollection.stop()
        self._vm.deactivate()

    # --- Dismissal and interaction ---

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Space toggles pause; Esc exits; all other keys are ignored."""
        if event.key() == Qt.Key_Space:
            self._vm.toggle_paused()
        elif event.key() == Qt.Key_Escape:
            self.reject()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Dismiss on any click on the dialog background."""
        self.reject()

    def _onCellClicked(self, cluster: Cluster) -> None:
        """Pin the cluster whose thumbnail was clicked and display it."""
        self._vm.pin_cluster(cluster)
        self._showClusterInFeaturedPanel(cluster)

    def _onPausedChanged(self, paused: bool) -> None:
        """Start or stop the advance timer in response to pause state."""
        if self._advance_timer is None:
            return
        if paused:
            self._advance_timer.stop()
            self._clusterCollection.pause_animation()
        else:
            self._advance_timer.start(self._vm.advance_interval_ms)
            self._clusterCollection.resume_animation()

    # --- Timers ---

    def _initTimers(self) -> None:
        """Creates and starts the advance timer."""
        self._advance_timer = QTimer(self)
        self._advance_timer.setInterval(self._vm.advance_interval_ms)
        self._advance_timer.timeout.connect(self._onAdvanceTick)
        self._advance_timer.start()

    def _stopTimers(self) -> None:
        """Stops and cleans up the advance timer."""
        if self._advance_timer is not None:
            self._advance_timer.stop()
            self._advance_timer = None

    @Slot()
    def _onAdvanceTick(self) -> None:
        """Timer slot: dequeues featured and advances the grid."""
        count = self._vm.advance()
        if count > 0:
            self._clusterCollection.animateAdvance(self._vm.grid, count)

    # --- Panel updates ---

    def _updateFeaturedPanel(self, cluster: Optional[Cluster]) -> None:
        """Advance-driven update — skipped when a cluster is pinned."""
        if cluster is not None and self._vm.pinned_cluster is not None:
            return
        self._showClusterInFeaturedPanel(cluster)

    def _showClusterInFeaturedPanel(self, cluster: Optional[Cluster]) -> None:
        """Unconditionally render *cluster* in the featured panel."""
        if cluster is None:
            self._featured_cluster = None
            self._featuredPanel.clearFeaturedPanel()
            return
        self._featured_cluster = cluster
        if cluster.data is None:
            self._vm.request_cluster_data(
                cluster,
                self._onClusterDataReady,
            )
            return
        self._featuredPanel.renderFeaturedPanel(cluster)

    def _onClusterDataReady(
        self,
        data: Optional[np.ndarray],
    ) -> None:
        """Background callback when FITS extraction completes."""
        self._pending_featured_data = data
        QMetaObject.invokeMethod(
            self,
            "_applyFeaturedData",
            Qt.AutoConnection,
        )

    @Slot()
    def _applyFeaturedData(self) -> None:
        """Main-thread slot: applies extracted cluster data."""
        if not isValid(self):
            return
        data = self._pending_featured_data
        self._pending_featured_data = None
        if data is None or self._featured_cluster is None:
            return
        self._featured_cluster.data = data
        self._featuredPanel.renderFeaturedPanel(self._featured_cluster)
