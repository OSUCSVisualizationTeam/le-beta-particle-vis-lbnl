from abc import ABC, abstractmethod
from typing import Callable, List, Optional

import numpy as np

from .BoundingBox import BoundingBox


class ClusteredEventInfo:
    """
    Represents information about a cluster of energy events.

    Attributes:
        boundingBox (BoundingBox): A bounding box defining the extents
            of the clustered events.
        data (np.ndarray): A NumPy array containing the clustered
            energy values.
        centerX (int): The x-coordinate (column) of the pixel with
            the maximum energy in the cluster.
        centerY (int): The y-coordinate (row) of the pixel with
            the maximum energy in the cluster.
    """

    def __init__(
        self,
        boundingBox: BoundingBox,
        data: np.ndarray,
        centerX: int,
        centerY: int,
    ):
        self.boundingBox = boundingBox
        self.data = data
        self.centerX = centerX
        self.centerY = centerY


class ClusterExtractor(ABC):
    @abstractmethod
    def extract(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        callback: Callable[[List[ClusteredEventInfo]], None],
        energyMinimum: Optional[float] = None,
        energyMaximum: Optional[float] = None,
    ) -> None:
        """
        Starts an asynchronous cluster extraction process.

        Implementations must run the extraction off the calling
        thread and invoke *callback* with results upon completion.

        Args:
            data: Raw pixel data (2-D NumPy array) for the region.
            bounding_box: The spatial extent of *data* within the
                full capture frame.
            callback: Called with a list of ClusteredEventInfo
                objects when extraction finishes.
            energyMinimum: Ignore pixels below this value.
            energyMaximum: Ignore pixels above this value.
        """
        raise NotImplementedError

    @abstractmethod
    def cancel(self) -> None:
        """Cancels any in-progress extraction.

        After cancel returns the previously supplied callback
        must not be invoked.
        """
        raise NotImplementedError
