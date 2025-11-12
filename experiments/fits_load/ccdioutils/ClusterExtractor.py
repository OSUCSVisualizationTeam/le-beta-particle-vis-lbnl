from abc import ABC, abstractmethod
from .BoundingBox import BoundingBox
from typing import List, Callable, Optional
import numpy as np


class ClusteredEventInfo:
    """
    Represents information about a cluster of energy events

    Attributes:
        boundingBox (BoundingBox): A bonding box defining the extents of the clustered events
        data (numpy.matrix): A Numpy matrix containing all the clustered energy events
        centerX (int): The x-coordinate of the pixel with the maximum energy in the cluster.
        centerY (int): The y-coordinate of the pixel with the maximum energy in the cluster.
    """

    def __init__(
        self, boundingBox: BoundingBox, data: np.matrix, centerX: int, centerY: int
    ):
        self.boundingBox = boundingBox
        self.data = data
        self.centerX = centerX
        self.centerY = centerY
        # Plus other meaningful info


class ClusterExtractor(ABC):
    @abstractmethod
    def extract(
        self,
        callback: Callable[[List[ClusteredEventInfo]], None],
        energyMinimum: Optional[float] = None,
        energyMaximum: Optional[float] = None,
    ):
        """
        Starts a cluster extraction process and calls the callback upon completion.

        Implementations of this method are encouraged to make use of concurrency. However, it is not
        a requirement.

        Args:
            callback (Callable[[List[ClusteredEventInfo]], None]): A function that will be called
                when the cluster extraction process completes. It will receive a list of
                ClusteredEventInfo objects as its single argument.
            energyMinimum (Optional[float], optional): The minimum energy value to consider for
                cluster extraction. Pixels with values below this will be ignored. Defaults to None.
            energyMaximum (Optional[float], optional): The maximum energy value to consider for
                cluster extraction. Pixels with values above this will be ignored. Defaults to None.
        """
        raise NotImplementedError
