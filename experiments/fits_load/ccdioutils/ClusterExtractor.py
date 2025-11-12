from abc import ABC, abstractmethod
from PySide6.QtCore import QObject
from .BoundingBox import BoundingBox
from typing import List, Callable
import numpy as np


class ClusteredEventInfo:
    """
    Represents information about a cluster of energy events

    Attributes:
        boundingBox (BoundingBox): A bonding box defining the extents of the clustered events
        data (numpy.matrix): A Numpy matrix containing all the clustered energy events
    """

    def __init__(self, boundingBox: BoundingBox, data: np.matrix):
        self.boundingBox = boundingBox
        self.data = data
        # Plus other meaningful info


class ClusterExtractor(ABC):
    @abstractmethod
    def extract(self, callback: Callable[[List[ClusteredEventInfo]], None]):
        """
        Starts a cluster extraction process and calls the callback upon completion.

        Implementations of this method are encouraged to make use of concurrency. However, it is not
        a requirement.

        Args:
            callback (Callable[[List[ClusteredEventInfo]], None]): A function that will be called
                when the cluster extraction process completes. Receives a list of ClusteredEventInfo
                objects.
        """
        raise NotImplementedError
