"""Detail panel for a selected historical event.

Uses ``InteractiveHistogramWidget`` (pyqtgraph) for native Qt
rendering with hover tooltips — no background threads needed.
"""

import logging
from typing import Optional

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.HistogramDataModel import HistogramDataModel
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)
from le_beta_vis.frontend.widgets.InteractiveHistogramWidget import (
    InteractiveHistogramWidget,
)

logger = logging.getLogger(__name__)

_HIGH_RES_SIZE = 256
_HISTOGRAM_BINS = 50


class _Style:
    PANEL = "background-color: #f0f0f0;" "color: #000000;"
    SECTION_HEADER = (
        "font-weight: bold;" "font-size: 13px;" "color: #333333;" "padding-top: 8px;"
    )
    PLACEHOLDER = "color: #999999;" "font-style: italic;" "padding: 20px;"


class HistoricalEventInspector(QWidget):
    """View for displaying detailed information about a selected event.

    Uses ``HistoricalEventInspectorViewModel`` for all formatting
    and display logic.  The thumbnail is rendered via
    ``EnergyClusterWidget`` and the histogram is rendered
    synchronously with ``InteractiveHistogramWidget``.
    """

    def __init__(
        self,
        viewModel: HistoricalEventInspectorViewModel,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._vm = viewModel
        self._colormap: Optional[Colormap] = None
        self._current_cluster: Optional[Cluster] = None
        self._initUI()

    def _initUI(self) -> None:
        self.setStyleSheet(_Style.PANEL)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setAlignment(Qt.AlignTop)

        # Placeholder shown when nothing is selected
        self._placeholder = QLabel(self.tr("Select an event to inspect"))
        self._placeholder.setStyleSheet(_Style.PLACEHOLDER)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._placeholder)

        # Detail widgets (hidden until an event is selected)
        self._detailWidget = QWidget()
        detail = QVBoxLayout(self._detailWidget)
        detail.setContentsMargins(8, 8, 8, 8)

        # Top section: image (left) + detail HTML (right)
        detail.addLayout(self._createTopSection())

        # Histogram
        self._createHistogramSection(detail)

        self._detailWidget.setVisible(False)
        self._layout.addWidget(self._detailWidget)

    def _createTopSection(self) -> QHBoxLayout:
        """Creates side-by-side thumbnail + rich-text detail."""
        top = QHBoxLayout()
        top.setSpacing(16)

        # Left column: cluster image
        leftCol = QVBoxLayout()
        self._imageWidget = EnergyClusterWidget(size=_HIGH_RES_SIZE)
        leftCol.addWidget(self._imageWidget)
        leftCol.addStretch()
        top.addLayout(leftCol)

        # Right column: rich-text detail label
        rightCol = QVBoxLayout()
        rightCol.setAlignment(Qt.AlignTop)

        self._detailLabel = QLabel()
        self._detailLabel.setWordWrap(True)
        self._detailLabel.setTextFormat(Qt.RichText)
        self._detailLabel.setAlignment(Qt.AlignTop)
        rightCol.addWidget(self._detailLabel)

        rightCol.addStretch()
        top.addLayout(rightCol, 1)

        return top

    def _createHistogramSection(self, parent: QVBoxLayout) -> None:
        """Creates the energy histogram section."""
        header = QLabel(self.tr("Energy Distribution"))
        header.setStyleSheet(_Style.SECTION_HEADER)
        parent.addWidget(header)

        self._histogram = InteractiveHistogramWidget()
        self._histogram.setPlaceholderText(
            self.tr("Select an event to see energy distribution")
        )
        self._histogram.setMinimumHeight(50)
        parent.addWidget(self._histogram, 1)

    # --- Public interface ---

    def setEvent(self, cluster: Optional[Cluster]) -> None:
        """Updates the inspector with cluster metadata.

        Image and histogram will be populated later via
        ``updateClusterData()``.

        Args:
            cluster: The cluster to display, or None to clear.
        """
        self._current_cluster = cluster
        self._vm.setEvent(cluster)
        if cluster is None:
            self.clear()
            return

        self._placeholder.setVisible(False)
        self._detailWidget.setVisible(True)

        self._detailLabel.setText(self._vm.formatDetailHtml(cluster))
        # Clear stale image/histogram — will be populated by updateClusterData
        self._imageWidget.clear()
        self._histogram.setData(None)

    def updateClusterData(self, data: Optional[np.ndarray]) -> None:
        """Updates the image and histogram with raw pixel data.

        Args:
            data: Raw cluster pixel data, or None if unavailable.
        """
        if data is None or self._current_cluster is None:
            return
        self._imageWidget.setCluster(data, self._colormap)
        self._updateHistogramFromData(data)

    def clear(self) -> None:
        """Resets the inspector to its empty state."""
        self._current_cluster = None
        self._placeholder.setVisible(True)
        self._detailWidget.setVisible(False)
        self._histogram.setData(None)

    def setColormap(self, colormap: Optional[Colormap]) -> None:
        """Sets the colormap for the high-res image.

        Args:
            colormap: Colormap enum or None for grayscale.
        """
        self._colormap = colormap

    # --- Histogram ---

    def _updateHistogramFromData(self, data: np.ndarray) -> None:
        """Builds a histogram model from raw data and pushes it to the widget."""
        hist_data = data.copy()
        cluster = self._current_cluster
        x_label = self._vm.formatHistogramXLabel(cluster)
        if self._vm.physics and self._vm.displayKeV:
            hist_data = self._vm.physics.adu_to_kev(hist_data)
            x_unit = "keV"
        else:
            x_unit = "ADU"

        model = HistogramDataModel.from_pixel_data(
            hist_data,
            _HISTOGRAM_BINS,
            x_label,
            x_unit=x_unit,
        )
        self._histogram.setData(model)
