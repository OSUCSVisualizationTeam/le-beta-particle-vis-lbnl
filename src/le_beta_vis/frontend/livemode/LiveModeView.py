"""Fullscreen non-interactive Live Mode screensaver.

Displays incoming classified beta-particle clusters as an animated
snake-path grid (right panel) alongside a featured cluster detail
panel (left panel).  Any keyboard or mouse input dismisses the
dialog.
"""

import logging
from typing import Optional

import numpy as np

from PySide6.QtCore import (
    QMetaObject,
    QTimer,
    Qt,
    Slot,
)
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.HistogramDataModel import HistogramDataModel
from le_beta_vis.frontend.theme import LiveModeColors
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from le_beta_vis.frontend.widgets.ClusterDetailWidget import (
    ClusterDetailWidget,
)
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)
from le_beta_vis.frontend.widgets.InteractiveHistogramWidget import (
    InteractiveHistogramWidget,
)

from ._ScaleGradientWidget import _ScaleGradientWidget
from ._ThumbnailGridWidget import _ThumbnailGridWidget
from .LiveModeViewModel import LiveModeViewModel

logger = logging.getLogger(__name__)

_HISTOGRAM_BINS = 50
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
        self._fallback_timer: Optional[QTimer] = None
        self._featured_cluster: Optional[Cluster] = None
        self._pending_featured_data: Optional[np.ndarray] = None
        self._pending_featured_update: Optional[Cluster] = None
        self._initUI()
        self._connectViewModel()

    # --- UI construction ---

    def _initUI(self) -> None:
        """Builds the fullscreen layout with left and right panels."""
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setStyleSheet(
            f"background-color: {LiveModeColors.BACKGROUND};"
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

        self._leftPanel = self._buildLeftPanel()
        self._leftPanel.setFixedWidth(panel_w)
        layout.addWidget(self._leftPanel)

        right = self._buildRightPanel()
        right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(right, stretch=1)

    def _buildLeftPanel(self) -> QWidget:
        """Constructs the left panel with featured image, gradient, stats, histogram."""
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {LiveModeColors.PANEL_LEFT};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._titleLabel = QLabel(self.tr("Real-time Detection"))
        self._titleLabel.setStyleSheet(
            f"color: {LiveModeColors.TITLE_TEXT};"
            "font-size: 18px; font-weight: bold;"
        )
        self._titleLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._titleLabel)

        featured_row = self._buildFeaturedRow()
        layout.addWidget(featured_row)

        self._statsWidget = ClusterDetailWidget(
            self._inspectorVM, show_filename=False,
        )
        self._statsWidget.setStyleSheet(
            f"background-color: {LiveModeColors.STATS_BACKGROUND};"
            f"color: {LiveModeColors.STATS_TEXT};"
            "padding: 8px; border-radius: 4px;"
        )
        layout.addWidget(self._statsWidget, stretch=0)

        self._histogram = InteractiveHistogramWidget()
        self._histogram.setPlaceholderText(
            self.tr("Awaiting cluster data..."),
        )
        self._histogram.setMinimumHeight(150)
        self._histogram.setStyleSheet(
            f"background-color: {LiveModeColors.HISTOGRAM_BG_DARK};"
            "border-radius: 4px;"
        )
        self._histogram.setTheme(
            LiveModeColors.HISTOGRAM_BG_DARK,
            LiveModeColors.HISTOGRAM_FG_DARK,
        )
        layout.addWidget(self._histogram, stretch=1)

        return panel

    def _buildFeaturedRow(self) -> QWidget:
        """Builds the row containing the featured image and gradient bar."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        self._featuredWidget = EnergyClusterWidget(
            size=self._vm.featured_size,
        )
        self._featuredWidget.setStyleSheet(
            f"background-color: {LiveModeColors.BACKGROUND};"
        )
        row_layout.addWidget(self._featuredWidget)

        self._gradientWidget = _ScaleGradientWidget(
            colormap=self._vm.colormap,
        )
        self._gradientWidget.setUnit("keV")
        row_layout.addWidget(self._gradientWidget)

        return row

    def _buildRightPanel(self) -> QWidget:
        """Constructs the right panel containing the thumbnail grid."""
        self._gridWidget = _ThumbnailGridWidget(self._vm)
        return self._gridWidget

    # --- ViewModel wiring ---

    def _connectViewModel(self) -> None:
        """Registers ViewModel callbacks for cross-thread notification."""
        self._vm.add_grid_changed_callback(self._onGridChangedFromBg)
        self._vm.add_featured_changed_callback(self._onFeaturedChangedFromBg)

    def _onGridChangedFromBg(self) -> None:
        """Callback from ViewModel (may be on a background thread).

        Marshals execution to the main thread via QMetaObject.
        """
        QMetaObject.invokeMethod(
            self, "_onGridChanged", Qt.AutoConnection,
        )

    @Slot()
    def _onGridChanged(self) -> None:
        """Main-thread slot: resets fallback timer on live data arrival."""
        self._resetFallbackTimer()

    def _onFeaturedChangedFromBg(
        self,
        cluster: Optional[Cluster],
    ) -> None:
        """Callback from ViewModel (may be on a background thread)."""
        self._pending_featured_update = cluster
        QMetaObject.invokeMethod(
            self, "_onFeaturedChanged", Qt.AutoConnection,
        )

    @Slot()
    def _onFeaturedChanged(self) -> None:
        """Main-thread slot: updates left panel with new featured cluster."""
        cluster = self._pending_featured_update
        self._pending_featured_update = None
        self._updateFeaturedPanel(cluster)

    # --- Lifecycle ---

    def showEvent(self, event) -> None:
        """Activates the ViewModel and starts timers on show."""
        super().showEvent(event)
        self.showFullScreen()
        self._vm.activate()
        self._refreshFeaturedSize()
        self._refreshHistogramMinHeight()
        self._initTimers()
        self._gridWidget.populate(self._vm.grid)

    def hideEvent(self, event) -> None:
        """Deactivates the ViewModel and stops timers on hide."""
        super().hideEvent(event)
        self._stopTimers()
        self._gridWidget.stop()
        self._vm.deactivate()

    # --- Dismissal ---

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Dismisses the screensaver on any key press."""
        self.reject()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Dismisses the screensaver on any mouse click."""
        self.reject()

    # --- Layout helpers ---

    def _refreshFeaturedSize(self) -> None:
        """Resize the featured widget to fill available panel width."""
        panel_w = self._leftPanel.width()
        margins = 24  # 12px left + 12px right
        gradient_w = 60 + 4  # gradient widget + spacing
        avail = panel_w - margins - gradient_w
        if avail > 0:
            self._featuredWidget.setFixedSize(avail, avail)

    def _refreshHistogramMinHeight(self) -> None:
        """Enforce minimum histogram height from screen percentage."""
        screen = QApplication.primaryScreen()
        screen_h = screen.availableGeometry().height() if screen else 1080
        pct = self._vm.histogram_min_height_pct
        min_h = max(100, int(screen_h * pct))
        self._histogram.setMinimumHeight(min_h)

    # --- Timers ---

    def _initTimers(self) -> None:
        """Creates and starts the advance and fallback timers."""
        self._advance_timer = QTimer(self)
        self._advance_timer.setInterval(self._vm.advance_interval_ms)
        self._advance_timer.timeout.connect(self._onAdvanceTick)
        self._advance_timer.start()

        self._fallback_timer = QTimer(self)
        self._fallback_timer.setSingleShot(True)
        self._fallback_timer.setInterval(
            self._vm.fallback_timeout_s * 1000,
        )
        self._fallback_timer.timeout.connect(self._onFallbackTimeout)
        self._fallback_timer.start()

    def _stopTimers(self) -> None:
        """Stops and cleans up both timers."""
        if self._advance_timer is not None:
            self._advance_timer.stop()
            self._advance_timer = None
        if self._fallback_timer is not None:
            self._fallback_timer.stop()
            self._fallback_timer = None

    def _resetFallbackTimer(self) -> None:
        """Restarts the fallback timer on live event arrival."""
        if self._fallback_timer is not None:
            self._fallback_timer.start()

    @Slot()
    def _onAdvanceTick(self) -> None:
        """Timer slot: advances the grid by one snake step."""
        self._vm.advance()
        self._gridWidget.animateAdvance(self._vm.grid)

    @Slot()
    def _onFallbackTimeout(self) -> None:
        """Timer slot: triggers fallback data load from database."""
        logger.info("Fallback timeout reached, loading from database")
        self._vm.trigger_fallback()

    # --- Panel updates ---

    def _updateFeaturedPanel(self, cluster: Optional[Cluster]) -> None:
        """Updates the featured image, gradient, stats, and histogram."""
        if cluster is None:
            self._featured_cluster = None
            self._featuredWidget.clear()
            self._statsWidget.clear()
            self._histogram.setData(None)
            return
        self._featured_cluster = cluster
        if cluster.data is None:
            self._vm.request_cluster_data(
                cluster, self._onClusterDataReady,
            )
            return
        self._renderFeaturedPanel(cluster)

    def _renderFeaturedPanel(self, cluster: Cluster) -> None:
        """Renders all featured panel widgets for a data-bearing cluster."""
        self._updateFeaturedImage(cluster)
        self._updateGradient(cluster)
        self._statsWidget.setCluster(cluster)
        self._updateHistogram(cluster)

    def _onClusterDataReady(
        self,
        data: Optional[np.ndarray],
    ) -> None:
        """Background callback when FITS extraction completes."""
        self._pending_featured_data = data
        QMetaObject.invokeMethod(
            self, "_applyFeaturedData", Qt.AutoConnection,
        )

    @Slot()
    def _applyFeaturedData(self) -> None:
        """Main-thread slot: applies extracted cluster data."""
        data = self._pending_featured_data
        self._pending_featured_data = None
        if data is None or self._featured_cluster is None:
            return
        self._featured_cluster.data = data
        self._renderFeaturedPanel(self._featured_cluster)

    def _updateFeaturedImage(self, cluster: Cluster) -> None:
        """Renders the featured cluster thumbnail."""
        self._featuredWidget.setCluster(
            cluster.data, self._vm.colormap,
        )

    def _updateGradient(self, cluster: Cluster) -> None:
        """Updates the gradient bar marker based on cluster energy."""
        self._gradientWidget.setColormap(self._vm.colormap)
        max_energy = self._currentMaxEnergy()
        if max_energy <= 0:
            return
        physics = self._vm.physics
        if physics is not None:
            cluster_kev = physics.adu_to_kev(cluster.energy)
            max_kev = physics.adu_to_kev(max_energy)
            ratio = min(1.0, cluster_kev / max_kev) if max_kev > 0 else 0.0
            self._gradientWidget.setMarkerRatio(ratio)
            self._gradientWidget.setRange(0.0, float(max_kev))
        else:
            ratio = min(1.0, cluster.energy / max_energy)
            self._gradientWidget.setMarkerRatio(ratio)
            self._gradientWidget.setRange(0.0, max_energy)

    def _updateHistogram(self, cluster: Cluster) -> None:
        """Builds and displays an energy histogram from cluster data."""
        if cluster.data is None:
            self._histogram.setData(None)
            return
        physics = self._vm.physics
        data = cluster.data.copy()
        if physics is not None:
            data = np.vectorize(physics.adu_to_kev)(data)
            x_label = "Energy (keV)"
            x_unit = "keV"
        else:
            x_label = "Energy (ADU)"
            x_unit = "ADU"
        model = HistogramDataModel.from_pixel_data(
            data, bins=_HISTOGRAM_BINS,
            x_label=x_label,
            colormap=self._vm.colormap.value,
            x_unit=x_unit,
        )
        self._histogram.setData(model)

    def _currentMaxEnergy(self) -> float:
        """Scans the grid for the maximum cluster energy."""
        grid = self._vm.grid
        energies = [
            c.energy for c in grid
            if c is not None and c.energy > 0
        ]
        return max(energies) if energies else 1.0
