from PySide6.QtCore import Qt, Slot, QMetaObject
from PySide6.QtWidgets import (
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
    HistoricalMode,
)
from ..viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)
from ..viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from ..views.HistoricalEventInspector import (
    HistoricalEventInspector,
)
from ..widgets.EventGridWidget import EventGridWidget
from ..widgets.HistoricalFilterBar import HistoricalFilterBar


class _Style:
    BROWSER_PANEL = "background-color: #2d2d2d;"
    INSPECTOR_PANEL = "background-color: #f0f0f0; color: #000000;"
    MODE_LIVE = "color: red; font-weight: bold;"
    MODE_HISTORICAL = "color: #cccccc;"


class HistoricalView(QWidget):
    """View for the Historical Event Analysis tab.

    Provides a two-panel layout with an event grid browser
    on the left and a detail inspector on the right, connected
    via a ``QSplitter``.  A filter toolbar between the header
    and splitter lets scientists constrain queries.
    """

    def __init__(self, viewModel: HistoricalViewModel):
        super().__init__()
        self.viewModel = viewModel
        self._pendingFilter = None
        self._initUI()
        self._bindViewModel()

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._buildFilterBar())
        root.addWidget(self._buildSplitter(), 1)
        self._applyGridConfig()

    def _buildFilterBar(self) -> QWidget:
        """Creates the filter toolbar below the header."""
        self._filterBarVM = HistoricalFilterBarViewModel(
            configService=self.viewModel._config,
            physicsManager=self.viewModel.physicsManager,
        )
        self._filterBarVM.add_filter_applied_callback(self._onFilterApplied)
        self._filterBar = HistoricalFilterBar(self._filterBarVM)
        return self._filterBar

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
            histogramRenderer=self.viewModel.histogramRenderer,
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
        w = int(cfg.get("gui:historical:grid_item_width", 140))
        h = int(cfg.get("gui:historical:grid_item_height", 160))
        self._gridWidget.setGridSize(w, h)

        default_cols = int(cfg.get("gui:historical:grid_default_columns", 2))
        max_cols = int(cfg.get("gui:historical:grid_max_columns", 3))
        self._gridWidget.setColumnConstraints(default_cols, max_cols)

    def _bindViewModel(self) -> None:
        """Connects ViewModel callbacks to View update slots."""
        self._connectViewModelCallbacks()
        self._configureInspector()
        self._configureGridWidget()
        self._updateMode()

    def _connectViewModelCallbacks(self) -> None:
        """Registers ViewModel observers and grid signals."""
        self.viewModel.add_mode_changed_callback(
            lambda mode: QMetaObject.invokeMethod(
                self, "_updateMode", Qt.AutoConnection
            )
        )
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
        self._gridWidget.eventSelected.connect(self._onGridItemSelected)

    def _configureInspector(self) -> None:
        """Applies view-level settings to the inspector.

        Configuration (physics, threshold, keV toggle) is passed
        via the ``HistoricalEventInspectorViewModel`` constructor.
        Only the colormap (a view concern) is set here.
        """
        pass

    def _configureGridWidget(self) -> None:
        """Wires ViewModel properties into the event grid."""
        self._gridWidget.setPhysicsManager(self.viewModel.physicsManager)
        self._gridWidget.setDisplayEnergyInKev(self.viewModel.displayEnergyInKev)
        self._gridWidget.setClassificationThreshold(
            self.viewModel.classificationThreshold
        )

    # --- Slots ---

    @Slot()
    def _updateMode(self) -> None:
        mode = self.viewModel.mode
        lbl = self._filterBar.modeLabel
        if mode == HistoricalMode.LIVE:
            lbl.setText(self.tr("LIVE MONITORING"))
            lbl.setStyleSheet(_Style.MODE_LIVE)
        else:
            lbl.setText(self.tr("Historical"))
            lbl.setStyleSheet(_Style.MODE_HISTORICAL)

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
        self._inspector.setEvent(cluster)

    @Slot()
    def _updateLoading(self) -> None:
        loading = self.viewModel.isLoading
        self._filterBar._applyBtn.setEnabled(not loading)
        if loading:
            self._filterBar._applyBtn.setText(self.tr("Loading..."))
        else:
            self._filterBar._applyBtn.setText(self.tr("Apply"))

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
