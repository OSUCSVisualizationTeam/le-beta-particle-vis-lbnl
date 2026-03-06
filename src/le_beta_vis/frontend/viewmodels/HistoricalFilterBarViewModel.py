"""ViewModel for the Historical Filter Bar.

Pure Python — no Qt imports — so it runs in headless CI.
Manages filter field state and builds ``ClusterQueryFilter``
instances for the ``HistoricalViewModel`` to execute.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Tuple

from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)

logger = logging.getLogger(__name__)

# Maps config default_query_hours to a preset key
_HOURS_TO_PRESET = {24: "24h", 72: "3d", 168: "7d", 720: "30d"}

# Maps preset key to number of hours for date computation
_PRESET_TO_HOURS = {"24h": 24, "3d": 72, "7d": 168, "30d": 720}


class HistoricalFilterBarViewModel:
    """Pure Python ViewModel for the filter toolbar.

    Manages filter-field state, converts display units to storage
    units (keV -> ADU), and notifies observers when a filter is
    applied or reset.
    """

    def __init__(
        self,
        configService: ConfigurationService,
        physicsManager: PhysicsConversionManager,
    ):
        self._config = configService
        self._physics = physicsManager

        # Resolve default time preset from config
        default_hours = int(self._config.get(
            "gui:historical:default_query_hours", 24
        ))
        self._default_time_preset = _HOURS_TO_PRESET.get(
            default_hours, "24h"
        )

        # Filter fields (all default to "no filter")
        self._time_preset: str = self._default_time_preset
        self._cluster_id: Optional[int] = None
        self._fits_id: Optional[int] = None
        self._hdu_id: Optional[int] = None
        self._min_sigma_x: Optional[float] = None
        self._min_sigma_y: Optional[float] = None
        self._min_total_energy: Optional[float] = None
        self._min_total_pixels: Optional[int] = None
        self._classification: Optional[str] = None
        self._start_datetime: Optional[datetime] = None
        self._end_datetime: Optional[datetime] = None

        # Callbacks
        self._on_filter_applied: List[
            Callable[[ClusterQueryFilter], None]
        ] = []
        self._on_filter_reset: List[Callable[[], None]] = []

    # --- Properties ---

    @property
    def time_preset(self) -> str:
        """Current time-range preset key."""
        return self._time_preset

    @time_preset.setter
    def time_preset(self, value: str) -> None:
        self._time_preset = value

    @property
    def cluster_id(self) -> Optional[int]:
        """Cluster ID filter, or ``None`` for any."""
        return self._cluster_id

    @cluster_id.setter
    def cluster_id(self, value: Optional[int]) -> None:
        self._cluster_id = value

    @property
    def fits_id(self) -> Optional[int]:
        """FITS ID filter, or ``None`` for any."""
        return self._fits_id

    @fits_id.setter
    def fits_id(self, value: Optional[int]) -> None:
        self._fits_id = value

    @property
    def hdu_id(self) -> Optional[int]:
        """HDU ID filter, or ``None`` for any."""
        return self._hdu_id

    @hdu_id.setter
    def hdu_id(self, value: Optional[int]) -> None:
        self._hdu_id = value

    @property
    def min_sigma_x(self) -> Optional[float]:
        """Minimum sigma-X filter, or ``None`` for any."""
        return self._min_sigma_x

    @min_sigma_x.setter
    def min_sigma_x(self, value: Optional[float]) -> None:
        self._min_sigma_x = value

    @property
    def min_sigma_y(self) -> Optional[float]:
        """Minimum sigma-Y filter, or ``None`` for any."""
        return self._min_sigma_y

    @min_sigma_y.setter
    def min_sigma_y(self, value: Optional[float]) -> None:
        self._min_sigma_y = value

    @property
    def min_total_energy(self) -> Optional[float]:
        """Minimum energy in display units (keV or ADU), or ``None``."""
        return self._min_total_energy

    @min_total_energy.setter
    def min_total_energy(self, value: Optional[float]) -> None:
        self._min_total_energy = value

    @property
    def min_total_pixels(self) -> Optional[int]:
        """Minimum pixel count filter, or ``None`` for any."""
        return self._min_total_pixels

    @min_total_pixels.setter
    def min_total_pixels(self, value: Optional[int]) -> None:
        self._min_total_pixels = value

    @property
    def classification(self) -> Optional[str]:
        """Classification string filter, or ``None`` for all."""
        return self._classification

    @classification.setter
    def classification(self, value: Optional[str]) -> None:
        self._classification = value

    @property
    def start_datetime(self) -> Optional[datetime]:
        """Start of the date range filter, or ``None``."""
        return self._start_datetime

    @start_datetime.setter
    def start_datetime(self, value: Optional[datetime]) -> None:
        self._start_datetime = value

    @property
    def end_datetime(self) -> Optional[datetime]:
        """End of the date range filter, or ``None``."""
        return self._end_datetime

    @end_datetime.setter
    def end_datetime(self, value: Optional[datetime]) -> None:
        self._end_datetime = value

    @property
    def display_energy_in_kev(self) -> bool:
        """Whether the UI should show energy values in keV."""
        return bool(self._config.get(
            "gui:raw_analysis:display_energy_in_kev", True
        ))

    @property
    def energy_unit_label(self) -> str:
        """Display label for the energy unit ('keV' or 'ADU')."""
        return "keV" if self.display_energy_in_kev else "ADU"

    @property
    def classification_options(
        self,
    ) -> List[Tuple[str, Optional[str]]]:
        """Available classification choices for the combo box.

        Returns a list of ``(display_text, filter_value)`` tuples.
        The first entry is always ``("All", None)`` (no filter).
        """
        options: List[Tuple[str, Optional[str]]] = [("All", None)]
        for pt in ParticleType:
            label = (
                f"{pt.display_name} {pt.symbol}"
                if pt != ParticleType.UNCLASSIFIED
                else pt.display_name
            )
            options.append((label, pt.name.lower()))
        return options

    # --- Commands ---

    @staticmethod
    def compute_dates_for_preset(
        preset: str,
    ) -> Tuple[datetime, datetime]:
        """Returns ``(start, end)`` for the given time-preset key.

        Unknown keys fall back to 24 hours.
        """
        hours = _PRESET_TO_HOURS.get(preset, 24)
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return start, end

    def build_filter(self) -> ClusterQueryFilter:
        """Constructs a ``ClusterQueryFilter`` from current field state.

        Energy values in keV are converted back to ADU for the query.
        Spinbox values of 0 are treated as "no filter" (``None``).
        """
        energy_adu: Optional[float] = None
        if self._min_total_energy is not None:
            if self.display_energy_in_kev:
                factor = self._physics.kev_conversion_factor
                energy_adu = (
                    self._min_total_energy / factor
                    if factor != 0 else None
                )
            else:
                energy_adu = self._min_total_energy

        if self._time_preset != self._default_time_preset:
            logger.info(
                "Time preset '%s' selected but date filtering is "
                "not yet supported by the EPS backend.",
                self._time_preset,
            )

        return ClusterQueryFilter(
            cluster_id=self._cluster_id,
            fits_id=self._fits_id,
            hdu_id=self._hdu_id,
            date_start = self.start_datetime,
            date_end = self.end_datetime,
            min_sigma_x=self._min_sigma_x,
            min_sigma_y=self._min_sigma_y,
            min_total_energy=energy_adu,
            min_total_pixels=self._min_total_pixels,
            classification=self._classification,
        )

    def apply(self) -> None:
        """Builds the current filter and notifies observers."""
        query_filter = self.build_filter()
        for callback in self._on_filter_applied:
            callback(query_filter)

    def reset(self) -> None:
        """Resets all fields to defaults and notifies observers."""
        self._time_preset = self._default_time_preset
        self._cluster_id = None
        self._fits_id = None
        self._hdu_id = None
        self._min_sigma_x = None
        self._min_sigma_y = None
        self._min_total_energy = None
        self._min_total_pixels = None
        self._classification = None
        self._start_datetime = None
        self._end_datetime = None
        for callback in self._on_filter_reset:
            callback()

    # --- Observer pattern ---

    def add_filter_applied_callback(
        self, callback: Callable[[ClusterQueryFilter], None]
    ) -> None:
        """Registers a callback fired when ``apply()`` is called."""
        self._on_filter_applied.append(callback)

    def add_filter_reset_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Registers a callback fired when ``reset()`` is called."""
        self._on_filter_reset.append(callback)
