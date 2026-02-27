"""Weighted-mean sigma computation for cluster data."""

from typing import Tuple

import numpy as np


def compute_cluster_sigmas(
    data: np.ndarray,
) -> Tuple[float, float]:
    """Compute weighted spatial spread of a cluster.

    Uses the intensity-weighted second moment to determine
    the Gaussian spread along each axis.

    Args:
        data: 2D array of cluster pixel intensities (may contain
            zeros for masked pixels).

    Returns:
        Tuple of (sigma_x, sigma_y). Returns (0.0, 0.0) if the
        total weight is zero (empty or all-zero data).
    """
    sum_weights = np.sum(data)
    if sum_weights <= 0:
        return 0.0, 0.0

    x, y = np.meshgrid(
        np.arange(data.shape[1]),
        np.arange(data.shape[0]),
    )
    mean_x = np.sum(x * data) / sum_weights
    mean_y = np.sum(y * data) / sum_weights
    sigma_x = float(np.sqrt(
        np.sum(data * (x - mean_x) ** 2) / sum_weights
    ))
    sigma_y = float(np.sqrt(
        np.sum(data * (y - mean_y) ** 2) / sum_weights
    ))
    return sigma_x, sigma_y
