"""Facade ViewModel for cluster extraction controls.

Delegates all state, methods, and callbacks to the parent
``RawDataViewModel``, keeping ClusterAnalysisView decoupled
from the full raw-data surface area.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

if TYPE_CHECKING:
    from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
    from le_beta_vis.frontend.fitsconverters import Colormap
    from .RawDataViewModel import ClusteringState, RawDataViewModel


class ClusterAnalysisViewModel:
    """Pure-Python facade that forwards clustering state to RawDataViewModel."""

    def __init__(self, parent: RawDataViewModel) -> None:
        self._parent = parent

    # --- Delegated properties ---

    @property
    def clusteringThreshold(self) -> float:
        """Returns the configured sigma threshold for clustering."""
        return self._parent.clusteringThreshold

    @property
    def isClusteringAvailable(self) -> bool:
        """Returns True when extraction can be triggered."""
        return self._parent.isClusteringAvailable

    @property
    def clusteringState(self) -> ClusteringState:
        """Returns the current clustering lifecycle state."""
        return self._parent.clusteringState

    @property
    def clusteringResults(self) -> List[ClusteredEventInfo]:
        """Returns the most recent extraction results."""
        return self._parent.clusteringResults

    @property
    def clusteringProgress(self) -> float:
        """Returns the current extraction progress in [0.0, 1.0]."""
        return self._parent.clusteringProgress

    @property
    def clusteringError(self) -> Optional[str]:
        """Returns the most recent clustering error message, if any."""
        return self._parent.clusteringError

    @property
    def clusterThumbnailColormap(self) -> Optional[Colormap]:
        """Returns the active colormap for thumbnails, or None."""
        return self._parent.clusterThumbnailColormap

    @property
    def displayEnergyInKev(self) -> bool:
        """Whether cluster energy should be displayed in keV."""
        return self._parent.displayEnergyInKev

    @property
    def kevConversion(self) -> float:
        """ADU-to-keV conversion factor."""
        return self._parent.kevConversion

    @property
    def selectedClusterIndex(self) -> int:
        """Returns the index of the currently selected cluster."""
        return self._parent.selectedClusterIndex

    # --- Delegated methods ---

    def triggerClustering(self) -> None:
        """Starts cluster extraction on the current ROI."""
        self._parent.triggerClustering()

    def cancelClustering(self) -> None:
        """Cancels any in-progress cluster extraction."""
        self._parent.cancelClustering()

    def selectCluster(self, index: int) -> None:
        """Selects a cluster by index."""
        self._parent.selectCluster(index)

    def classifySelectedCluster(self) -> None:
        """Placeholder for cluster classification."""
        self._parent.classifySelectedCluster()

    def exportSelectedCluster(self) -> None:
        """Placeholder for training data export."""
        self._parent.exportSelectedCluster()

    # --- Delegated callback registration ---

    def add_clustering_state_changed_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for clustering state changes."""
        self._parent.add_clustering_state_changed_callback(callback)

    def add_clustering_completed_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for clustering completion."""
        self._parent.add_clustering_completed_callback(callback)

    def add_clustering_error_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for clustering errors."""
        self._parent.add_clustering_error_callback(callback)

    def add_clustering_progress_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for clustering progress updates."""
        self._parent.add_clustering_progress_callback(callback)

    def add_selected_cluster_changed_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for cluster selection changes."""
        self._parent.add_selected_cluster_changed_callback(callback)

    def add_active_tool_changed_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for active tool changes."""
        self._parent.add_active_tool_changed_callback(callback)

    def add_roi_changed_callback(
        self, callback: Callable,
    ) -> None:
        """Register callback for ROI changes."""
        self._parent.add_roi_changed_callback(callback)
