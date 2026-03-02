"""Frozen dataclass holding computed statistics for an ROI region."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from .BoundingBox import BoundingBox
from .PhysicsConversionManager import PhysicsConversionManager


@dataclass(frozen=True)
class ROIStatistics:
    """Immutable summary of energy statistics for an ROI slice.

    All keV values are computed via ``PhysicsConversionManager.adu_to_kev()``.
    Statistics are computed over non-zero pixels only (consistent with the
    histogram).
    """

    min_adu: float
    max_adu: float
    min_kev: float
    max_kev: float
    min_roi_coord: Tuple[int, int]
    max_roi_coord: Tuple[int, int]
    min_abs_coord: Tuple[int, int]
    max_abs_coord: Tuple[int, int]
    mean_adu: float
    mean_kev: float
    sigma_adu: float
    sigma_kev: float
    pixel_count: int
    nonzero_count: int

    @staticmethod
    def from_roi_data(
        data: np.ndarray,
        bbox: BoundingBox,
        physics: PhysicsConversionManager,
    ) -> ROIStatistics:
        """Build statistics from a 2-D ADU array and its bounding box.

        Args:
            data: 2-D numpy array of raw ADU pixel values.
            bbox: The absolute bounding box of *data* within the full frame.
            physics: Conversion manager for ADU-to-keV.

        Returns:
            A frozen ``ROIStatistics`` instance.
        """
        nonzero_mask = data != 0
        nonzero_count = int(np.count_nonzero(data))
        pixel_count = int(data.size)

        if nonzero_count == 0:
            return ROIStatistics._empty(pixel_count, bbox)

        return ROIStatistics._compute(
            data, nonzero_mask, nonzero_count, pixel_count, bbox, physics,
        )

    @staticmethod
    def _empty(pixel_count: int, bbox: BoundingBox) -> ROIStatistics:
        """Return an all-zero statistics instance."""
        abs_coord = (bbox.top, bbox.left)
        return ROIStatistics(
            min_adu=0.0, max_adu=0.0,
            min_kev=0.0, max_kev=0.0,
            min_roi_coord=(0, 0), max_roi_coord=(0, 0),
            min_abs_coord=abs_coord, max_abs_coord=abs_coord,
            mean_adu=0.0, mean_kev=0.0,
            sigma_adu=0.0, sigma_kev=0.0,
            pixel_count=pixel_count, nonzero_count=0,
        )

    @staticmethod
    def _compute(
        data: np.ndarray,
        nonzero_mask: np.ndarray,
        nonzero_count: int,
        pixel_count: int,
        bbox: BoundingBox,
        physics: PhysicsConversionManager,
    ) -> ROIStatistics:
        """Compute stats over the non-zero pixels of *data*."""
        nz_values = data[nonzero_mask]

        min_adu = float(nz_values.min())
        max_adu = float(nz_values.max())
        mean_adu = float(nz_values.mean())
        sigma_adu = float(nz_values.std())

        min_idx = int(np.argmin(nz_values))
        max_idx = int(np.argmax(nz_values))
        nz_positions = np.argwhere(nonzero_mask)
        min_roi_coord = (int(nz_positions[min_idx][0]),
                         int(nz_positions[min_idx][1]))
        max_roi_coord = (int(nz_positions[max_idx][0]),
                         int(nz_positions[max_idx][1]))

        min_abs_coord = (min_roi_coord[0] + bbox.top,
                         min_roi_coord[1] + bbox.left)
        max_abs_coord = (max_roi_coord[0] + bbox.top,
                         max_roi_coord[1] + bbox.left)

        return ROIStatistics(
            min_adu=min_adu, max_adu=max_adu,
            min_kev=float(physics.adu_to_kev(min_adu)),
            max_kev=float(physics.adu_to_kev(max_adu)),
            min_roi_coord=min_roi_coord, max_roi_coord=max_roi_coord,
            min_abs_coord=min_abs_coord, max_abs_coord=max_abs_coord,
            mean_adu=mean_adu,
            mean_kev=float(physics.adu_to_kev(mean_adu)),
            sigma_adu=sigma_adu,
            sigma_kev=float(physics.adu_to_kev(sigma_adu)),
            pixel_count=pixel_count, nonzero_count=nonzero_count,
        )
