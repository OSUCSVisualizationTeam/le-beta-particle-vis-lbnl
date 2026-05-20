from ..widgets.ExportOptionsDialog import ExportOptionsDialog
from ..widgets.ProgressOverlay import ProgressOverlay
from ..widgets.HistoricalFilterBar import HistoricalFilterBar
from ..widgets.EventGridWidget import EventGridWidget
from ..views.HistoricalEventInspector import (
    HistoricalEventInspector,
)
from ..viewmodels.MainWindowStatusViewModel import MainWindowStatusViewModel
from ..viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from ..viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)
from ..viewmodels.HistoricalViewModel import HistoricalViewModel
from ..viewmodels.HistoricalExportViewModel import HistoricalExportViewModel
from le_beta_vis.export.ClusterExportService import ClusterMetadataLabels
from le_beta_vis.export.DirectPNGClusterExportService import (
    DirectPNGClusterExportService,
)
from le_beta_vis.export.H5ExportStorageService import H5ExportStorageService
from le_beta_vis.export.HistoricalExportService import HistoricalExportService
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, Slot, QMetaObject, Signal
import numpy as np
import collections
import logging
from pathlib import Path
from typing import Callable, Optional

from le_beta_vis.common.Cluster import Cluster

logger = logging.getLogger(__name__)


class _Style:
    BROWSER_PANEL = "background-color: #2d2d2d;"
    INSPECTOR_PANEL = "background-color: #f0f0f0; color: #000000;"


class HistoricalView(QWidget):
    """View for the Historical Event Analysis tab.

    Provides a two-panel layout with an event grid browser
    on the left and a detail inspector on the right, connected
    via a ``QSplitter``.  A filter toolbar between the header
    and splitter lets scientists constrain queries.
    """

    _exportProgressReceived = Signal(int, int, str)
    _exportCompleteReceived = Signal(Path)
    _exportErrorReceived = Signal(str)
    _exportCancelledReceived = Signal()

    def __init__(
        self,
        viewModel: HistoricalViewModel,
        statusViewModel: Optional[MainWindowStatusViewModel] = None,
        openInRawDataHandler: Optional[Callable[[Cluster], None]] = None,
    ):
        super().__init__()
        self.viewModel = viewModel
        self._statusVM = statusViewModel
        self._openInRawDataHandler = openInRawDataHandler
        self._pendingFilter = None
        self._pendingLoadError: Optional[str] = None
        self._thumbnailQueue: collections.deque = collections.deque()
        self._pendingClusterData: Optional[np.ndarray] = None
        self._progressToken: Optional[str] = None
        self._exportVM: Optional[HistoricalExportViewModel] = None
        self._initUI()
        self._bindViewModel()

    @property
    def export_viewmodel(self) -> Optional[HistoricalExportViewModel]:
        """The export ViewModel, available after ``_buildExportViewModel`` runs."""
        return self._exportVM

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._buildFilterBar())
        root.addWidget(self._buildSplitter(), 1)
        self._loadingOverlay = ProgressOverlay(
            title=self.tr("Loading Events"), parent=self,
        )
        self._applyGridConfig()

    def _buildFilterBar(self) -> QWidget:
        """Creates the filter toolbar below the header."""
        self._filterBarVM = HistoricalFilterBarViewModel(
            configService=self.viewModel._config,
            physicsManager=self.viewModel.physicsManager,
        )
        self._filterBarVM.add_filter_applied_callback(self._onFilterApplied)
        self._filterBar = HistoricalFilterBar(self._filterBarVM)
        self._buildExportViewModel()
        self._filterBar.saveClicked.connect(self._onSaveClicked)
        self._filterBar.cancelClicked.connect(self._onCancelClicked)
        self._refreshSaveGating()
        return self._filterBar

    def _buildExportViewModel(self) -> None:
        """Constructs the ExportViewModel + service graph (issue #56)."""
        physics = self.viewModel.physicsManager
        storage = H5ExportStorageService(physics)
        png = DirectPNGClusterExportService()
        n_workers = int(self.viewModel._config.get("gui:export:png_render_workers", 4))
        service = HistoricalExportService(
            repository=self.viewModel.repository,
            storage=storage,
            png_renderer=png,
            physics=physics,
            thumbnail_service=self.viewModel.thumbnail_service,
            png_render_workers=n_workers,
        )
        self._exportVM = HistoricalExportViewModel(
            config=self.viewModel._config,
            physics=physics,
            export_service=service,
            filter_bar_vm=self._filterBarVM,
        )
        self._exportCompleteReceived.connect(self._onExportComplete)
        self._exportErrorReceived.connect(self._onExportError)
        self._exportProgressReceived.connect(self._onExportProgress)
        self._exportCancelledReceived.connect(self._onExportCancelled)
        self._exportVM.add_complete_callback(self._exportCompleteReceived.emit)
        self._exportVM.add_error_callback(self._exportErrorReceived.emit)
        self._exportVM.add_progress_callback(self._exportProgressReceived.emit)
        self._exportVM.add_cancelled_callback(self._exportCancelledReceived.emit)
        self._exportVM.add_gating_changed_callback(self._onExportGatingChanged)
        self._filterBarVM.add_filter_applied_callback(
            lambda _: self._refreshSaveGating()
        )
        self._filterBarVM.add_filter_reset_callback(self._refreshSaveGating)

    def _buildSplitter(self) -> QSplitter:
        """Creates the horizontal splitter with grid and inspector."""
        self._splitter = QSplitter(Qt.Horizontal)

        self._gridWidget = EventGridWidget()
        self._gridWidget.setStyleSheet(_Style.BROWSER_PANEL)
        self._splitter.addWidget(self._gridWidget)

        self._inspectorVM = HistoricalEventInspectorViewModel(
            physics=self.viewModel.physicsManager,
            threshold=self.viewModel.classificationThreshold,
            displayKeV=self.viewModel.displayEnergyInKev,
        )
        if self._openInRawDataHandler is not None:
            self._inspectorVM.setOpenInRawDataHandler(
                self._openInRawDataHandler
            )
        self._inspector = HistoricalEventInspector(self._inspectorVM)
        self._splitter.addWidget(self._inspector)

        # Grid takes only its preferred width; inspector fills the rest
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        return self._splitter

    def _applyGridConfig(self) -> None:
        """Reads grid configuration and applies size constraints."""
        cfg = self.viewModel._config
        w = cfg.get_int("gui:historical:grid_item_width", 140)
        h = cfg.get_int("gui:historical:grid_item_height", 160)
        self._gridWidget.setGridSize(w, h)

        default_cols = cfg.get_int("gui:historical:grid_default_columns", 2)
        max_cols = cfg.get_int("gui:historical:grid_max_columns", 3)
        self._gridWidget.setColumnConstraints(default_cols, max_cols)

        header_h = cfg.get_int("gui:historical:grid_section_header_height", 48)
        self._gridWidget.setHeaderHeight(header_h)

    def _bindViewModel(self) -> None:
        """Connects ViewModel callbacks to View update slots."""
        self._connectViewModelCallbacks()
        self._configureInspector()
        self._configureGridWidget()

    def _connectViewModelCallbacks(self) -> None:
        """Registers ViewModel observers and grid signals."""
        self.viewModel.add_events_changed_callback(
            lambda: QMetaObject.invokeMethod(self, "_updateEvents", Qt.AutoConnection)
        )
        self.viewModel.add_selected_event_changed_callback(
            lambda: QMetaObject.invokeMethod(
                self, "_updateSelection", Qt.AutoConnection
            )
        )
        self.viewModel.add_loading_changed_callback(
            lambda loading: QMetaObject.invokeMethod(
                self, "_updateLoading", Qt.AutoConnection
            )
        )
        self.viewModel.add_load_error_callback(self._onLoadError)
        self._gridWidget.eventSelected.connect(self._onGridItemSelected)
        self._gridWidget.visibleRangeChanged.connect(
            self.viewModel.request_thumbnails_for_range,
        )
        self._gridWidget.prefetchRequested.connect(
            self.viewModel.prefetch_thumbnails,
        )
        self.viewModel.add_thumbnail_ready_callback(self._enqueueThumbnail)

    def _configureInspector(self) -> None:
        """Applies view-level settings to the inspector.

        Configuration (physics, threshold, keV toggle) is passed
        via the ``HistoricalEventInspectorViewModel`` constructor.
        Only the colormap (a view concern) is set here.
        """
        self._inspector.setColormap(self.viewModel.thumbnailColormap)

    def _configureGridWidget(self) -> None:
        """Wires ViewModel properties into the event grid."""
        cfg = self.viewModel._config
        self._gridWidget.setPhysicsManager(self.viewModel.physicsManager)
        self._gridWidget.setDisplayEnergyInKev(self.viewModel.displayEnergyInKev)
        self._gridWidget.setClassificationThreshold(
            self.viewModel.classificationThreshold
        )
        self._gridWidget.setPrefetchCount(
            cfg.get_int("gui:historical:prefetch_thumbnail_count", 30)
        )
        self._gridWidget.setSmoothScaling(
            cfg.get_bool("gui:historical:thumbnail_smooth_scaling", False)
        )

    # --- Slots ---

    @Slot()
    def _updateEvents(self) -> None:
        events = self.viewModel.events
        self._gridWidget.setEvents(events)
        count = len(events)
        lbl = self._filterBar.countLabel
        if count == 0:
            lbl.setText(self.tr("No events"))
        elif count == 1:
            lbl.setText(self.tr("1 event"))
        else:
            lbl.setText(self.tr("{count} events").format(count=count))

    @Slot()
    def _updateSelection(self) -> None:
        cluster = self.viewModel.selectedEvent
        index = self.viewModel.selectedIndex
        self._gridWidget.setSelectedIndex(index)
        if cluster is None:
            self._inspector.setEvent(None)
            return
        self._inspector.setEvent(cluster)
        self.viewModel.request_selected_cluster_data(
            self._onClusterDataReady,
        )

    def _onClusterDataReady(self, data: Optional[np.ndarray]) -> None:
        """Callback from service with raw cluster data — may be on bg thread."""
        self._pendingClusterData = data
        QMetaObject.invokeMethod(
            self, "_applyClusterData", Qt.AutoConnection,
        )

    @Slot()
    def _applyClusterData(self) -> None:
        """Apply raw cluster data to the inspector on the main thread."""
        data = self._pendingClusterData
        self._pendingClusterData = None
        self._inspector.updateClusterData(data)

    @Slot()
    def _updateLoading(self) -> None:
        loading = self.viewModel.isLoading
        self._filterBar._applyBtn.setEnabled(not loading)
        if loading:
            self._filterBar._applyBtn.setText(self.tr("Loading..."))
            self._loadingOverlay.showOverlay()
        else:
            self._filterBar._applyBtn.setText(self.tr("Apply"))
            self._loadingOverlay.hideOverlay()

    # --- Export slots (issue #56) ---

    def _refreshSaveGating(self) -> None:
        if self._exportVM is None:
            return
        ok, reason = self._exportVM.gating_reason()
        self._filterBar.setSaveEnabled(ok, self.tr(reason) if reason else "")

    def _onSaveClicked(self) -> None:
        if self._exportVM is None:
            return
        include_pngs = ExportOptionsDialog.ask(self)
        if include_pngs is None:
            return
        default_dir = self._exportVM.default_export_path
        if include_pngs:
            file_filter = self.tr("ZIP archive (*.zip)")
            expected_suffix = ".zip"
        else:
            file_filter = self.tr("HDF5 (*.h5)")
            expected_suffix = ".h5"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Export"),
            default_dir,
            file_filter,
        )
        if not path_str:
            return
        out = Path(path_str)
        if out.suffix.lower() != expected_suffix:
            out = out.with_suffix(expected_suffix)
        query_filter = self._filterBarVM.build_filter()
        if self._statusVM is not None:
            self._progressToken = self._statusVM.begin_progress(
                self.tr("Exporting results..."), cancelable=True
            )
            self._statusVM.add_cancel_callback(
                self._progressToken, self._onCancelClicked
            )
        self._exportVM.export(
            out, query_filter, labels=self._buildMetadataLabels(), include_pngs=include_pngs
        )

    def _buildMetadataLabels(self) -> ClusterMetadataLabels:
        """Pre-translates the PNG metadata labels via Qt's tr().

        Services in common/ stay headless — Qt's translation layer lives
        here in the View.
        """
        return ClusterMetadataLabels(
            energy=self.tr("Energy"),
            pixels=self.tr("Num. pixels"),
            sigma_x=self.tr("σx"),
            sigma_y=self.tr("σy"),
            full_width_x=self.tr("Full width x"),
            full_width_y=self.tr("Full width y"),
            energy_per_pixel=self.tr("Energy per pixel"),
            peak_xy=self.tr("Peak xy"),
            selection=self.tr("Selection"),
            kev_unit=self.tr("keV"),
            colorbar=self.tr("Pixel energy [keV]"),
            x_axis=self.tr("Pixel x"),
            y_axis=self.tr("Pixel y"),
        )

    def _onCancelClicked(self) -> None:
        if self._exportVM is None:
            return
        reply = QMessageBox.question(
            self,
            self.tr("Cancel Export"),
            self.tr(
                "Are you sure you want to cancel the export?\n"
                "The output file will not be saved."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._exportVM.cancel()

    def _onExportProgress(self, done: int, total: int, stage: str) -> None:
        if self._statusVM is None or self._progressToken is None:
            return
        fraction = self._exportVM.aggregated_fraction(done, total, stage)
        label = {
            "query": self.tr("Querying clusters..."),
            "fits": self.tr("Loading pixel data ({done}/{total})"),
            "h5": self.tr("Writing HDF5 ({done}/{total})"),
            "png": self.tr("Rendering thumbnails ({done}/{total})"),
        }.get(stage, stage)
        if "{" in label:
            label = label.format(done=done, total=total)
        self._statusVM.update_progress(self._progressToken, fraction, message=label)

    def _onExportComplete(self, out_path: Path) -> None:
        self._endProgress()
        self._lastExportPath = out_path
        self._showExportSuccess()

    def _onExportError(self, message: str) -> None:
        logger.error("Export error received in view: %s", message)
        self._endProgress()
        self._pendingExportError = message
        self._showExportError()

    def _onExportGatingChanged(self, enabled: bool, reason: str) -> None:
        self._filterBar.setSaveEnabled(enabled, self.tr(reason) if reason else "")

    def _endProgress(self) -> None:
        if self._statusVM is not None and self._progressToken is not None:
            self._statusVM.end_progress(self._progressToken)
            self._progressToken = None

    @Slot()
    def _showExportSuccess(self) -> None:
        path = getattr(self, "_lastExportPath", None)
        QMessageBox.information(
            self,
            self.tr("Export complete"),
            self.tr("Export written to {path}").format(path=str(path)),
        )

    @Slot()
    def _showExportError(self) -> None:
        msg = getattr(self, "_pendingExportError", None) or self.tr(
            "An unknown error occurred while exporting."
        )
        self._pendingExportError = None
        QMessageBox.warning(self, self.tr("Export Failed"), msg)

    @Slot()
    def _onExportCancelled(self) -> None:
        self._endProgress()
        self._showExportCancelled()

    @Slot()
    def _showExportCancelled(self) -> None:
        QMessageBox.information(
            self,
            self.tr("Export Cancelled"),
            self.tr("The export was cancelled. No file was written."),
        )

    def _onLoadError(self, message: str) -> None:
        """Receives error from ViewModel — may arrive on bg thread."""
        self._pendingLoadError = message
        QMetaObject.invokeMethod(
            self, "_showLoadError", Qt.AutoConnection,
        )

    @Slot()
    def _showLoadError(self) -> None:
        """Displays a warning dialog with the load error message."""
        msg = self._pendingLoadError or self.tr(
            "An unknown error occurred while loading events."
        )
        self._pendingLoadError = None
        QMessageBox.warning(
            self,
            self.tr("Load Failed"),
            msg,
        )

    def _onFilterApplied(self, query_filter) -> None:
        """Receives filter from the filter bar VM and triggers load.

        Stores the filter and uses ``QMetaObject.invokeMethod``
        with ``Qt.AutoConnection`` to marshal to the main thread
        when the callback fires from a background thread.
        """
        self._pendingFilter = query_filter
        QMetaObject.invokeMethod(self, "_applyPendingFilter", Qt.AutoConnection)

    @Slot()
    def _applyPendingFilter(self) -> None:
        """Applies the stored filter and loads events."""
        if self._pendingFilter is not None:
            self.viewModel.setQueryFilter(self._pendingFilter)
            self._pendingFilter = None
        self.viewModel.loadEvents()

    def _onGridItemSelected(self, index: int) -> None:
        self.viewModel.selectEvent(index)

    def _enqueueThumbnail(
        self, key: int, buffer: np.ndarray,
    ) -> None:
        """Appends the thumbnail to the queue and marshals to the main thread."""
        self._thumbnailQueue.append((key, buffer))
        QMetaObject.invokeMethod(
            self, "_onThumbnailReady", Qt.AutoConnection,
        )

    @Slot()
    def _onThumbnailReady(self) -> None:
        """Drains the thumbnail queue, converting buffers to QPixmaps."""
        while self._thumbnailQueue:
            key, buffer = self._thumbnailQueue.popleft()
            pixmap = self._arrayToPixmap(buffer)
            self._gridWidget.updateThumbnail(key, pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._loadingOverlay.setGeometry(self.rect())

    @staticmethod
    def _arrayToPixmap(buffer: np.ndarray) -> QPixmap:
        """Convert a uint8 numpy array to a QPixmap."""
        h, w = buffer.shape[:2]
        if buffer.ndim == 3:
            q_img = QImage(
                buffer.data, w, h, 3 * w, QImage.Format_RGB888,
            )
        else:
            q_img = QImage(
                buffer.data, w, h, w, QImage.Format_Grayscale8,
            )
        return QPixmap.fromImage(q_img.copy())
