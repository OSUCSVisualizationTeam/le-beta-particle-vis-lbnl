import logging
import threading
from typing import Callable, List, Optional, Tuple

import numpy as np
from scipy.ndimage import find_objects, label, maximum_position

from .BoundingBox import BoundingBox
from .ClusterExtractor import ClusteredEventInfo, ClusterExtractor

logger = logging.getLogger(__name__)

_MIN_PIXEL_COUNT = 5
_MIN_ENERGY_KEV = 1.0


def _process_cluster(
    data: np.ndarray,
    labeled_array: np.ndarray,
    label_idx: int,
    slices: Tuple[slice, slice],
    bounding_box: BoundingBox,
    kev_conversion: float,
    energy_min: Optional[float],
    energy_max: Optional[float],
) -> Optional[ClusteredEventInfo]:
    """Build a ClusteredEventInfo for one label, or None if filtered out."""
    sub_label = labeled_array[slices]
    sub_data = data[slices]
    mask = sub_label == label_idx
    cluster_data = np.where(mask, sub_data, 0)

    pixel_count = int(np.count_nonzero(cluster_data))
    if pixel_count < _MIN_PIXEL_COUNT:
        return None

    energy = float(np.sum(cluster_data))
    energy_kev = energy * kev_conversion
    if energy_kev < _MIN_ENERGY_KEV:
        return None

    if energy_min is not None and energy_kev < energy_min:
        return None
    if energy_max is not None and energy_kev > energy_max:
        return None

    max_pos: Tuple[int, ...] = maximum_position(
        cluster_data, labels=sub_label, index=label_idx
    )
    peak_row, peak_col = int(max_pos[0]), int(max_pos[1])

    # Offset within full ROI array
    row_offset = slices[0].start
    col_offset = slices[1].start

    bbox = BoundingBox(
        top=bounding_box.top + row_offset,
        left=bounding_box.left + col_offset,
        bottom=bounding_box.top + row_offset + cluster_data.shape[0],
        right=bounding_box.left + col_offset + cluster_data.shape[1],
    )

    return ClusteredEventInfo(
        boundingBox=bbox,
        data=cluster_data.copy(),
        centerX=bounding_box.left + col_offset + peak_col,
        centerY=bounding_box.top + row_offset + peak_row,
    )


class GeneralClusterExtractor(ClusterExtractor):
    """General-purpose multi-cluster extractor for ROI analysis.

    Returns all qualifying clusters from a region of interest using
    ``scipy.ndimage.find_objects`` for efficient per-cluster slicing.
    Unlike the LBNL backends (which are tritium-detection specific
    and return only the single brightest cluster), this extractor
    applies broad filters (min pixel count, min energy, optional
    energy range) and returns every cluster that passes.
    """

    def __init__(
        self,
        sigma_multiplier: float = 4.0,
        ped_width: int = 1400,
        kev_conversion: float = 1.02857e-5,
    ):
        self._sigma = sigma_multiplier
        self._ped_width = ped_width
        self._kev = kev_conversion
        self._cancelled = False
        self._thread: Optional[threading.Thread] = None

    def extract(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        callback: Callable[[List[ClusteredEventInfo]], None],
        energyMinimum: Optional[float] = None,
        energyMaximum: Optional[float] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Start asynchronous extraction on a daemon thread."""
        self._cancelled = False
        self._thread = threading.Thread(
            target=self._run,
            args=(data.copy(), bounding_box, callback,
                  energyMinimum, energyMaximum, progress_callback),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Cancel in-progress extraction."""
        self._cancelled = True

    def _run(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        callback: Callable[[List[ClusteredEventInfo]], None],
        energy_min: Optional[float],
        energy_max: Optional[float],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Worker executed on background thread."""
        if self._cancelled:
            return
        try:
            results = self._extract_all(
                data, bounding_box, energy_min, energy_max,
                progress_callback,
            )
            if not self._cancelled:
                callback(results)
        except Exception:
            logger.exception("Cluster extraction failed")
            if not self._cancelled:
                callback([])

    def _extract_all(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        energy_min: Optional[float],
        energy_max: Optional[float],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[ClusteredEventInfo]:
        """Label, slice, and filter all clusters."""
        threshold = self._sigma * self._ped_width
        labeled_array, num_features = label(data > threshold)

        if num_features == 0:
            return []

        slices_list = find_objects(labeled_array)
        total = len(slices_list)
        results: List[ClusteredEventInfo] = []

        for label_idx, slices in enumerate(slices_list, start=1):
            if self._cancelled:
                return []
            if slices is None:
                if progress_callback is not None:
                    progress_callback(label_idx / total)
                continue

            event = _process_cluster(
                data, labeled_array, label_idx, slices,
                bounding_box, self._kev, energy_min, energy_max,
            )
            if event is not None:
                results.append(event)

            if progress_callback is not None:
                progress_callback(label_idx / total)

        return results
