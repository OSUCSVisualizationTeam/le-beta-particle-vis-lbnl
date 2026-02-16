from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from .BoundingBox import BoundingBox


class RegionOfInterest(ABC):
    """
    Abstract base class defining the contract for a Region of Interest (ROI).
    Implementations represent spatial selections on CCD image data.
    """

    @abstractmethod
    def geometry(self) -> BoundingBox:
        """Returns the bounding box of this ROI."""
        raise NotImplementedError

    @abstractmethod
    def set_geometry(
        self, top: int, left: int, bottom: int, right: int
    ) -> None:
        """Updates the ROI geometry."""
        raise NotImplementedError

    @abstractmethod
    def extract_raw_data(
        self, source: np.ndarray
    ) -> Optional[np.ndarray]:
        """Crops raw data to this ROI, returning the subarray."""
        raise NotImplementedError

    @abstractmethod
    def extract_rendered_region(
        self, rendered: np.ndarray
    ) -> Optional[np.ndarray]:
        """Crops a rendered RGB buffer to this ROI."""
        raise NotImplementedError

    @abstractmethod
    def run_clustering(self) -> None:
        """Runs cluster extraction within this ROI (future ticket)."""
        raise NotImplementedError
