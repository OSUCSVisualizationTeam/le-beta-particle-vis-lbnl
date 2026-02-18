from typing import Optional

import numpy as np

from .BoundingBox import BoundingBox
from .RegionOfInterest import RegionOfInterest


class RoiRect(RegionOfInterest):
    """
    A rectangular Region of Interest backed by a BoundingBox.
    Supports extracting sub-regions from raw and rendered data arrays.
    """

    def __init__(
        self, top: int, left: int, bottom: int, right: int
    ) -> None:
        self._bbox = BoundingBox(top, left, bottom, right)

    def geometry(self) -> BoundingBox:
        """Returns the bounding box of this ROI."""
        return self._bbox

    def set_geometry(
        self, top: int, left: int, bottom: int, right: int
    ) -> None:
        """Updates the ROI geometry."""
        self._bbox = BoundingBox(top, left, bottom, right)

    def _clamp_and_slice(
        self, source: np.ndarray
    ) -> Optional[np.ndarray]:
        """Clamps the ROI to array bounds and returns the subarray."""
        rows, cols = source.shape[0], source.shape[1]
        top = max(0, min(self._bbox.top, rows))
        left = max(0, min(self._bbox.left, cols))
        bottom = max(0, min(self._bbox.bottom, rows))
        right = max(0, min(self._bbox.right, cols))
        if bottom <= top or right <= left:
            return None
        return source[top:bottom, left:right].copy()

    def extract_raw_data(
        self, source: np.ndarray
    ) -> Optional[np.ndarray]:
        """Crops raw 2D data to this ROI, clamped to source bounds."""
        return self._clamp_and_slice(source)

    def extract_rendered_region(
        self, rendered: np.ndarray
    ) -> Optional[np.ndarray]:
        """Crops a rendered RGB buffer (H, W, C) to this ROI."""
        return self._clamp_and_slice(rendered)

    def run_clustering(self) -> None:
        """No-op stub for future cluster extraction."""
        pass

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RoiRect):
            return NotImplemented
        return self._bbox == other._bbox

    def __repr__(self) -> str:
        b = self._bbox
        return (
            f"RoiRect(top={b.top}, left={b.left}, "
            f"bottom={b.bottom}, right={b.right})"
        )
