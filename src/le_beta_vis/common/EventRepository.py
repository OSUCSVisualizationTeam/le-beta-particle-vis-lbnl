from abc import ABC, abstractmethod
from typing import List

from .Cluster import Cluster


class EventRepository(ABC):
    """Abstract interface for fetching persisted cluster events.

    Concrete implementations may use ZMQ, direct SQL, or
    hardcoded data (mock).  The frontend depends only on this
    interface, allowing the backend to evolve independently.
    """

    @abstractmethod
    def fetch_events(self) -> List[Cluster]:
        """Returns all available cluster events.

        Implementations should return a list of ``Cluster``
        objects with classification scores and pixel data
        populated.
        """
        raise NotImplementedError
