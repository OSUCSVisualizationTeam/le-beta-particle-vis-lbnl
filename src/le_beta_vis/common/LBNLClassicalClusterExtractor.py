import logging
import threading
from typing import Callable, List, Optional

import numpy as np
from scipy.ndimage import label

from .BoundingBox import BoundingBox
from .ClusterExtractor import ClusteredEventInfo, ClusterExtractor

logger = logging.getLogger(__name__)

_MIN_PIXELS_IN_CLUSTER = 5


def _find_brightest_label_by_peak(
    data: np.ndarray,
    labeled_array: np.ndarray,
    num_features: int,
) -> Optional[int]:
    """Return the label containing the single brightest pixel.

    Uses ``argmax`` on the thresholded data to locate the peak pixel,
    then reads which label it belongs to.  Returns ``None`` when no
    features are present.
    """
    if num_features == 0:
        return None

    masked = np.where(labeled_array > 0, data, 0)
    peak_idx = int(np.argmax(masked))
    peak_row, peak_col = np.unravel_index(peak_idx, data.shape)
    best_label = int(labeled_array[peak_row, peak_col])

    if best_label == 0:
        return None
    return best_label


def _build_event_info(
    data: np.ndarray,
    labeled_array: np.ndarray,
    best_label: int,
    bounding_box: BoundingBox,
    sigma_x: float,
    sigma_y: float,
    energy: float,
) -> ClusteredEventInfo:
    """Build a ClusteredEventInfo for the given label."""
    cluster_mask = labeled_array == best_label
    cluster_data = np.where(cluster_mask, data, 0)
    pixel_count = int(np.count_nonzero(cluster_mask))

    peak_idx = int(np.argmax(cluster_data))
    peak_row, peak_col = np.unravel_index(peak_idx, data.shape)

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
        centerX=bounding_box.left + int(peak_col),
        centerY=bounding_box.top + int(peak_row),
        sigmaX=sigma_x,
        sigmaY=sigma_y,
        energy=energy,
        pixelCount=pixel_count,
    )


class LBNLClassicalClusterExtractor(ClusterExtractor):
    """Cluster extractor wrapping ``mlccd_diffusion.cluster_sigma``.

    Delegates sigma/energy computation to the canonical lab
    implementation and performs its own ``scipy.ndimage.label``
    call for spatial information (bounding box, peak coords,
    pixel count).

    The brightest cluster is selected by **max single pixel**
    (argmax), matching ``cluster_sigma``'s strategy.
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
        # Lazy import to avoid hard dependency at import time
        from mlccd_diffusion.help_functions import cluster_sigma

        threshold = self._sigma * self._ped_width

        # Pad to square: cluster_sigma has a meshgrid bug where
        # coordinate grids get shape (ypixels, xpixels) instead of
        # (xpixels, ypixels).  For square arrays this is harmless;
        # for non-square it causes a broadcast error.  Zero-padding
        # to square is safe — zeros are below threshold and
        # contribute no weight to sigma/energy calculations.
        rows, cols = data.shape
        if rows != cols:
            size = max(rows, cols)
            padded = np.zeros((size, size), dtype=data.dtype)
            padded[:rows, :cols] = data
        else:
            padded = data

        sigma_x, sigma_y, energy = cluster_sigma(
            padded,
            threshold=threshold,
            min_pixels_in_cluster=_MIN_PIXELS_IN_CLUSTER,
        )

        if self._cancelled:
            return

        if energy == 0:
            callback([])
            return

        # Own labeling for spatial info (on original orientation)
        labeled_array, num_features = label(data > threshold)

        if self._cancelled:
            return

        best_label = _find_brightest_label_by_peak(
            data, labeled_array, num_features
        )

        if best_label is None:
            callback([])
            return

        if self._cancelled:
            return

        event = _build_event_info(
            data, labeled_array, best_label, bounding_box,
            sigma_x, sigma_y, energy,
        )
        if not self._cancelled:
            callback([event])
