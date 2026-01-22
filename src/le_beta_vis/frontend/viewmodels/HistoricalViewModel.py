from typing import List, Callable
from enum import Enum
from le_beta_vis.common.ConfigurationService import ConfigurationService


class HistoricalMode(str, Enum):
    LIVE = "live"
    HISTORICAL = "historical"


class HistoricalViewModel:
    """
    ViewModel for the Historical Event Analysis mode.
    Manages mode state (Live vs Historical) and query parameters.
    Pure Python class - No Qt Signals/Slots.
    """

    def __init__(self, configService: ConfigurationService):
        self._config = configService

        # Load initial mode from config (stored as string)
        mode_str = self._config.get("gui:historical:mode", HistoricalMode.HISTORICAL)
        self._mode = HistoricalMode(mode_str)

        self._on_mode_changed_callbacks: List[Callable[[HistoricalMode], None]] = []

    @property
    def mode(self) -> HistoricalMode:
        return self._mode

    def setMode(self, mode: HistoricalMode):
        if not isinstance(mode, HistoricalMode):
            # Try to cast from string if needed
            try:
                mode = HistoricalMode(mode)
            except ValueError:
                raise ValueError(f"Invalid mode: {mode}")

        if self._mode != mode:
            self._mode = mode
            self._notify_mode_changed()

    def toggleMode(self):
        """Toggles between Live and Historical mode."""
        new_mode = (
            HistoricalMode.HISTORICAL
            if self._mode == HistoricalMode.LIVE
            else HistoricalMode.LIVE
        )
        self.setMode(new_mode)

    # --- Observer Pattern ---

    def add_mode_changed_callback(self, callback: Callable[[HistoricalMode], None]):
        self._on_mode_changed_callbacks.append(callback)

    def _notify_mode_changed(self):
        for callback in self._on_mode_changed_callbacks:
            callback(self._mode)
