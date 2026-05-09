import logging
import queue
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.frontend.fitsconverters import (
    Colormap,
    OpenCVBasedConverter,
    ScalingFunction,
)
from .ClusterAnalysisViewModel import ClusterAnalysisViewModel
from .MosaicViewModel import MosaicViewModel

logger = logging.getLogger(__name__)


class ActiveTool(str, Enum):
    """Enumeration of interactive tools available in the Raw Data View."""

    MAGNIFIER = "magnifier"
    BOX_SELECT = "box_select"


class RawDataViewModel:
    """
    ViewModel for the Interactive Raw Data Analysis mode.
    Manages loading FITS files and visualization state.
    Uses background threading for high-performance rendering.
    Pure Python class - No Qt dependencies.
    """

    def __init__(
        self,
        configService: ConfigurationService,
        physics_manager: PhysicsConversionManager,
    ):
        self._config = configService
        self._physics_manager = physics_manager
        self._converter = OpenCVBasedConverter()
        self._captures: List[CCDCaptureModel] = []
        self._activeIndex: int = -1
        self._fits_path: Optional[str] = None
        self._init_callbacks()
        self._init_sub_viewmodels()
        self._init_visualization_state()
        self._init_render_pipeline()

    def _init_sub_viewmodels(self) -> None:
        """Constructs sub-ViewModels and wires cross-VM notifications."""
        self.mosaicViewModel = MosaicViewModel(
            self._config, self._physics_manager
        )
        self.mosaicViewModel.add_selection_changed_callback(self.setActiveHDU)

        self.clusterAnalysisViewModel = ClusterAnalysisViewModel(
            self._config,
            self._physics_manager,
            lambda: self.activeRawData,
            lambda: self._colormap,
        )
        self.add_active_tool_changed_callback(
            self.clusterAnalysisViewModel._notify_active_tool_changed
        )

    def _init_visualization_state(self) -> None:
        """Initializes colormap, value range, scaling, zoom, tool,
        magnifier, image bounds, and pointer hover state."""
        colormap_str = self._config.get(
            "gui:raw_analysis:default_colormap", Colormap.VIRIDIS
        )
        self._colormap = Colormap(colormap_str)
        self._vrange = (
            self._config.get("gui:raw_analysis:vis_range_min", 0.0),
            self._config.get("gui:raw_analysis:vis_range_max", 20.0),
        )
        scaling_str = self._config.get(
            "gui:raw_analysis:default_scaling_function", ScalingFunction.LINEAR
        )
        try:
            self._scalingFunction = ScalingFunction(scaling_str)
        except ValueError:
            self._scalingFunction = ScalingFunction.LINEAR
        self._scale: float = 1.0
        self._activeTool: ActiveTool = ActiveTool.BOX_SELECT
        self._magnificationFactor: float = self._config.get(
            "gui:raw_analysis:magnifier_default_factor", 3.0
        )
        self._magnifier_pos: Tuple[int, int] = (0, 0)
        self._image_bounds: Tuple[int, int] = (0, 0)
        self._pointer_hover_pos: Optional[Tuple[int, int]] = None

    def _init_render_pipeline(self) -> None:
        """Creates the render queue and buffer lock, then starts the
        background render worker daemon thread."""
        self._buffer_lock = threading.Lock()
        self._current_buffer: Optional[np.ndarray] = None
        self._render_queue: queue.Queue = queue.Queue(maxsize=1)
        self._render_thread = threading.Thread(
            target=self._render_worker, daemon=True
        )
        self._render_thread.start()

    def _init_callbacks(self) -> None:
        """Initializes all observer callback registries to empty lists."""
        self._on_image_changed_callbacks: List[Callable] = []
        self._on_file_loaded_callbacks: List[Callable] = []
        self._on_scale_changed_callbacks: List[Callable] = []
        self._on_active_tool_changed_callbacks: List[Callable] = []
        self._on_magnifier_state_changed_callbacks: List[Callable] = []
        self._on_magnifier_position_changed_callbacks: List[Callable] = []
        self._on_pointer_hover_changed_callbacks: List[Callable] = []
        self._on_active_hdu_changed_callbacks: List[Callable] = []

    def loadFile(self, filePath: str):
        path = Path(filePath)
        if not path.exists():
            return

        self._captures = CCDCaptureModel.load(path)
        self._activeIndex = -1
        self._fits_path = filePath
        self.mosaicViewModel.setCaptures(self._captures)

        if self._captures:
            self._notify_file_loaded()

    def setActiveHDU(self, index: int):
        if 0 <= index < len(self._captures):
            if self._activeIndex == index:
                return
            self._activeIndex = index
            self._notify_active_hdu_changed()
            self.mosaicViewModel.selectIndex(index)
            self._request_render()

    def setColormap(self, colormap: str):
        try:
            self._colormap = Colormap(colormap)
            self._request_render()
        except ValueError:
            pass

    def setScalingFunction(self, scaling: str) -> None:
        """Sets the scaling transfer function and re-queues a render."""
        try:
            self._scalingFunction = ScalingFunction(scaling)
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

    # --- Magnifier Tool ---

    def setActiveTool(self, tool: ActiveTool) -> None:
        """
        Sets the currently active interactive tool.
        Notifies listeners only if the tool actually changed.
        """
        if self._activeTool == tool:
            return
        self._activeTool = tool
        self._notify_active_tool_changed()

    def toggleMagnifier(self) -> None:
        """
        Toggles between the Magnifier tool and the ROI (Box Select) tool.
        If the magnifier is active, switches to Box Select; otherwise
        switches to Magnifier.
        """
        if self._activeTool == ActiveTool.MAGNIFIER:
            self.setActiveTool(ActiveTool.BOX_SELECT)
        else:
            self.setActiveTool(ActiveTool.MAGNIFIER)

    def adjustMagnification(self, delta: int) -> None:
        """
        Adjusts the magnification factor by delta * step.
        The result is clamped between the configured minimum and maximum.
        Notifies magnifier state listeners on change.
        """
        step = self._config.get("gui:raw_analysis:magnifier_factor_step", 0.5)
        min_factor = self._config.get(
            "gui:raw_analysis:magnifier_min_factor", 1.0
        )
        max_factor = self._config.get(
            "gui:raw_analysis:magnifier_max_factor", 100.0
        )
        new_factor = self._magnificationFactor + delta * step
        new_factor = max(min_factor, min(new_factor, max_factor))
        if new_factor != self._magnificationFactor:
            self._magnificationFactor = new_factor
            self._notify_magnifier_state_changed()

    def setMagnifierPosition(self, row: int, col: int) -> None:
        """
        Sets the magnifier's pixel position, clamped to image bounds.
        Notifies position listeners if the position changed.
        """
        rows, cols = self._image_bounds
        if rows > 0 and cols > 0:
            row = max(0, min(row, rows - 1))
            col = max(0, min(col, cols - 1))
        new_pos = (row, col)
        if new_pos != self._magnifier_pos:
            self._magnifier_pos = new_pos
            self._notify_magnifier_position_changed()

    def moveMagnifier(self, drow: int, dcol: int) -> None:
        """
        Moves the magnifier by delta * configured step size.
        Delegates to setMagnifierPosition for clamping.
        """
        step = self._config.get("gui:raw_analysis:magnifier_move_step", 1)
        row, col = self._magnifier_pos
        self.setMagnifierPosition(row + drow * step, col + dcol * step)

    # --- Pointer Tool ---

    def setPointerHoverPosition(self, row: int, col: int) -> None:
        """
        Sets the pointer hover pixel position, clamped to image bounds.
        Notifies listeners if the position changed.
        """
        rows, cols = self._image_bounds
        if rows > 0 and cols > 0:
            row = max(0, min(row, rows - 1))
            col = max(0, min(col, cols - 1))
        new_pos = (row, col)
        if new_pos != self._pointer_hover_pos:
            self._pointer_hover_pos = new_pos
            self._notify_pointer_hover_changed()

    def clearPointerHover(self) -> None:
        """
        Clears the pointer hover position.
        Notifies listeners if it was previously set.
        """
        if self._pointer_hover_pos is not None:
            self._pointer_hover_pos = None
            self._notify_pointer_hover_changed()

    # --- Box Selection active-state ---

    @property
    def isBoxSelectActive(self) -> bool:
        """Returns True if the box selection tool is active."""
        return self._activeTool == ActiveTool.BOX_SELECT

    def _request_render(self):
        """Queues a render request, coalescing rapid calls into one."""
        try:
            self._render_queue.put_nowait(True)
        except queue.Full:
            pass

    def _render_worker(self):
        """Background thread loop."""
        while True:
            self._render_queue.get()
            self._render_worker_logic()

    def _render_worker_logic(self):
        """Core rendering logic, extracted for testability."""
        if self._activeIndex == -1 or not self._captures:
            with self._buffer_lock:
                self._current_buffer = None
        else:
            try:
                current_capture = self._captures[self._activeIndex]
                raw_data = current_capture.rawData()
                self._image_bounds = raw_data.shape[:2]
                viz_data = self._physics_manager.adu_to_kev(raw_data)

                buffer = self._converter.convert(
                    viz_data,
                    self._colormap,
                    self._vrange,
                    scaling=self._scalingFunction,
                )
                with self._buffer_lock:
                    self._current_buffer = buffer
            except Exception:
                logger.exception("Render failed")
                with self._buffer_lock:
                    self._current_buffer = None

        self._notify_image_changed()

    # --- Data Accessors ---

    @property
    def currentBuffer(self) -> Optional[np.ndarray]:
        with self._buffer_lock:
            return self._current_buffer

    @property
    def dataRange(self) -> Tuple[float, float]:
        if self._activeIndex == -1 or not self._captures:
            return 0.0, 1000.0
        info = self._captures[self._activeIndex].info()
        return (
            float(self._physics_manager.adu_to_kev(info.min)),
            float(self._physics_manager.adu_to_kev(info.max)),
        )

    @property
    def visualizationRange(self) -> Tuple[float, float]:
        return self._vrange

    @property
    def colormap(self) -> str:
        return self._colormap.value

    @property
    def scalingFunction(self) -> str:
        """Returns the current scaling function as a string."""
        return self._scalingFunction.value

    @property
    def activeIndex(self) -> int:
        return self._activeIndex

    @property
    def fits_path(self) -> Optional[str]:
        """Path of the currently loaded FITS file; None if no file is loaded."""
        return self._fits_path

    def active_capture_info(self) -> Optional[CCDCaptureModel.Info]:
        """Metadata for the currently active HDU; None if nothing is loaded."""
        if self._activeIndex == -1 or not self._captures:
            return None
        return self._captures[self._activeIndex].info()

    @property
    def activeHDULabel(self) -> Optional[str]:
        """Returns 'HDU <N>' when active, None when no file is loaded."""
        if self._activeIndex == -1 or not self._captures:
            return None
        return f"HDU {self._activeIndex}"

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def activeTool(self) -> ActiveTool:
        return self._activeTool

    @property
    def isMagnifierActive(self) -> bool:
        return self._activeTool == ActiveTool.MAGNIFIER

    @property
    def magnificationFactor(self) -> float:
        return self._magnificationFactor

    @property
    def physics_manager(self) -> PhysicsConversionManager:
        """Returns the physics conversion manager instance."""
        return self._physics_manager

    @property
    def kevConversionFactor(self) -> float:
        return self._physics_manager.kev_conversion_factor

    @property
    def activeRawData(self) -> Optional[np.ndarray]:
        if self._activeIndex == -1 or not self._captures:
            return None
        return self._captures[self._activeIndex].rawData()

    @property
    def pointerHoverInfo(
        self,
    ) -> Optional[Tuple[int, int, float]]:
        """Returns (row, col, keV_value) or None if not hovering."""
        if self._pointer_hover_pos is None:
            return None
        row, col = self._pointer_hover_pos
        raw = self.activeRawData
        if raw is None:
            return None
        value = self._physics_manager.adu_to_kev(float(raw[row, col]))
        return (row, col, value)

    @property
    def magnifierPosition(self) -> Tuple[int, int]:
        return self._magnifier_pos

    @property
    def magnifierMoveStep(self) -> int:
        return self._config.get("gui:raw_analysis:magnifier_move_step", 1)

    @property
    def showToolHints(self) -> bool:
        return self._config.get("gui:raw_analysis:show_tool_hints", True)

    @property
    def autoRangeOnLoad(self) -> bool:
        """Whether to auto-set the visualization range on load."""
        return self._config.get("gui:raw_analysis:auto_range_on_load", False)

    # --- Observer Pattern Helpers ---

    def add_image_changed_callback(self, callback: Callable):
        self._on_image_changed_callbacks.append(callback)

    def add_file_loaded_callback(self, callback: Callable):
        self._on_file_loaded_callbacks.append(callback)

    def add_active_hdu_changed_callback(self, callback: Callable) -> None:
        """Register a callback fired whenever the active HDU index changes."""
        self._on_active_hdu_changed_callbacks.append(callback)

    def _notify_active_hdu_changed(self) -> None:
        for callback in self._on_active_hdu_changed_callbacks:
            callback()

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

    def add_active_tool_changed_callback(self, callback: Callable):
        self._on_active_tool_changed_callbacks.append(callback)

    def add_magnifier_state_changed_callback(self, callback: Callable):
        self._on_magnifier_state_changed_callbacks.append(callback)

    def _notify_active_tool_changed(self):
        for callback in self._on_active_tool_changed_callbacks:
            callback()

    def _notify_magnifier_state_changed(self):
        for callback in self._on_magnifier_state_changed_callbacks:
            callback()

    def add_magnifier_position_changed_callback(self, callback: Callable):
        self._on_magnifier_position_changed_callbacks.append(callback)

    def _notify_magnifier_position_changed(self):
        for callback in self._on_magnifier_position_changed_callbacks:
            callback()

    def add_pointer_hover_changed_callback(self, callback: Callable):
        self._on_pointer_hover_changed_callbacks.append(callback)

    def _notify_pointer_hover_changed(self):
        for callback in self._on_pointer_hover_changed_callbacks:
            callback()
