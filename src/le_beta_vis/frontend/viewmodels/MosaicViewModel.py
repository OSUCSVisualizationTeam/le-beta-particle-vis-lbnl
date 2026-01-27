from typing import List, Callable
from PySide6.QtGui import QPixmap
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.frontend.fitsconverters import FastPixmapConverter, ScalingFunction

class MosaicViewModel:
    """
    ViewModel for the Mosaic View (HDU Thumbnail Strip).
    Manages generation and selection of thumbnails.
    Pure Python class - No Qt Signals.
    """

    def __init__(self, configService: ConfigurationService):
        self._config = configService
        self._converter = FastPixmapConverter()

        self._captures: List[CCDCaptureModel] = []
        self._thumbnails: List[QPixmap] = []
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
        kev_factor = self._config.get("global:physics:kev_conversion", 1.02857e-5)

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
            data_kev = capture.rawData() * kev_factor

            # Generate Thumbnail
            pixmap = self._converter.convert(
                data_kev, "grayscale", (vmin, vmax), scaling=scaling
            )

            self._thumbnails.append(pixmap)

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
    def thumbnails(self) -> List[QPixmap]:
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
