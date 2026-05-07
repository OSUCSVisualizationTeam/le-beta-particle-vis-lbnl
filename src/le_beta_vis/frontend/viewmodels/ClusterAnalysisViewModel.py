"""ViewModel for cluster extraction controls and results.

Owns all ROI and clustering lifecycle state.
Pure Python — no Qt dependencies.
"""
import logging
import threading
from enum import Enum
from typing import Callable, FrozenSet, List, Optional

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ClusterExtractor import (
    ClusteredEventInfo,
    ClusterExtractor,
)
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.common.RoiRect import RoiRect
from le_beta_vis.frontend.fitsconverters import Colormap

logger = logging.getLogger(__name__)


class ClusteringState(str, Enum):
    """State of the cluster extraction lifecycle."""

    IDLE = "idle"
    RUNNING = "running"


class ClusterAnalysisViewModel:
    """ViewModel owning ROI and cluster extraction state.

    Constructed by RawDataViewModel and exposed as
    ``raw_data_vm.clusterAnalysisViewModel``.
    """

    def __init__(
        self,
        config: ConfigurationService,
        physics_manager: PhysicsConversionManager,
        active_raw_data: Callable[[], Optional[np.ndarray]],
        colormap_provider: Optional[Callable[[], Colormap]] = None,
    ) -> None:
        self._config = config
        self._physics_manager = physics_manager
        self._active_raw_data = active_raw_data
        self._colormap_provider = colormap_provider
        self._init_roi_state()
        self._init_clustering_state()
        self._init_callbacks()

    def _init_roi_state(self) -> None:
        """Initializes the ROI list."""
        self._rois: List[RoiRect] = []

    def _init_clustering_state(self) -> None:
        """Initializes all clustering lifecycle state."""
        self._clusterExtractor: Optional[ClusterExtractor] = None
        self._clusteringState: ClusteringState = ClusteringState.IDLE
        self._clusteringResults: List[ClusteredEventInfo] = []
        self._clusteringError: Optional[str] = None
        self._clusteringProgress: float = 0.0
        self._clustering_timeout_timer: Optional[threading.Timer] = None
        self._selectedClusterIndices: FrozenSet[int] = frozenset()
        self._export_handler: Optional[
            Callable[[List[ClusteredEventInfo]], None]
        ] = None

    def _init_callbacks(self) -> None:
        """Initializes all observer callback registries to empty lists."""
        self._on_active_tool_changed_callbacks: List[Callable] = []
        self._on_roi_changed_callbacks: List[Callable] = []
        self._on_box_selection_completed_callbacks: List[Callable] = []
        self._on_clustering_state_changed_callbacks: List[Callable] = []
        self._on_clustering_completed_callbacks: List[Callable] = []
        self._on_clustering_error_callbacks: List[Callable] = []
        self._on_clustering_progress_callbacks: List[Callable] = []
        self._on_selected_cluster_changed_callbacks: List[Callable] = []

    # --- ROI ---

    @property
    def rois(self) -> List[RoiRect]:
        """Returns a shallow copy of the ROI list."""
        return list(self._rois)

    @property
    def boxSelectColor(self) -> str:
        """Returns the configured box selection color."""
        return self._config.get("gui:raw_analysis:box_select_color", "#00BFFF")

    @property
    def boxSelectBorderWidth(self) -> int:
        """Returns the configured box selection border width."""
        return self._config.get("gui:raw_analysis:box_select_border_width", 2)

    @property
    def selectedRoiRawData(self) -> Optional[np.ndarray]:
        """Returns the raw data cropped to the current ROI, or None."""
        raw = self._active_raw_data()
        if not self._rois or raw is None:
            return None
        return self._rois[-1].extract_raw_data(raw)

    @property
    def selectedRoiBoundingBox(self) -> Optional[BoundingBox]:
        """Returns the bounding box of the current ROI, or None."""
        if not self._rois:
            return None
        return self._rois[-1].geometry()

    def addRoi(self, top: int, left: int, bottom: int, right: int) -> RoiRect:
        """Creates and appends a new rectangular ROI.

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
        """Clears all ROIs and clustering results.

        Notifies listeners if the list was non-empty.
        """
        if self._rois:
            self._rois.clear()
            self._notify_roi_changed()
        self.clearClusteringResults()

    def removeRoi(self, index: int) -> None:
        """Removes an ROI by index. Notifies listeners on success."""
        if 0 <= index < len(self._rois):
            self._rois.pop(index)
            self._notify_roi_changed()

    # --- Clustering config ---

    @property
    def clusteringThreshold(self) -> float:
        """Returns the configured sigma threshold for clustering."""
        return self._config.get("gui:raw_analysis:clustering_threshold", 4.0)

    @property
    def clusteringTimeoutSeconds(self) -> int:
        """Returns the configured clustering timeout in seconds."""
        return self._config.get(
            "gui:raw_analysis:clustering_timeout_seconds", 300
        )

    @property
    def clusterThumbnailColormap(self) -> Optional[Colormap]:
        """Returns the active colormap if thumbnail coloring is enabled.

        Reads ``gui:raw_analysis:cluster_thumbnail_use_colormap``.
        When enabled, returns the current colormap for false-color
        cluster thumbnails. When disabled, returns None (grayscale).
        """
        use_colormap: bool = self._config.get(
            "gui:raw_analysis:cluster_thumbnail_use_colormap", True
        )
        if use_colormap and self._colormap_provider is not None:
            return self._colormap_provider()
        return None

    @property
    def displayEnergyInKev(self) -> bool:
        """Whether cluster energy should be displayed in keV."""
        return bool(
            self._config.get("gui:raw_analysis:display_energy_in_kev", True)
        )

    @property
    def kevConversion(self) -> float:
        """ADU-to-keV conversion factor from configuration."""
        return self._physics_manager.kev_conversion_factor

    # --- Clustering lifecycle ---

    def setClusterExtractor(self, extractor: ClusterExtractor) -> None:
        """Sets the cluster extractor implementation to use."""
        self._clusterExtractor = extractor

    @property
    def isClusteringAvailable(self) -> bool:
        """Returns True when extraction can be triggered.

        Requires: extractor set, at least one ROI, state IDLE,
        and raw data loaded.
        """
        raw = self._active_raw_data()
        return (
            self._clusterExtractor is not None
            and len(self._rois) > 0
            and self._clusteringState == ClusteringState.IDLE
            and raw is not None
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
    def clusteringError(self) -> Optional[str]:
        """Returns the most recent clustering error message, if any."""
        return self._clusteringError

    @property
    def clusteringProgress(self) -> float:
        """Returns the current extraction progress in [0.0, 1.0]."""
        return self._clusteringProgress

    @property
    def selectedClusterIndices(self) -> List[int]:
        """Returns a sorted list of selected cluster indices. Empty = none selected."""
        return sorted(self._selectedClusterIndices)

    @property
    def selectedClusters(self) -> List[ClusteredEventInfo]:
        """Returns the list of currently selected ClusteredEventInfo objects."""
        n = len(self._clusteringResults)
        return [
            self._clusteringResults[i]
            for i in sorted(self._selectedClusterIndices)
            if 0 <= i < n
        ]

    @property
    def selectedClusterIndex(self) -> int:
        """Backward-compat: returns the single selected index, or -1."""
        if len(self._selectedClusterIndices) == 1:
            return next(iter(self._selectedClusterIndices))
        return -1

    @property
    def selectedCluster(self) -> Optional[ClusteredEventInfo]:
        """Backward-compat: returns the single selected cluster, or None."""
        idx = self.selectedClusterIndex
        if 0 <= idx < len(self._clusteringResults):
            return self._clusteringResults[idx]
        return None

    def selectClusters(self, indices: List[int]) -> None:
        """Sets the multi-selection. Pass an empty list to deselect all.

        Validates each index, silently ignores out-of-range values.
        No-op if the resulting set equals the current selection.
        Notifies listeners only on change.

        Args:
            indices: List of zero-based cluster indices to select.
        """
        n = len(self._clusteringResults)
        valid = frozenset(i for i in indices if 0 <= i < n)
        if valid == self._selectedClusterIndices:
            return
        self._selectedClusterIndices = valid
        self._notify_selected_cluster_changed()

    def selectCluster(self, index: int) -> None:
        """Backward-compat: delegates to selectClusters."""
        self.selectClusters([] if index < 0 else [index])

    def clearClusteringResults(self) -> None:
        """Clears results and resets selection. Notifies listeners."""
        if self._clusteringResults or self._selectedClusterIndices:
            self._clusteringResults = []
            self._selectedClusterIndices = frozenset()
            self._notify_clustering_completed()
            self._notify_selected_cluster_changed()

    def setExportHandler(
        self,
        handler: Optional[Callable[[List[ClusteredEventInfo]], None]],
    ) -> None:
        """Injects the export callback for selected clusters.

        The handler receives the full list of selected clusters so it can
        present a single-file dialog for one cluster or a batch UI for many.
        Kept as an injection seam so this pure-Python VM stays free of
        direct knowledge of the storage/PNG services and Qt file-dialogs.
        """
        self._export_handler = handler

    def classifySelectedCluster(self) -> None:
        """Placeholder for cluster classification (issue #54).

        Logs the request for all selected clusters; no-op until the
        classification pipeline is wired.
        """
        clusters = self.selectedClusters
        if not clusters:
            logger.info("classifySelectedCluster: no cluster selected")
            return
        for cluster in clusters:
            logger.info(
                "classifySelectedCluster: placeholder for cluster at "
                "(%d, %d) with energy %.2f ADU",
                cluster.centerX,
                cluster.centerY,
                cluster.energy,
            )

    def exportSelectedCluster(self) -> None:
        """Requests an export for all currently selected clusters.

        No-op when no handler is wired or no clusters are selected.
        """
        clusters = self.selectedClusters
        if not clusters:
            logger.info("exportSelectedCluster: no cluster selected")
            return
        if self._export_handler is None:
            logger.info(
                "exportSelectedCluster: no handler wired (%d cluster(s) selected)",
                len(clusters),
            )
            return
        self._export_handler(clusters)

    def triggerClustering(self) -> None:
        """Starts cluster extraction on the current ROI.

        No-op when isClusteringAvailable is False.
        Starts a timeout watchdog that aborts the extraction
        if it does not complete within the configured limit.
        """
        if not self.isClusteringAvailable:
            return

        roi = self._rois[-1]
        raw = self._active_raw_data()
        data = roi.extract_raw_data(raw)
        if data is None:
            return

        self._clusteringResults = []
        self._selectedClusterIndices = frozenset()
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
            data,
            bbox,
            self._on_clustering_success,
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

    # --- Observer Pattern ---

    def add_active_tool_changed_callback(self, callback: Callable) -> None:
        """Register callback for active-tool changes (forwarded by RDVM)."""
        self._on_active_tool_changed_callbacks.append(callback)

    def _notify_active_tool_changed(self) -> None:
        for callback in self._on_active_tool_changed_callbacks:
            callback()

    def add_roi_changed_callback(self, callback: Callable) -> None:
        """Register callback for ROI list changes."""
        self._on_roi_changed_callbacks.append(callback)

    def add_box_selection_completed_callback(self, callback: Callable) -> None:
        """Register callback fired when a box selection is finalized."""
        self._on_box_selection_completed_callbacks.append(callback)

    def _notify_roi_changed(self) -> None:
        for callback in self._on_roi_changed_callbacks:
            callback()

    def _notify_box_selection_completed(self) -> None:
        for callback in self._on_box_selection_completed_callbacks:
            callback()

    def add_clustering_state_changed_callback(
        self, callback: Callable
    ) -> None:
        """Register callback for clustering state transitions."""
        self._on_clustering_state_changed_callbacks.append(callback)

    def add_clustering_completed_callback(self, callback: Callable) -> None:
        """Register callback for extraction completion."""
        self._on_clustering_completed_callbacks.append(callback)

    def add_clustering_error_callback(self, callback: Callable) -> None:
        """Register callback for clustering errors."""
        self._on_clustering_error_callbacks.append(callback)

    def add_clustering_progress_callback(self, callback: Callable) -> None:
        """Register callback for extraction progress updates."""
        self._on_clustering_progress_callbacks.append(callback)

    def add_selected_cluster_changed_callback(
        self, callback: Callable
    ) -> None:
        """Register callback for cluster selection changes."""
        self._on_selected_cluster_changed_callbacks.append(callback)

    def _notify_clustering_state_changed(self) -> None:
        for callback in self._on_clustering_state_changed_callbacks:
            callback()

    def _notify_clustering_completed(self) -> None:
        for callback in self._on_clustering_completed_callbacks:
            callback()

    def _notify_clustering_error(self) -> None:
        for callback in self._on_clustering_error_callbacks:
            callback()

    def _notify_clustering_progress(self) -> None:
        for callback in self._on_clustering_progress_callbacks:
            callback()

    def _notify_selected_cluster_changed(self) -> None:
        for callback in self._on_selected_cluster_changed_callbacks:
            callback()
