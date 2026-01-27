from typing import List, Optional, Callable
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.frontend.fitsconverters import (
    OpenCVBasedConverter,
)
from .MosaicViewModel import MosaicViewModel
from PySide6.QtGui import QPixmap
from pathlib import Path


class RawDataViewModel:
    """
    ViewModel for the Interactive Raw Data Analysis mode.
    Manages loading FITS files, HDU selection, and visualization state.
    Pure Python class - No Qt Signals/Slots to ensure easy testing.
    """

    def __init__(self, configService: ConfigurationService):
        self._config = configService
        self._converter = OpenCVBasedConverter()

        self._captures: List[CCDCaptureModel] = []
        self._activeIndex: int = -1

        # Sub-ViewModels
        self.mosaicViewModel = MosaicViewModel(configService)
        # Bidirectional sync: When mosaic selection changes, update this VM
        self.mosaicViewModel.add_selection_changed_callback(self.setActiveHDU)

        # Viz Parameters - Loaded from Config
        self._colormap = self._config.get(
            "gui:raw_analysis:default_colormap", "viridis"
        )
        self._vrange = (
            self._config.get("gui:raw_analysis:vis_range_min", 0.0),
            self._config.get("gui:raw_analysis:vis_range_max", 20.0),
        )
        self._pixmap: Optional[QPixmap] = None

        # Simple Observer pattern for View updates (optional, or View can just poll)
        self._on_image_changed_callbacks: List[Callable] = []
        self._on_file_loaded_callbacks: List[Callable] = []

    def loadFile(self, filePath: str):
        """Loads a FITS file and populates the HDU list."""
        path = Path(filePath)
        if not path.exists():
            return

        # Load all HDUs from the FITS file
        self._captures = CCDCaptureModel.load(path)

        # Reset active index so the MosaicVM sync triggers an update.
        self._activeIndex = -1

        # Pass data to Mosaic VM
        self.mosaicViewModel.setCaptures(self._captures)

        if self._captures:
            self._notify_file_loaded()

    def setActiveHDU(self, index: int):
        """Changes the active HDU and updates the visualization."""
        if 0 <= index < len(self._captures):
            if self._activeIndex == index:
                return  # Avoid infinite recursion

            self._activeIndex = index
            self._updatePixmap()

            # Sync Mosaic Selection
            self.mosaicViewModel.selectIndex(index)

            self._notify_image_changed()

    def setColormap(self, colormap: str):
        """Updates the colormap and refreshes the image."""
        self._colormap = colormap
        self._updatePixmap()
        self._notify_image_changed()

    def setVisualizationRange(self, vmin: float, vmax: float):
        """Updates the intensity range and refreshes the image."""
        self._vrange = (vmin, vmax)
        self._updatePixmap()
        self._notify_image_changed()

    def _updatePixmap(self):
        """Internal helper to regenerate the QPixmap using the current state."""
        if self._activeIndex == -1 or not self._captures:
            self._pixmap = None
            return

        current_capture = self._captures[self._activeIndex]
        raw_data = current_capture.rawData()

        # Apply keV conversion if needed
        kev_factor = self._config.get("global:physics:kev_conversion", 1.0)
        viz_data = raw_data * kev_factor

        self._pixmap = self._converter.convert(viz_data, self._colormap, self._vrange)

    # --- Data Accessors ---

    @property
    def currentPixmap(self) -> QPixmap:
        return self._pixmap

    @property
    def hduSummaries(self) -> List[str]:
        """Returns a list of strings describing the available HDUs."""
        return [
            f"HDU {i}: {c.info().rows}x{c.info().cols}"
            for i, c in enumerate(self._captures)
        ]

    @property
    def activeIndex(self) -> int:
        return self._activeIndex

    # --- Observer Pattern Helpers ---

    def add_image_changed_callback(self, callback: Callable):
        self._on_image_changed_callbacks.append(callback)

    def add_file_loaded_callback(self, callback: Callable):
        self._on_file_loaded_callbacks.append(callback)

    def _notify_image_changed(self):
        for callback in self._on_image_changed_callbacks:
            callback()

    def _notify_file_loaded(self):
        for callback in self._on_file_loaded_callbacks:
            callback()
