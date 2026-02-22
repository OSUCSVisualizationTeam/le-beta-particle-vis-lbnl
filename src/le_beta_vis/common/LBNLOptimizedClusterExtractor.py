import logging
import threading
from typing import Callable, List, Optional, Tuple

import numpy as np
from scipy.ndimage import label, maximum_position

from .BoundingBox import BoundingBox
from .ClusterExtractor import ClusteredEventInfo, ClusterExtractor

logger = logging.getLogger(__name__)


def _find_brightest_label(
    data: np.ndarray,
    labeled_array: np.ndarray,
    num_features: int,
    kev_conversion: float,
) -> Optional[int]:
    """Return the label index with the highest energy, or None.

    Skips clusters whose total energy is below 1 keV.
    Label 0 is background and is never considered.
    """
    best_label: Optional[int] = None
    best_energy = 0.0

    for i in range(1, num_features + 1):
        cluster_image = np.where(labeled_array == i, data, 0)
        energy = float(np.sum(cluster_image))
        if energy * kev_conversion < 1.0:
            continue
        if energy > best_energy:
            best_energy = energy
            best_label = i

    return best_label


def _build_event_info(
    data: np.ndarray,
    labeled_array: np.ndarray,
    best_label: int,
    bounding_box: BoundingBox,
) -> ClusteredEventInfo:
    """Build a ClusteredEventInfo for the given label."""
    cluster_data = np.where(labeled_array == best_label, data, 0)

    max_pos: Tuple[int, ...] = maximum_position(
        cluster_data, labels=labeled_array, index=best_label
    )
    peak_row, peak_col = int(max_pos[0]), int(max_pos[1])

    energy = float(np.sum(cluster_data))
    pixel_count = int(np.count_nonzero(cluster_data))

    # 10x10 box centred on peak, fallback to tight nonzero bounds
    rows, cols = data.shape
    if (peak_row - 5 >= 0 and peak_row + 5 <= rows
            and peak_col - 5 >= 0 and peak_col + 5 <= cols):
        y_start, y_end = peak_row - 5, peak_row + 5
        x_start, x_end = peak_col - 5, peak_col + 5
    else:
        indices = np.where(cluster_data > 0)
        y_start = int(np.min(indices[0]))
        y_end = int(np.max(indices[0])) + 1
        x_start = int(np.min(indices[1]))
        x_end = int(np.max(indices[1])) + 1

    sub_data = cluster_data[y_start:y_end, x_start:x_end].copy()
    bbox = BoundingBox(
        top=bounding_box.top + y_start,
        left=bounding_box.left + x_start,
        bottom=bounding_box.top + y_end,
        right=bounding_box.left + x_end,
    )

    return ClusteredEventInfo(
        boundingBox=bbox,
        data=sub_data,
        centerX=bounding_box.left + peak_col,
        centerY=bounding_box.top + peak_row,
        energy=energy,
        pixelCount=pixel_count,
    )


class LBNLOptimizedClusterExtractor(ClusterExtractor):
    """Cluster extractor that returns only the single brightest cluster.

    Selects the brightest cluster by **total energy sum** across all
    labels.  This is the original ported algorithm from
    ``FileProcessing.py:cluster_fits``, fixing the off-by-one in label
    iteration (label 0 is background).
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
            args=(data.copy(), bounding_box, callback),
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
    ) -> None:
        """Worker executed on background thread."""
        if self._cancelled:
            return
        try:
            self._run_impl(data, bounding_box, callback)
        except Exception:
            logger.exception("Cluster extraction failed")
            if not self._cancelled:
                callback([])

    def _run_impl(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        callback: Callable[[List[ClusteredEventInfo]], None],
    ) -> None:
        """Core extraction logic."""
        threshold = self._sigma * self._ped_width
        labeled_array, num_features = label(data > threshold)

        if self._cancelled:
            return

        best = _find_brightest_label(
            data, labeled_array, num_features, self._kev
        )

        if self._cancelled:
            return

        if best is None:
            callback([])
            return

        event = _build_event_info(data, labeled_array, best, bounding_box)
        if not self._cancelled:
            callback([event])
