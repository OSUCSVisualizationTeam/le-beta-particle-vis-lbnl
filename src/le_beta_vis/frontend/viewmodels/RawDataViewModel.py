import queue
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.frontend.fitsconverters import Colormap, OpenCVBasedConverter


class RawDataViewModel:
    """
    ViewModel for the Interactive Raw Data Analysis mode.
    Manages loading FITS files and visualization state.
    Uses background threading for high-performance rendering.
    Pure Python class - No Qt dependencies.
    """

    def __init__(self, configService: ConfigurationService):
        self._config = configService
        self._converter = OpenCVBasedConverter()

        self._captures: List[CCDCaptureModel] = []
        self._activeIndex: int = -1

        # Sub-ViewModels
        from .MosaicViewModel import MosaicViewModel

        self.mosaicViewModel = MosaicViewModel(configService)
        self.mosaicViewModel.add_selection_changed_callback(self.setActiveHDU)

        # Viz Parameters
        colormap_str = self._config.get(
            "gui:raw_analysis:default_colormap", Colormap.VIRIDIS
        )
        self._colormap = Colormap(colormap_str)
        self._vrange = (
            self._config.get("gui:raw_analysis:vis_range_min", 0.0),
            self._config.get("gui:raw_analysis:vis_range_max", 20.0),
        )
        self._scale: float = 1.0

        # Async Rendering State
        self._current_buffer: Optional[np.ndarray] = None
        self._render_queue = queue.Queue(maxsize=1)
        self._render_thread = threading.Thread(target=self._render_worker, daemon=True)
        self._render_thread.start()

        # Callbacks
        self._on_image_changed_callbacks: List[Callable] = []
        self._on_file_loaded_callbacks: List[Callable] = []
        self._on_scale_changed_callbacks: List[Callable] = []

    def loadFile(self, filePath: str):
        path = Path(filePath)
        if not path.exists():
            return

        self._captures = CCDCaptureModel.load(path)
        self._activeIndex = -1
        self.mosaicViewModel.setCaptures(self._captures)

        if self._captures:
            self._notify_file_loaded()

    def setActiveHDU(self, index: int):
        if 0 <= index < len(self._captures):
            if self._activeIndex == index:
                return
            self._activeIndex = index
            self.mosaicViewModel.selectIndex(index)
            self._request_render()

    def setColormap(self, colormap: str):
        try:
            self._colormap = Colormap(colormap)
            self._request_render()
        except ValueError:
            pass

    def setVisualizationRange(self, vmin: float, vmax: float):
        self._vrange = (vmin, vmax)
        self._request_render()

    def zoomIn(self):
        """
        Increases the zoom scale by the configured factor.
        Clamped at a maximum scale of 1000.0 (1000%).
        Notifies scale changed listeners.
        """
        factor = self._config.get("gui:raw_analysis:zoom_step_factor", 1.2)
        new_scale = self._scale * factor
        if new_scale <= 1000.0:
            self._scale = new_scale
            self._notify_scale_changed()

    def zoomOut(self):
        """
        Decreases the zoom scale by the configured factor.
        Clamped at a minimum scale of 0.1 (10%).
        Notifies scale changed listeners.
        """
        factor = self._config.get("gui:raw_analysis:zoom_step_factor", 1.2)
        new_scale = self._scale / factor
        if new_scale >= 0.1:
            self._scale = new_scale
            self._notify_scale_changed()

    def resetZoom(self):
        """
        Resets the zoom scale to 1.0 (100%).
        Notifies scale changed listeners if a change occurred.
        """
        if self._scale != 1.0:
            self._scale = 1.0
            self._notify_scale_changed()

    def _request_render(self):
        """Queues a render request."""
        try:
            self._render_queue.get_nowait()
        except queue.Empty:
            pass
        self._render_queue.put(True)

    def _render_worker(self):
        """Background thread loop."""
        while True:
            self._render_queue.get()
            self._render_worker_logic()

    def _render_worker_logic(self):
        """Core rendering logic, extracted for testability."""
        if self._activeIndex == -1 or not self._captures:
            self._current_buffer = None
        else:
            try:
                current_capture = self._captures[self._activeIndex]
                raw_data = current_capture.rawData()
                kev_factor = self._config.get(
                    "global:physics:kev_conversion", 1.02857e-5
                )
                viz_data = raw_data * kev_factor

                self._current_buffer = self._converter.convert(
                    viz_data, self._colormap, self._vrange
                )
            except Exception:
                self._current_buffer = None

        self._notify_image_changed()

    # --- Data Accessors ---

    @property
    def currentBuffer(self) -> Optional[np.ndarray]:
        return self._current_buffer

    @property
    def dataRange(self) -> Tuple[float, float]:
        if self._activeIndex == -1 or not self._captures:
            return 0.0, 1000.0
        info = self._captures[self._activeIndex].info()
        kev_factor = self._config.get("global:physics:kev_conversion", 1.02857e-5)
        return (float(info.min * kev_factor), float(info.max * kev_factor))

    @property
    def visualizationRange(self) -> Tuple[float, float]:
        return self._vrange

    @property
    def colormap(self) -> str:
        return self._colormap.value

    @property
    def hduSummaries(self) -> List[str]:
        return [
            f"HDU {i}: {c.info().rows}x{c.info().cols}"
            for i, c in enumerate(self._captures)
        ]

    @property
    def activeIndex(self) -> int:
        return self._activeIndex

    @property
    def scale(self) -> float:
        return self._scale

    # --- Observer Pattern Helpers ---

    def add_image_changed_callback(self, callback: Callable):
        self._on_image_changed_callbacks.append(callback)

    def add_file_loaded_callback(self, callback: Callable):
        self._on_file_loaded_callbacks.append(callback)

    def add_scale_changed_callback(self, callback: Callable):
        self._on_scale_changed_callbacks.append(callback)

    def _notify_image_changed(self):
        for callback in self._on_image_changed_callbacks:
            callback()

    def _notify_file_loaded(self):
        for callback in self._on_file_loaded_callbacks:
            callback()

    def _notify_scale_changed(self):
        for callback in self._on_scale_changed_callbacks:
            callback()
