from PySide6.QtCore import Qt, Slot, QMetaObject
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
    HistoricalMode,
)
from ..viewmodels.HistoricalEventInspectorViewModel import (
    HistoricalEventInspectorViewModel,
)
from ..views.HistoricalEventInspector import (
    HistoricalEventInspector,
)
from ..widgets.EventGridWidget import EventGridWidget


class _Style:
    BROWSER_PANEL = "background-color: #2d2d2d;"
    INSPECTOR_PANEL = "background-color: #f0f0f0; color: #000000;"
    HEADER = (
        "font-weight: bold;"
        "font-size: 14px;"
        "color: white;"
    )
    MODE_LIVE = "color: red; font-weight: bold;"
    MODE_HISTORICAL = "color: #cccccc;"
    LOAD_BTN = (
        "QPushButton {"
        "  background-color: #0078d7;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "  padding: 6px 16px;"
        "  font-weight: bold;"
        "}"
        "QPushButton:hover {"
        "  background-color: #005fa3;"
        "}"
        "QPushButton:disabled {"
        "  background-color: #555555;"
        "  color: #999999;"
        "}"
    )
    HEADER_BAR = "background-color: #1e1e1e; padding: 4px;"
    COUNT_LABEL = "color: #aaaaaa; font-size: 11px;"


class HistoricalView(QWidget):
    """View for the Historical Event Analysis tab.

    Provides a two-panel layout with an event grid browser
    on the left and a detail inspector on the right, connected
    via a ``QSplitter``.
    """

    def __init__(self, viewModel: HistoricalViewModel):
        super().__init__()
        self.viewModel = viewModel
        self._initUI()
        self._bindViewModel()

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._buildHeaderBar())
        root.addWidget(self._buildSplitter(), 1)
        self._applyGridConfig()

    def _buildHeaderBar(self) -> QWidget:
        """Creates the top bar with title, mode, count and load button."""
        header = QWidget()
        header.setStyleSheet(_Style.HEADER_BAR)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)

        self._titleLabel = QLabel(
            self.tr("Historical Event Analysis")
        )
        self._titleLabel.setStyleSheet(_Style.HEADER)
        layout.addWidget(self._titleLabel)

        self._modeLabel = QLabel()
        layout.addWidget(self._modeLabel)
        layout.addStretch()

        self._countLabel = QLabel()
        self._countLabel.setStyleSheet(_Style.COUNT_LABEL)
        layout.addWidget(self._countLabel)

        self._loadBtn = QPushButton(self.tr("Load Events"))
        self._loadBtn.setStyleSheet(_Style.LOAD_BTN)
        self._loadBtn.clicked.connect(self._onLoadClicked)
        layout.addWidget(self._loadBtn)

        return header

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
        self._inspector = HistoricalEventInspector(
            self._inspectorVM
        )
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

        default_cols = int(cfg.get(
            "gui:historical:grid_default_columns", 2
        ))
        max_cols = int(cfg.get(
            "gui:historical:grid_max_columns", 3
        ))
        self._gridWidget.setColumnConstraints(
            default_cols, max_cols
        )

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
            lambda: QMetaObject.invokeMethod(
                self, "_updateEvents", Qt.AutoConnection
            )
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
        self._gridWidget.eventSelected.connect(
            self._onGridItemSelected
        )

    def _configureInspector(self) -> None:
        """Applies view-level settings to the inspector.

        Configuration (physics, threshold, keV toggle) is passed
        via the ``HistoricalEventInspectorViewModel`` constructor.
        Only the colormap (a view concern) is set here.
        """
        pass

    def _configureGridWidget(self) -> None:
        """Wires ViewModel properties into the event grid."""
        self._gridWidget.setPhysicsManager(
            self.viewModel.physicsManager
        )
        self._gridWidget.setDisplayEnergyInKev(
            self.viewModel.displayEnergyInKev
        )
        self._gridWidget.setClassificationThreshold(
            self.viewModel.classificationThreshold
        )

    # --- Slots ---

    @Slot()
    def _updateMode(self) -> None:
        mode = self.viewModel.mode
        if mode == HistoricalMode.LIVE:
            self._modeLabel.setText(
                self.tr("LIVE MONITORING")
            )
            self._modeLabel.setStyleSheet(_Style.MODE_LIVE)
        else:
            self._modeLabel.setText(
                self.tr("Historical")
            )
            self._modeLabel.setStyleSheet(_Style.MODE_HISTORICAL)

    @Slot()
    def _updateEvents(self) -> None:
        events = self.viewModel.events
        self._gridWidget.setEvents(events)
        count = len(events)
        if count == 0:
            self._countLabel.setText(self.tr("No events"))
        elif count == 1:
            self._countLabel.setText(self.tr("1 event"))
        else:
            self._countLabel.setText(
                self.tr("{count} events").format(count=count)
            )

    @Slot()
    def _updateSelection(self) -> None:
        cluster = self.viewModel.selectedEvent
        index = self.viewModel.selectedIndex
        self._gridWidget.setSelectedIndex(index)
        self._inspector.setEvent(cluster)

    @Slot()
    def _updateLoading(self) -> None:
        loading = self.viewModel.isLoading
        self._loadBtn.setEnabled(not loading)
        if loading:
            self._loadBtn.setText(self.tr("Loading..."))
        else:
            self._loadBtn.setText(self.tr("Load Events"))

    def _onLoadClicked(self) -> None:
        self.viewModel.loadEvents()

    def _onGridItemSelected(self, index: int) -> None:
        self.viewModel.selectEvent(index)
