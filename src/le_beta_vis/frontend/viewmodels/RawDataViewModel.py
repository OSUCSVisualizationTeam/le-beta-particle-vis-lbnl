import logging
import queue
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ClusterExtractor import (
    ClusteredEventInfo,
    ClusterExtractor,
)
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.RoiRect import RoiRect
from le_beta_vis.frontend.fitsconverters import Colormap, OpenCVBasedConverter

logger = logging.getLogger(__name__)


class ActiveTool(str, Enum):
    """Enumeration of interactive tools available in the Raw Data View."""

    POINTER = "pointer"
    MAGNIFIER = "magnifier"
    BOX_SELECT = "box_select"


class ClusteringState(str, Enum):
    """State of the cluster extraction lifecycle."""

    IDLE = "idle"
    RUNNING = "running"


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

        # Tool State
        self._activeTool: ActiveTool = ActiveTool.POINTER
        self._magnificationFactor: float = self._config.get(
            "gui:raw_analysis:magnifier_default_factor", 3.0
        )
        self._magnifier_pos: Tuple[int, int] = (0, 0)
        self._image_bounds: Tuple[int, int] = (0, 0)

        # Pointer Hover State
        self._pointer_hover_pos: Optional[Tuple[int, int]] = None

        # ROI State
        self._rois: List[RoiRect] = []

        # Clustering State
        self._clusterExtractor: Optional[ClusterExtractor] = None
        self._clusteringState: ClusteringState = ClusteringState.IDLE
        self._clusteringResults: List[ClusteredEventInfo] = []
        self._clusteringError: Optional[str] = None
        self._clusteringProgress: float = 0.0
        self._clustering_timeout_timer: Optional[threading.Timer] = None

        # Async Rendering State
        self._current_buffer: Optional[np.ndarray] = None
        self._render_queue = queue.Queue(maxsize=1)
        self._render_thread = threading.Thread(
            target=self._render_worker, daemon=True
        )
        self._render_thread.start()

        # Callbacks
        self._on_image_changed_callbacks: List[Callable] = []
        self._on_file_loaded_callbacks: List[Callable] = []
        self._on_scale_changed_callbacks: List[Callable] = []
        self._on_active_tool_changed_callbacks: List[Callable] = []
        self._on_magnifier_state_changed_callbacks: List[Callable] = []
        self._on_magnifier_position_changed_callbacks: List[Callable] = []
        self._on_pointer_hover_changed_callbacks: List[Callable] = []
        self._on_roi_changed_callbacks: List[Callable] = []
        self._on_box_selection_completed_callbacks: List[Callable] = []
        self._on_clustering_state_changed_callbacks: List[Callable] = []
        self._on_clustering_completed_callbacks: List[Callable] = []
        self._on_clustering_error_callbacks: List[Callable] = []
        self._on_clustering_progress_callbacks: List[Callable] = []

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
        Toggles between the Magnifier tool and the Pointer tool.
        If the magnifier is active, switches to Pointer; otherwise
        switches to Magnifier.
        """
        if self._activeTool == ActiveTool.MAGNIFIER:
            self.setActiveTool(ActiveTool.POINTER)
        else:
            self.setActiveTool(ActiveTool.MAGNIFIER)

    def adjustMagnification(self, delta: int) -> None:
        """
        Adjusts the magnification factor by delta * step.
        The result is clamped between the configured minimum and maximum.
        Notifies magnifier state listeners on change.
        """
        step = self._config.get(
            "gui:raw_analysis:magnifier_factor_step", 0.5
        )
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
        step = self._config.get(
            "gui:raw_analysis:magnifier_move_step", 1
        )
        row, col = self._magnifier_pos
        self.setMagnifierPosition(
            row + drow * step, col + dcol * step
        )

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

    # --- Box Selection / ROI ---

    @property
    def isBoxSelectActive(self) -> bool:
        """Returns True if the box selection tool is active."""
        return self._activeTool == ActiveTool.BOX_SELECT

    @property
    def rois(self) -> List[RoiRect]:
        """Returns a shallow copy of the ROI list."""
        return list(self._rois)

    @property
    def boxSelectColor(self) -> str:
        """Returns the configured box selection color."""
        return self._config.get(
            "gui:raw_analysis:box_select_color", "#00BFFF"
        )

    @property
    def boxSelectBorderWidth(self) -> int:
        """Returns the configured box selection border width."""
        return self._config.get(
            "gui:raw_analysis:box_select_border_width", 2
        )

    @property
    def clusteringThreshold(self) -> float:
        """Returns the configured sigma threshold for clustering."""
        return self._config.get(
            "gui:raw_analysis:clustering_threshold", 4.0
        )

    def addRoi(
        self, top: int, left: int, bottom: int, right: int
    ) -> RoiRect:
        """
        Creates and appends a new rectangular ROI.
        Coordinates are normalized so top <= bottom and left <= right.
        Notifies both roi_changed and box_selection_completed callbacks.
        """
        norm_top = min(top, bottom)
        norm_left = min(left, right)
        norm_bottom = max(top, bottom)
        norm_right = max(left, right)
        roi = RoiRect(norm_top, norm_left, norm_bottom, norm_right)
        self._rois.append(roi)
        self._notify_roi_changed()
        self._notify_box_selection_completed()
        return roi

    def clearRois(self) -> None:
        """Clears all ROIs. Notifies listeners if the list was non-empty."""
        if self._rois:
            self._rois.clear()
            self._notify_roi_changed()

    def removeRoi(self, index: int) -> None:
        """Removes an ROI by index. Notifies listeners on success."""
        if 0 <= index < len(self._rois):
            self._rois.pop(index)
            self._notify_roi_changed()

    # --- Cluster Extraction ---

    def setClusterExtractor(
        self, extractor: ClusterExtractor
    ) -> None:
        """Sets the cluster extractor implementation to use."""
        self._clusterExtractor = extractor

    @property
    def isClusteringAvailable(self) -> bool:
        """Returns True when extraction can be triggered.

        Requires: extractor set, BOX_SELECT tool active, at least
        one ROI, state IDLE, and raw data loaded.
        """
        return (
            self._clusterExtractor is not None
            and self._activeTool == ActiveTool.BOX_SELECT
            and len(self._rois) > 0
            and self._clusteringState == ClusteringState.IDLE
            and self.activeRawData is not None
        )

    @property
    def clusteringState(self) -> ClusteringState:
        """Returns the current clustering lifecycle state."""
        return self._clusteringState

    @property
    def clusteringResults(self) -> List[ClusteredEventInfo]:
        """Returns the most recent extraction results."""
        return list(self._clusteringResults)

    @property
    def clusteringTimeoutSeconds(self) -> int:
        """Returns the configured clustering timeout in seconds."""
        return self._config.get(
            "gui:raw_analysis:clustering_timeout_seconds", 300
        )

    @property
    def clusteringError(self) -> Optional[str]:
        """Returns the most recent clustering error message, if any."""
        return self._clusteringError

    @property
    def clusteringProgress(self) -> float:
        """Returns the current extraction progress in [0.0, 1.0]."""
        return self._clusteringProgress

    def triggerClustering(self) -> None:
        """Starts cluster extraction on the current ROI.

        No-op when isClusteringAvailable is False.
        Starts a timeout watchdog that aborts the extraction
        if it does not complete within the configured limit.
        """
        if not self.isClusteringAvailable:
            return

        roi = self._rois[-1]
        raw = self.activeRawData
        data = roi.extract_raw_data(raw)
        if data is None:
            return

        self._clusteringError = None
        self._clusteringProgress = 0.0
        self._clusteringState = ClusteringState.RUNNING
        self._notify_clustering_state_changed()

        timeout = self.clusteringTimeoutSeconds
        self._clustering_timeout_timer = threading.Timer(
            timeout, self._on_clustering_timeout
        )
        self._clustering_timeout_timer.daemon = True
        self._clustering_timeout_timer.start()

        bbox = roi.geometry()
        self._clusterExtractor.extract(
            data, bbox, self._on_clustering_success,
            progress_callback=self._on_clustering_progress,
        )

    def cancelClustering(self) -> None:
        """Cancels any in-progress cluster extraction."""
        self._cancel_timeout_timer()
        if self._clusterExtractor is not None:
            self._clusterExtractor.cancel()
        self._clusteringState = ClusteringState.IDLE
        self._notify_clustering_state_changed()

    def _on_clustering_success(
        self, results: List[ClusteredEventInfo]
    ) -> None:
        """Callback from extractor thread on completion."""
        self._cancel_timeout_timer()
        if self._clusteringState != ClusteringState.RUNNING:
            return
        self._clusteringResults = results
        self._clusteringState = ClusteringState.IDLE
        self._notify_clustering_state_changed()
        self._notify_clustering_completed()

    def _on_clustering_timeout(self) -> None:
        """Called by the watchdog timer when extraction takes too long."""
        if self._clusteringState != ClusteringState.RUNNING:
            return
        logger.warning("Cluster extraction timed out")
        if self._clusterExtractor is not None:
            self._clusterExtractor.cancel()
        self._clusteringError = (
            "Cluster extraction timed out after "
            f"{self.clusteringTimeoutSeconds} seconds."
        )
        self._clusteringState = ClusteringState.IDLE
        self._notify_clustering_state_changed()
        self._notify_clustering_error()

    def _on_clustering_progress(self, value: float) -> None:
        """Called from the extractor thread with progress updates."""
        self._clusteringProgress = value
        self._notify_clustering_progress()

    def _cancel_timeout_timer(self) -> None:
        """Cancels the timeout watchdog if active."""
        if self._clustering_timeout_timer is not None:
            self._clustering_timeout_timer.cancel()
            self._clustering_timeout_timer = None

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
                self._image_bounds = raw_data.shape[:2]
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
        kev_factor = self._config.get(
            "global:physics:kev_conversion", 1.02857e-5
        )
        return (
            float(info.min * kev_factor),
            float(info.max * kev_factor),
        )

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

    @property
    def activeTool(self) -> ActiveTool:
        return self._activeTool

    @property
    def isPointerActive(self) -> bool:
        return self._activeTool == ActiveTool.POINTER

    @property
    def isMagnifierActive(self) -> bool:
        return self._activeTool == ActiveTool.MAGNIFIER

    @property
    def magnificationFactor(self) -> float:
        return self._magnificationFactor

    @property
    def kevConversionFactor(self) -> float:
        return self._config.get("global:physics:kev_conversion", 1.02857e-5)

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
        value = float(raw[row, col]) * self.kevConversionFactor
        return (row, col, value)

    @property
    def magnifierPosition(self) -> Tuple[int, int]:
        return self._magnifier_pos

    @property
    def magnifierMoveStep(self) -> int:
        return self._config.get(
            "gui:raw_analysis:magnifier_move_step", 1
        )

    @property
    def showToolHints(self) -> bool:
        return self._config.get(
            "gui:raw_analysis:show_tool_hints", True
        )

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

    def add_magnifier_position_changed_callback(
        self, callback: Callable
    ):
        self._on_magnifier_position_changed_callbacks.append(callback)

    def _notify_magnifier_position_changed(self):
        for callback in self._on_magnifier_position_changed_callbacks:
            callback()

    def add_pointer_hover_changed_callback(
        self, callback: Callable
    ):
        self._on_pointer_hover_changed_callbacks.append(callback)

    def _notify_pointer_hover_changed(self):
        for callback in self._on_pointer_hover_changed_callbacks:
            callback()

    def add_roi_changed_callback(self, callback: Callable):
        self._on_roi_changed_callbacks.append(callback)

    def add_box_selection_completed_callback(self, callback: Callable):
        self._on_box_selection_completed_callbacks.append(callback)

    def _notify_roi_changed(self):
        for callback in self._on_roi_changed_callbacks:
            callback()

    def _notify_box_selection_completed(self):
        for callback in self._on_box_selection_completed_callbacks:
            callback()

    def add_clustering_state_changed_callback(
        self, callback: Callable
    ):
        self._on_clustering_state_changed_callbacks.append(callback)

    def add_clustering_completed_callback(
        self, callback: Callable
    ):
        self._on_clustering_completed_callbacks.append(callback)

    def _notify_clustering_state_changed(self):
        for callback in self._on_clustering_state_changed_callbacks:
            callback()

    def _notify_clustering_completed(self):
        for callback in self._on_clustering_completed_callbacks:
            callback()

    def add_clustering_error_callback(
        self, callback: Callable
    ):
        self._on_clustering_error_callbacks.append(callback)

    def _notify_clustering_error(self):
        for callback in self._on_clustering_error_callbacks:
            callback()

    def add_clustering_progress_callback(
        self, callback: Callable
    ):
        """Register a callback for extraction progress updates."""
        self._on_clustering_progress_callbacks.append(callback)

    def _notify_clustering_progress(self) -> None:
        for callback in self._on_clustering_progress_callbacks:
            callback()
