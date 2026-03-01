import logging
import threading
from queue import Queue
from typing import Optional

from PySide6.QtCore import Qt, QMetaObject, QTimer, Slot, Q_ARG
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)

logger = logging.getLogger(__name__)

_HIGH_RES_SIZE = 256
_HISTOGRAM_H = 200
_HISTOGRAM_DPI = 100
_HISTOGRAM_BINS = 50
_HISTOGRAM_MIN_W = 200
_HISTOGRAM_MIN_H = 200
_RESIZE_DEBOUNCE_MS = 200


class _Style:
    PANEL = (
        "background-color: #f0f0f0;"
        "color: #000000;"
    )
    SECTION_HEADER = (
        "font-weight: bold;"
        "font-size: 13px;"
        "color: #333333;"
        "padding-top: 8px;"
    )
    PLACEHOLDER = (
        "color: #999999;"
        "font-style: italic;"
        "padding: 20px;"
    )


class HistoricalEventInspector(QWidget):
    """View for displaying detailed information about a selected event.

    Uses ``HistoricalEventInspectorViewModel`` for all formatting
    and display logic.  The thumbnail is rendered via
    ``EnergyClusterWidget`` and the histogram is produced
    asynchronously on a background thread.
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
        self._histogram_generation: int = 0
        self._pending_histogram_bytes: Optional[bytes] = None
        self._render_queue: Queue = Queue(maxsize=1)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._onResizeSettled)
        self._initUI()
        self._startHistogramWorker()

    def _initUI(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(_Style.PANEL)
        outer.addWidget(scroll)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(container)

        # Placeholder shown when nothing is selected
        self._placeholder = QLabel(
            self.tr("Select an event to inspect")
        )
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

        detail.addStretch()
        self._detailWidget.setVisible(False)
        self._layout.addWidget(self._detailWidget)

    def _createTopSection(self) -> QHBoxLayout:
        """Creates side-by-side thumbnail + rich-text detail."""
        top = QHBoxLayout()
        top.setSpacing(16)

        # Left column: cluster image
        leftCol = QVBoxLayout()
        self._imageWidget = EnergyClusterWidget(
            size=_HIGH_RES_SIZE
        )
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

    def _createHistogramSection(
        self, parent: QVBoxLayout
    ) -> None:
        """Creates the energy histogram section."""
        header = QLabel(self.tr("Energy Distribution"))
        header.setStyleSheet(_Style.SECTION_HEADER)
        parent.addWidget(header)

        self._histogramLabel = QLabel()
        self._histogramLabel.setAlignment(Qt.AlignCenter)
        self._histogramLabel.setMinimumHeight(_HISTOGRAM_MIN_H)
        parent.addWidget(self._histogramLabel)

    # --- Public interface ---

    def setEvent(self, cluster: Optional[Cluster]) -> None:
        """Updates the inspector with the given cluster's details.

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

        self._imageWidget.setCluster(
            cluster.data, self._colormap
        )
        self._detailLabel.setText(
            self._vm.formatDetailHtml(cluster)
        )
        self._requestHistogram(cluster)

    def clear(self) -> None:
        """Resets the inspector to its empty state."""
        self._current_cluster = None
        self._placeholder.setVisible(True)
        self._detailWidget.setVisible(False)

    def setColormap(self, colormap: Optional[Colormap]) -> None:
        """Sets the colormap for the high-res image.

        Args:
            colormap: Colormap enum or None for grayscale.
        """
        self._colormap = colormap

    # --- Resize ---

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Debounces resize to re-render histogram at new size."""
        super().resizeEvent(event)
        if self._current_cluster is not None:
            self._resize_timer.start()

    def _onResizeSettled(self) -> None:
        """Re-renders histogram after resize settles."""
        if self._current_cluster is not None:
            self._requestHistogram(self._current_cluster)

    # --- Async histogram ---

    def _startHistogramWorker(self) -> None:
        """Starts a daemon thread for histogram rendering."""
        thread = threading.Thread(
            target=self._histogramWorkerLoop, daemon=True
        )
        thread.start()

    def _histogramWidth(self) -> int:
        """Returns the available width for histogram rendering."""
        w = self._detailWidget.width() - 16
        return max(w, _HISTOGRAM_MIN_W)

    def _histogramHeight(self) -> int:
        """Returns proportional height (40% of widget, min 200)."""
        h = int(self.height() * 0.4)
        return max(h, _HISTOGRAM_MIN_H)

    def _requestHistogram(self, cluster: Cluster) -> None:
        """Enqueues a histogram render, discarding stale requests."""
        self._histogram_generation += 1
        gen = self._histogram_generation
        self._histogramLabel.setText(self.tr("Rendering..."))

        hist_data = cluster.data.copy()
        x_label = self._vm.formatHistogramXLabel(cluster)
        if self._vm.physics and self._vm.displayKeV:
            hist_data = self._vm.physics.adu_to_kev(hist_data)

        # Drain stale requests
        while not self._render_queue.empty():
            try:
                self._render_queue.get_nowait()
            except Exception:
                break
        self._render_queue.put((
            hist_data, gen,
            self._histogramWidth(), self._histogramHeight(),
            x_label,
        ))

    def _histogramWorkerLoop(self) -> None:
        """Background loop that renders histograms."""
        while True:
            data, generation, width, height, x_label = (
                self._render_queue.get()
            )
            try:
                png_bytes = self._vm.renderer.render_energy_histogram(
                    data, _HISTOGRAM_BINS,
                    width, height, _HISTOGRAM_DPI,
                    x_label=x_label,
                )
                self._pending_histogram_bytes = png_bytes
                QMetaObject.invokeMethod(
                    self,
                    "_applyHistogram",
                    Qt.QueuedConnection,
                    Q_ARG(int, generation),
                )
            except Exception:
                logger.exception("Histogram render failed")

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
        self._histogramLabel.setPixmap(pixmap)
