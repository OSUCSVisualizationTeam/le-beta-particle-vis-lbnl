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


def _pad_to_square(data: np.ndarray) -> np.ndarray:
    """Pad a non-square array to square with zeros.

    Workaround for ``cluster_sigma``'s meshgrid bug where coordinate
    grids get shape ``(ypixels, xpixels)`` instead of
    ``(xpixels, ypixels)``.  Zero-padding is safe — zeros are below
    threshold and contribute no weight to sigma/energy calculations.
    """
    rows, cols = data.shape
    if rows == cols:
        return data
    size = max(rows, cols)
    padded = np.zeros((size, size), dtype=data.dtype)
    padded[:rows, :cols] = data
    return padded


class LBNLClassicalClusterExtractor(ClusterExtractor):
    """Tritium-detection extractor wrapping ``mlccd_diffusion``.

    This backend is specific to the LBNL tritium detection pipeline
    and depends on ``mlccd_diffusion.cluster_sigma`` for sigma and
    energy computation.  It iteratively extracts all qualifying
    clusters (brightest first) by zeroing each found cluster and
    re-running ``cluster_sigma`` until no signal remains.

    Each cluster is characterised with ``sigmaX``, ``sigmaY``,
    ``energy``, and ``pixelCount``.

    For general-purpose multi-cluster ROI analysis without the
    ``mlccd_diffusion`` dependency, use ``GeneralClusterExtractor``.
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
            args=(
                data.copy(), bounding_box, callback,
                progress_callback,
            ),
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
        progress_callback: Optional[Callable[[float], None]],
    ) -> None:
        """Worker executed on background thread."""
        if self._cancelled:
            return
        try:
            results = self._run_impl(
                data, bounding_box, progress_callback,
            )
            if not self._cancelled:
                callback(results)
        except Exception:
            logger.exception("Cluster extraction failed")
            if not self._cancelled:
                callback([])

    def _run_impl(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        progress_callback: Optional[Callable[[float], None]],
    ) -> List[ClusteredEventInfo]:
        """Iteratively extract all clusters via cluster_sigma."""
        from mlccd_diffusion.help_functions import cluster_sigma

        threshold = self._sigma * self._ped_width
        working_data = data.copy()

        # Initial labeling for iteration cap and progress
        _, max_clusters = label(working_data > threshold)
        if max_clusters == 0:
            return []

        results: List[ClusteredEventInfo] = []

        for iteration in range(max_clusters):
            if self._cancelled:
                return []

            event = self._extract_one(
                working_data, threshold, bounding_box,
                cluster_sigma,
            )
            if event is None:
                break

            results.append(event)
            if progress_callback is not None:
                progress_callback(
                    (iteration + 1) / max_clusters
                )

        if progress_callback is not None:
            progress_callback(1.0)

        return results

    def _extract_one(
        self,
        working_data: np.ndarray,
        threshold: float,
        bounding_box: BoundingBox,
        cluster_sigma: Callable,
    ) -> Optional[ClusteredEventInfo]:
        """Extract the brightest remaining cluster, zeroing it.

        Calls ``cluster_sigma`` on the current working data, finds
        the brightest label, builds the event info, and zeros the
        label mask in ``working_data`` so the next iteration skips it.

        Returns None when no above-threshold signal remains.
        """
        padded = _pad_to_square(working_data)
        sigma_x, sigma_y, energy = cluster_sigma(
            padded,
            threshold=threshold,
            min_pixels_in_cluster=_MIN_PIXELS_IN_CLUSTER,
        )

        if energy == 0:
            return None

        labeled_array, num_features = label(
            working_data > threshold
        )
        best_label = _find_brightest_label_by_peak(
            working_data, labeled_array, num_features,
        )
        if best_label is None:
            return None

        event = _build_event_info(
            working_data, labeled_array, best_label,
            bounding_box, sigma_x, sigma_y, energy,
        )

        # Zero all pixels of this cluster so the next iteration
        # skips it.  Uses the label mask (not the display bounding
        # box) to guarantee complete removal.
        working_data[labeled_array == best_label] = 0

        return event
