"""Widget displaying ROI statistics and energy histogram.

Uses ``InteractiveHistogramWidget`` (pyqtgraph) for native Qt
rendering with hover tooltips — no background threads needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional

import numpy as np
from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.HistogramDataModel import HistogramDataModel
from le_beta_vis.common.ROIStatistics import ROIStatistics
from le_beta_vis.frontend.widgets.InteractiveHistogramWidget import (
    InteractiveHistogramWidget,
)

if TYPE_CHECKING:
    from le_beta_vis.frontend.viewmodels.ClusterAnalysisViewModel import (
        ClusterAnalysisViewModel,
    )
    from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
        RawDataViewModel,
    )

logger = logging.getLogger(__name__)

_HISTOGRAM_BINS = 50


class _Style:
    HEADER = "font-weight: bold; font-size: 13px; color: #333333;"
    STAT_LABEL = (
        "font-weight: bold; font-size: 11px; color: #555555; border: none;"
    )
    STAT_VALUE = "font-size: 11px; color: #222222; border: none;"


class _ROIInfoWidget(QWidget):
    """Interactive ROI info display with statistics and histogram."""

    def __init__(
        self,
        viewModel: RawDataViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._cavm: ClusterAnalysisViewModel = (
            viewModel.clusterAnalysisViewModel
        )
        self._stat_labels: Dict[str, QLabel] = {}
        self._roi_coord_labels: Dict[str, QLabel] = {}
        self._initUI()
        self._bindViewModel()

    # --- UI ---

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self._initCoordSection(layout)
        self._initStatsSection(layout)
        self._initHistogramSection(layout)

    def _initCoordSection(self, parent_layout: QVBoxLayout) -> None:
        """Creates the ROI coordinate and dimensions display."""
        header = QLabel(self.tr("ROI Region"))
        header.setStyleSheet(_Style.HEADER)
        parent_layout.addWidget(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        rows = [
            ("roi_origin", self.tr("Origin:")),
            ("roi_dimensions", self.tr("Size:")),
        ]
        for row_idx, (key, label_text) in enumerate(rows):
            label = QLabel(label_text)
            label.setStyleSheet(_Style.STAT_LABEL)
            value = QLabel("—")
            value.setStyleSheet(_Style.STAT_VALUE)
            grid.addWidget(label, row_idx, 0, Qt.AlignTop)
            grid.addWidget(value, row_idx, 1, Qt.AlignTop)
            self._roi_coord_labels[key] = value

        parent_layout.addLayout(grid)

    def _initStatsSection(self, parent_layout: QVBoxLayout) -> None:
        """Creates the statistics header and grid."""
        header = QLabel(self.tr("ROI Statistics"))
        header.setStyleSheet(_Style.HEADER)
        parent_layout.addWidget(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        rows = [
            ("max_energy", self.tr("Max Energy:")),
            ("min_energy", self.tr("Min Energy:")),
            ("mean_energy", self.tr("Mean Energy:")),
            ("sigma", self.tr("σ:")),
            ("pixel_count", self.tr("Pixel Count:")),
        ]
        for row_idx, (key, label_text) in enumerate(rows):
            label = QLabel(label_text)
            label.setStyleSheet(_Style.STAT_LABEL)
            value = QLabel("—")
            value.setStyleSheet(_Style.STAT_VALUE)
            value.setWordWrap(True)
            grid.addWidget(label, row_idx, 0, Qt.AlignTop)
            grid.addWidget(value, row_idx, 1, Qt.AlignTop)
            self._stat_labels[key] = value

        parent_layout.addLayout(grid)

    def _initHistogramSection(self, parent_layout: QVBoxLayout) -> None:
        """Creates the energy histogram."""
        header = QLabel(self.tr("Energy Distribution"))
        header.setStyleSheet(_Style.HEADER)
        parent_layout.addWidget(header)

        self._histogram = InteractiveHistogramWidget()
        self._histogram.setPlaceholderText(
            self.tr("Draw an ROI to see energy distribution")
        )
        self._histogram.setLogarithmicBars(True)
        parent_layout.addWidget(self._histogram, 1)

    # --- ViewModel bindings ---

    def _bindViewModel(self) -> None:
        """Connects ViewModel callbacks to the render slot."""
        self._cavm.add_roi_changed_callback(self._onRoiChanged)
        self._vm.add_image_changed_callback(self._onImageChanged)

    def _onRoiChanged(self) -> None:
        """Called when the ROI list changes (any thread)."""
        QMetaObject.invokeMethod(
            self,
            "_scheduleRender",
            Qt.AutoConnection,
        )

    def _onImageChanged(self) -> None:
        """Re-render when colormap/range changes (any thread)."""
        QMetaObject.invokeMethod(
            self,
            "_scheduleRender",
            Qt.AutoConnection,
        )

    # --- Render scheduling ---

    @Slot()
    def _scheduleRender(self) -> None:
        """Builds all display sections from current ROI data."""
        roi_data = self._cavm.selectedRoiRawData
        if roi_data is None:
            self._clearAll()
            return

        data = roi_data.copy()
        self._updateCoords()
        self._updateStatistics(data)
        self._updateHistogram(data)

    def _updateCoords(self) -> None:
        """Populates ROI origin and dimensions from the bounding box."""
        bbox = self._cavm.selectedRoiBoundingBox
        if bbox is None:
            return
        width = bbox.right - bbox.left
        height = bbox.bottom - bbox.top
        self._roi_coord_labels["roi_origin"].setText(
            f"({bbox.top}, {bbox.left})"
        )
        self._roi_coord_labels["roi_dimensions"].setText(
            f"{width} × {height}"
        )

    def _updateStatistics(self, data: np.ndarray) -> None:
        """Computes and displays ROI statistics."""
        bbox = self._cavm.selectedRoiBoundingBox
        if bbox is None:
            return
        stats = ROIStatistics.from_roi_data(
            data,
            bbox,
            self._vm.physics_manager,
        )
        self._populateStatLabels(stats)

    def _updateHistogram(self, data: np.ndarray) -> None:
        """Builds a histogram model and pushes it to the widget."""
        cmap_enum = self._cavm.clusterThumbnailColormap
        colormap_str = cmap_enum.value if cmap_enum is not None else None

        if self._cavm.displayEnergyInKev:
            data = self._vm.physics_manager.adu_to_kev(data)
            x_label = "Energy (keV)"
            x_unit = "keV"
        else:
            x_label = "Energy (ADU)"
            x_unit = "ADU"

        model = HistogramDataModel.from_pixel_data(
            data,
            _HISTOGRAM_BINS,
            x_label,
            colormap_str,
            x_unit=x_unit,
        )
        self._histogram.setData(model)

    def _clearAll(self) -> None:
        """Resets all sections when no ROI is selected."""
        self._histogram.setData(None)
        for label in self._stat_labels.values():
            label.setText("—")
        for label in self._roi_coord_labels.values():
            label.setText("—")

    def _populateStatLabels(self, stats: ROIStatistics) -> None:
        """Formats ROIStatistics values into the stat labels."""
        self._stat_labels["max_energy"].setText(
            f"{stats.max_kev:.4f} keV / {stats.max_adu:.1f} ADU\n"
            f"ROI {stats.max_roi_coord}  Abs {stats.max_abs_coord}"
        )
        self._stat_labels["min_energy"].setText(
            f"{stats.min_kev:.4f} keV / {stats.min_adu:.1f} ADU\n"
            f"ROI {stats.min_roi_coord}  Abs {stats.min_abs_coord}"
        )
        self._stat_labels["mean_energy"].setText(
            f"{stats.mean_kev:.4f} keV / {stats.mean_adu:.1f} ADU"
        )
        self._stat_labels["sigma"].setText(
            f"{stats.sigma_kev:.4f} keV / {stats.sigma_adu:.1f} ADU"
        )
        self._stat_labels["pixel_count"].setText(
            f"{stats.pixel_count} total, {stats.nonzero_count} non-zero"
        )
