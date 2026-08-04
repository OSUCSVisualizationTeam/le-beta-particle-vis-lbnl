"""Left panel widget for the Live Mode screensaver.

Displays the featured cluster's image, colormap gradient bar,
detection stats, and energy histogram.
"""

from typing import Optional

import numpy as np
from shiboken6 import isValid

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.HistogramDataModel import HistogramDataModel
from le_beta_vis.frontend.theme import LiveModeColors
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from le_beta_vis.frontend.widgets.ClusterDetailWidget import ClusterDetailWidget
from le_beta_vis.frontend.widgets.EnergyClusterWidget import EnergyClusterWidget
from le_beta_vis.frontend.widgets.InteractiveHistogramWidget import (
    InteractiveHistogramWidget,
)

from ..LiveModeViewModel import LiveModeViewModel
from ._LiveModeControlStrip import _LiveModeControlStrip
from ._PinningMiniToolbar import _PinningMiniToolbar
from ._ScaleGradientWidget import _ScaleGradientWidget
from .ClusterLocationMapWidget import ClusterLocationMapWidget

_HISTOGRAM_BINS = 50


class FeaturedClusterWidget(QWidget):
    """Left panel for Live Mode: featured image, gradient, stats, histogram, sensor map.

    Args:
        vm: The Live Mode ViewModel.
        inspector_vm: ViewModel for the cluster detail stats widget.
        parent: Optional parent widget.
    """

    _hduFrameReady = Signal(object, object)

    def __init__(
        self,
        vm: LiveModeViewModel,
        inspector_vm: HistoricalEventInspectorViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        self._inspector_vm = inspector_vm
        self._current_cluster: Optional[Cluster] = None
        self._pinningMiniToolbar = _PinningMiniToolbar(vm, parent=self)
        self._controlStrip = _LiveModeControlStrip(vm, parent=self)
        self._buildLayout()
        self._hduFrameReady.connect(self._onHduFrameReady)
        vm.add_hdu_frame_ready_callback(self._hduFrameReady.emit)

    # --- Construction ---

    def _buildLayout(self) -> None:
        """Construct the vertical label / featured row / stats / histogram layout."""
        self.setObjectName("FeaturedClusterWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._titleLabel = QLabel(self.tr("Live mode"))
        self._titleLabel.setObjectName("featuredTitleLabel")
        self._titleLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)
        top_row.addWidget(self._pinningMiniToolbar)
        top_row.addWidget(self._titleLabel, stretch=1)
        top_row.addWidget(self._controlStrip)
        layout.addLayout(top_row)

        featured_row = self._buildFeaturedRow()
        layout.addWidget(featured_row)

        self._statsWidget = ClusterDetailWidget(
            self._inspector_vm,
            show_filename=False,
            show_open_action=False,
        )
        self._statsWidget.setObjectName("featuredStatsWidget")
        layout.addWidget(self._statsWidget, stretch=0)

        self._histogram = InteractiveHistogramWidget()
        self._histogram.setPlaceholderText(
            self.tr("Awaiting cluster data..."),
        )
        self._histogram.setMinimumHeight(150)
        self._histogram.setObjectName("featuredHistogram")
        self._histogram.setTheme(
            LiveModeColors.HISTOGRAM_BG_DARK,
            LiveModeColors.HISTOGRAM_FG_DARK,
        )
        layout.addWidget(self._histogram, stretch=1)

        sensorLabel = QLabel(self.tr("Sensor Location"))
        sensorLabel.setObjectName("featuredSensorLabel")
        sensorLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(sensorLabel)

        self._locationMap = ClusterLocationMapWidget(physics=self._vm.physics)
        self._locationMap.setMinimumHeight(120)
        layout.addWidget(self._locationMap, stretch=0)

    def _buildFeaturedRow(self) -> QWidget:
        """Builds the row containing the featured image and gradient bar."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        self._featuredWidget = EnergyClusterWidget(
            size=64,
            enable_hover_tooltip=True,
        )
        self._featuredWidget.set_kev_converter(self._vm.physics.adu_to_kev)
        self._featuredWidget.setObjectName("featuredThumbnail")
        row_layout.addWidget(self._featuredWidget)

        self._gradientWidget = _ScaleGradientWidget(
            colormap=self._vm.colormap,
        )
        self._gradientWidget.setUnit("keV")
        row_layout.addWidget(self._gradientWidget)

        return row

    # --- Public interface ---

    @property
    def current_cluster(self) -> Optional[Cluster]:
        """The cluster currently displayed in the featured panel."""
        return self._current_cluster

    def renderFeaturedPanel(self, cluster: Cluster) -> None:
        """Render all featured panel widgets for a data-bearing cluster.

        Args:
            cluster: Cluster with non-None data to display.
        """
        self._current_cluster = cluster
        self._updateFeaturedImage(cluster)
        self._updateGradient(cluster)
        self._statsWidget.setCluster(cluster)
        self._updateHistogram(cluster)
        self._updateClassifierVisibility(cluster)
        self._vm.load_hdu_for_cluster(cluster)

    def clearFeaturedPanel(self) -> None:
        """Clear the featured panel to its empty state."""
        self._current_cluster = None
        self._featuredWidget.clear()
        self._statsWidget.clear()
        self._histogram.setData(None)
        self._locationMap.clear()
        self._statsWidget.set_classifiers_visible(False)

    def refreshFeaturedSize(self) -> None:
        """Resize the featured image widget to fill available panel width."""
        margins = 24  # 12px left + 12px right
        gradient_w = 60 + 4  # gradient widget + spacing
        avail = self.width() - margins - gradient_w
        if avail > 0:
            self._featuredWidget.setDisplaySize(avail)

    def resizeEvent(self, event) -> None:
        """Keep the featured thumbnail filling the available panel width."""
        super().resizeEvent(event)
        self.refreshFeaturedSize()

    def refreshHistogramMinHeight(self) -> None:
        """Enforce minimum histogram height from screen percentage."""
        screen = QApplication.primaryScreen()
        screen_h = screen.availableGeometry().height() if screen else 1080
        pct = self._vm.histogram_min_height_pct
        min_h = max(100, int(screen_h * pct))
        self._histogram.setMinimumHeight(min_h)

    # --- Private helpers ---

    def _updateFeaturedImage(self, cluster: Cluster) -> None:
        """Renders the featured cluster thumbnail."""
        self._featuredWidget.setCluster(
            cluster.data,
            self._vm.colormap,
        )

    def _updateGradient(self, cluster: Cluster) -> None:
        """Calibrates the gradient legend to the featured thumbnail's scale."""
        self._gradientWidget.setColormap(self._vm.colormap)
        vmax_adu = self._clusterPeakPixel(cluster)
        physics = self._vm.physics
        if physics is not None:
            vmax = float(physics.adu_to_kev(vmax_adu))
        else:
            vmax = vmax_adu
        self._gradientWidget.setRange(0.0, vmax)

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
            data,
            bins=_HISTOGRAM_BINS,
            x_label=x_label,
            colormap=self._vm.colormap.value,
            x_unit=x_unit,
        )
        self._histogram.setData(model)

    def _clusterPeakPixel(self, cluster: Cluster) -> float:
        """Peak pixel value (ADU) of the featured cluster, matching thumbnail vmax."""
        if cluster.data is None or cluster.data.size == 0:
            return 1.0
        peak = float(np.max(cluster.data))
        return peak if peak > 0 else 1.0

    def _updateClassifierVisibility(self, cluster: Cluster) -> None:
        """Show or hide the classifier section based on config key and score availability."""
        has_scores = (
            max(
                cluster.cnnClassification,
                cluster.nrgClassification,
                cluster.bdtClassification,
            )
            > 0
        )
        show = self._vm.badges_classifiers_enabled and has_scores
        self._statsWidget.set_classifiers_visible(show)

    def _onHduFrameReady(self, frame: object, bbox: object) -> None:
        """Main-thread slot: update the sensor location map with the loaded HDU frame."""
        if not isValid(self):
            return
        if frame is not None and bbox is not None:
            self._locationMap.set_hdu_frame(frame, bbox)
        else:
            self._locationMap.clear()
