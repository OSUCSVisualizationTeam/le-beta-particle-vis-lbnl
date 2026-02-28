"""Widget displaying the energy histogram for the active ROI.

Renders the histogram asynchronously on a daemon thread following
the same pattern as ``HistoricalEventInspector``.
"""
from __future__ import annotations

import logging
import threading
from queue import Queue
from typing import TYPE_CHECKING, Optional

import numpy as np

from PySide6.QtCore import QMetaObject, Qt, QTimer, Slot, Q_ARG
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.HistogramRenderer import (
    MatplotlibHistogramRenderer,
)

if TYPE_CHECKING:
    from le_beta_vis.frontend.viewmodels.RawDataViewModel import (
        RawDataViewModel,
    )

logger = logging.getLogger(__name__)

_HISTOGRAM_BINS = 50
_HISTOGRAM_DPI = 100
_HISTOGRAM_MIN_W = 180
_HISTOGRAM_MIN_H = 150
_RESIZE_DEBOUNCE_MS = 200


class _Style:
    HEADER = "font-weight: bold; font-size: 13px; color: #333333;"
    PLACEHOLDER = (
        "color: #999999; font-style: italic; padding: 20px;"
    )


class ROIInfoWidget(QWidget):
    """Async ROI energy histogram display."""

    def __init__(
        self,
        viewModel: RawDataViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._renderer = MatplotlibHistogramRenderer()

        # Async state
        self._render_queue: Queue = Queue(maxsize=1)
        self._histogram_generation: int = 0
        self._pending_histogram_bytes: Optional[bytes] = None

        self._initUI()
        self._startWorker()
        self._bindViewModel()

        # Resize debounce
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._onResizeSettled)

    # --- UI ---

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        header = QLabel(self.tr("Energy Distribution"))
        header.setStyleSheet(_Style.HEADER)
        layout.addWidget(header)

        self._histogramLabel = QLabel(
            self.tr("Draw an ROI to see energy distribution")
        )
        self._histogramLabel.setStyleSheet(_Style.PLACEHOLDER)
        self._histogramLabel.setAlignment(Qt.AlignCenter)
        self._histogramLabel.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding,
        )
        self._histogramLabel.setWordWrap(True)
        layout.addWidget(self._histogramLabel, 1)

    # --- ViewModel bindings ---

    def _bindViewModel(self) -> None:
        self._vm.add_roi_changed_callback(self._onRoiChanged)
        self._vm.add_image_changed_callback(self._onImageChanged)

    def _onRoiChanged(self) -> None:
        """Called when the ROI list changes (any thread)."""
        QMetaObject.invokeMethod(
            self, "_scheduleRender", Qt.AutoConnection,
        )

    def _onImageChanged(self) -> None:
        """Re-render when colormap/range changes (any thread)."""
        QMetaObject.invokeMethod(
            self, "_scheduleRender", Qt.AutoConnection,
        )

    # --- Render scheduling ---

    @Slot()
    def _scheduleRender(self) -> None:
        """Enqueues a histogram render if ROI data exists."""
        roi_data = self._vm.selectedRoiRawData
        if roi_data is None:
            self._histogramLabel.setPixmap(QPixmap())
            self._histogramLabel.setText(
                self.tr("Draw an ROI to see energy distribution")
            )
            self._histogramLabel.setStyleSheet(_Style.PLACEHOLDER)
            return
        self._requestHistogram(roi_data)

    def _requestHistogram(self, data: "np.ndarray") -> None:
        """Enqueues data for background rendering."""
        self._histogram_generation += 1
        gen = self._histogram_generation
        self._histogramLabel.setText(self.tr("Rendering..."))
        self._histogramLabel.setStyleSheet(_Style.PLACEHOLDER)

        # Determine colormap string
        cmap_enum = self._vm.clusterThumbnailColormap
        colormap_str = cmap_enum.value if cmap_enum is not None else None

        # Determine x-label and convert if needed
        display_kev = self._vm.displayEnergyInKev
        if display_kev:
            data = data.copy() * self._vm.kevConversion
            x_label = "Energy (keV)"
        else:
            data = data.copy()
            x_label = "Energy (ADU)"

        # Drain stale requests
        while not self._render_queue.empty():
            try:
                self._render_queue.get_nowait()
            except Exception:
                break

        self._render_queue.put((
            data, gen,
            self._histogramWidth(), self._histogramHeight(),
            x_label, colormap_str,
        ))

    # --- Sizing ---

    def _histogramWidth(self) -> int:
        """Available width for histogram rendering."""
        w = self.width() - 16
        return max(w, _HISTOGRAM_MIN_W)

    def _histogramHeight(self) -> int:
        """Proportional height for histogram rendering."""
        h = int(self.height() * 0.7)
        return max(h, _HISTOGRAM_MIN_H)

    # --- Resize debounce ---

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Debounces resize to re-render at the new size."""
        super().resizeEvent(event)
        if self._vm.selectedRoiRawData is not None:
            self._resize_timer.start()

    def _onResizeSettled(self) -> None:
        """Re-renders histogram after resize settles."""
        self._scheduleRender()

    # --- Background worker ---

    def _startWorker(self) -> None:
        """Starts a daemon thread for histogram rendering."""
        thread = threading.Thread(
            target=self._workerLoop, daemon=True,
        )
        thread.start()

    def _workerLoop(self) -> None:
        """Background loop that renders histograms."""
        while True:
            data, generation, width, height, x_label, colormap = (
                self._render_queue.get()
            )
            try:
                png_bytes = self._renderer.render_energy_histogram(
                    data, _HISTOGRAM_BINS,
                    width, height, _HISTOGRAM_DPI,
                    x_label=x_label,
                    colormap=colormap,
                )
                self._pending_histogram_bytes = png_bytes
                QMetaObject.invokeMethod(
                    self,
                    "_applyHistogram",
                    Qt.QueuedConnection,
                    Q_ARG(int, generation),
                )
            except Exception:
                logger.exception("ROI histogram render failed")

    @Slot(int)
    def _applyHistogram(self, generation: int) -> None:
        """Applies the rendered histogram if still current."""
        if generation != self._histogram_generation:
            return
        png_bytes = self._pending_histogram_bytes
        if png_bytes is None:
            return
        pixmap = QPixmap()
        pixmap.loadFromData(png_bytes, "PNG")
        scaled = pixmap.scaled(
            self._histogramLabel.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._histogramLabel.setStyleSheet("")
        self._histogramLabel.setPixmap(scaled)
