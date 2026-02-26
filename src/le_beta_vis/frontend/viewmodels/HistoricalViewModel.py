from typing import List, Callable, Optional
from enum import Enum
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.HistogramRenderer import (
    HistogramRenderer,
    MatplotlibHistogramRenderer,
)
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.Cluster import Cluster


class HistoricalMode(str, Enum):
    LIVE = "live"
    HISTORICAL = "historical"


class HistoricalViewModel:
    """ViewModel for the Historical Event Analysis mode.

    Manages mode state (Live vs Historical), event data from an
    ``EventRepository``, and the currently selected event for
    the Detail Inspector.

    Pure Python class — no Qt dependencies.
    """

    def __init__(
        self,
        configService: ConfigurationService,
        physicsManager: PhysicsConversionManager,
        repository: EventRepository,
        histogramRenderer: Optional[HistogramRenderer] = None,
    ):
        self._config = configService
        self._physics = physicsManager
        self._repository = repository
        self._histogramRenderer: HistogramRenderer = (
            histogramRenderer or MatplotlibHistogramRenderer()
        )

        # Mode state
        mode_str = self._config.get(
            "gui:historical:mode", HistoricalMode.HISTORICAL
        )
        self._mode = HistoricalMode(mode_str)

        # Event state
        self._events: List[Cluster] = []
        self._selectedIndex: int = -1
        self._loading: bool = False

        # Callbacks
        self._on_mode_changed_callbacks: List[
            Callable[[HistoricalMode], None]
        ] = []
        self._on_events_changed_callbacks: List[Callable[[], None]] = []
        self._on_selected_event_changed_callbacks: List[
            Callable[[], None]
        ] = []
        self._on_loading_changed_callbacks: List[
            Callable[[bool], None]
        ] = []

    # --- Properties ---

    @property
    def mode(self) -> HistoricalMode:
        """Current operational mode (live or historical)."""
        return self._mode

    @property
    def events(self) -> List[Cluster]:
        """List of loaded cluster events."""
        return self._events

    @property
    def selectedIndex(self) -> int:
        """Index of the selected event, or -1 if none."""
        return self._selectedIndex

    @property
    def selectedEvent(self) -> Optional[Cluster]:
        """The currently selected Cluster, or None."""
        if 0 <= self._selectedIndex < len(self._events):
            return self._events[self._selectedIndex]
        return None

    @property
    def isLoading(self) -> bool:
        """True while events are being fetched."""
        return self._loading

    @property
    def physicsManager(self) -> PhysicsConversionManager:
        """The physics conversion manager for ADU/keV display."""
        return self._physics

    @property
    def histogramRenderer(self) -> HistogramRenderer:
        """The histogram rendering service."""
        return self._histogramRenderer

    @property
    def classificationThreshold(self) -> float:
        """Classification confidence threshold from configuration."""
        return float(self._config.get(
            "gui:historical:classification_threshold", 0.75
        ))

    @property
    def displayEnergyInKev(self) -> bool:
        """Whether cluster energy should be displayed in keV."""
        return bool(self._config.get(
            "gui:raw_analysis:display_energy_in_kev", True
        ))

    # --- Commands ---

    def setMode(self, mode: HistoricalMode) -> None:
        """Sets the operational mode.

        Args:
            mode: The new mode to switch to.

        Raises:
            ValueError: If *mode* is not a valid HistoricalMode.
        """
        if not isinstance(mode, HistoricalMode):
            try:
                mode = HistoricalMode(mode)
            except ValueError:
                raise ValueError(f"Invalid mode: {mode}")

        if self._mode != mode:
            self._mode = mode
            self._notify_mode_changed()

    def toggleMode(self) -> None:
        """Toggles between Live and Historical mode."""
        new_mode = (
            HistoricalMode.HISTORICAL
            if self._mode == HistoricalMode.LIVE
            else HistoricalMode.LIVE
        )
        self.setMode(new_mode)

    def loadEvents(self) -> None:
        """Fetches events from the repository and notifies observers.

        Sets loading state before/after the fetch.  On success
        the events list is replaced and any selection is cleared.
        """
        self._setLoading(True)
        try:
            self._events = self._repository.fetch_events()
            self._selectedIndex = 0 if self._events else -1
        finally:
            self._setLoading(False)
        self._notify_events_changed()
        self._notify_selected_event_changed()

    def selectEvent(self, index: int) -> None:
        """Selects an event by index.

        Args:
            index: Zero-based index into ``events``, or -1 to
                clear the selection.
        """
        if index < -1 or index >= len(self._events):
            index = -1
        if self._selectedIndex != index:
            self._selectedIndex = index
            self._notify_selected_event_changed()

    # --- Observer Pattern ---

    def add_mode_changed_callback(
        self, callback: Callable[[HistoricalMode], None]
    ) -> None:
        """Registers a callback for mode changes."""
        self._on_mode_changed_callbacks.append(callback)

    def add_events_changed_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Registers a callback for when the event list changes."""
        self._on_events_changed_callbacks.append(callback)

    def add_selected_event_changed_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Registers a callback for selection changes."""
        self._on_selected_event_changed_callbacks.append(callback)

    def add_loading_changed_callback(
        self, callback: Callable[[bool], None]
    ) -> None:
        """Registers a callback for loading state changes."""
        self._on_loading_changed_callbacks.append(callback)

    # --- Private helpers ---

    def _setLoading(self, loading: bool) -> None:
        if self._loading != loading:
            self._loading = loading
            self._notify_loading_changed()

    def _notify_mode_changed(self) -> None:
        for callback in self._on_mode_changed_callbacks:
            callback(self._mode)

    def _notify_events_changed(self) -> None:
        for callback in self._on_events_changed_callbacks:
            callback()

    def _notify_selected_event_changed(self) -> None:
        for callback in self._on_selected_event_changed_callbacks:
            callback()

    def _notify_loading_changed(self) -> None:
        for callback in self._on_loading_changed_callbacks:
            callback(self._loading)
