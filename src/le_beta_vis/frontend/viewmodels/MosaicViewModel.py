from typing import List, Callable
import numpy as np
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.frontend.fitsconverters import (
    FastPixmapConverter,
    ScalingFunction,
    Colormap,
)


class MosaicViewModel:
    """
    ViewModel for the Mosaic View (HDU Thumbnail Strip).
    Manages generation and selection of thumbnails.
    Pure Python class - No Qt dependencies.
    """

    def __init__(self, configService: ConfigurationService, physics_manager: PhysicsConversionManager):
        self._config = configService
        self._physics_manager = physics_manager
        self._converter = FastPixmapConverter()

        self._captures: List[CCDCaptureModel] = []
        self._thumbnails: List[np.ndarray] = []  # Stores raw uint8 grayscale buffers
        self._selectedIndex: int = -1

        # Callbacks
        self._on_thumbnails_changed_callbacks: List[Callable] = []
        self._on_selection_changed_callbacks: List[Callable[[int], None]] = []

    def setCaptures(self, captures: List[CCDCaptureModel]):
        """
        Sets the list of captures and regenerates thumbnails based on configuration.
        """
        self._captures = captures
        self._thumbnails = []

        # Retrieve Config Constants

        # Use Shared Thresholds from Main View
        vmin = self._config.get("gui:raw_analysis:vis_range_min", 0.0)
        vmax = self._config.get("gui:raw_analysis:vis_range_max", 20.0)

        # Get Scaling Function
        scaling_str = self._config.get(
            "gui:mosaic:scaling_function", ScalingFunction.LOG
        )
        try:
            scaling = ScalingFunction(scaling_str)
        except ValueError:
            scaling = ScalingFunction.LOG

        # Generate Thumbnails
        for capture in self._captures:
            # Convert to keV
            data_kev = self._physics_manager.adu_to_kev(capture.rawData())

            # Generate Thumbnail Buffer
            buffer = self._converter.convert(
                data_kev, Colormap.VIRIDIS, (vmin, vmax), scaling=scaling
            )

            self._thumbnails.append(buffer)

        # Reset selection
        self._selectedIndex = 0 if self._thumbnails else -1

        self._notify_thumbnails_changed()
        self._notify_selection_changed()

    def selectIndex(self, index: int):
        if 0 <= index < len(self._captures):
            if self._selectedIndex == index:
                return  # Break loop if already selected
            self._selectedIndex = index
            self._notify_selection_changed()

    @property
    def thumbnails(self) -> List[np.ndarray]:
        return self._thumbnails

    @property
    def selectedIndex(self) -> int:
        return self._selectedIndex

    # --- Config Accessors for View ---

    @property
    def containerHeight(self) -> int:
        return self._config.get("gui:mosaic:height", 130)

    @property
    def thumbnailHeight(self) -> int:
        return self._config.get("gui:mosaic:thumbnail_height", 100)

    # --- Callbacks ---
    def add_thumbnails_changed_callback(self, callback: Callable):
        self._on_thumbnails_changed_callbacks.append(callback)

    def add_selection_changed_callback(self, callback: Callable[[int], None]):
        self._on_selection_changed_callbacks.append(callback)

    def _notify_thumbnails_changed(self):
        for cb in self._on_thumbnails_changed_callbacks:
            cb()

    def _notify_selection_changed(self):
        for cb in self._on_selection_changed_callbacks:
            cb(self._selectedIndex)
