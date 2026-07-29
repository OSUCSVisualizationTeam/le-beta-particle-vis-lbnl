from typing import Optional, TYPE_CHECKING

from .BoundingBox import BoundingBox

if TYPE_CHECKING:
    from .Cluster import Cluster


class AnnotationOverlay:
    """A region of scientific interest to be highlighted on the HUD.

    The bounding_box is expressed in source-scene (FITS pixel) coordinates.
    Additional display fields (label, color override, confidence) may be
    added without changing the HUD API.
    """

    def __init__(
        self,
        bounding_box: BoundingBox,
        cluster: Optional["Cluster"] = None,
    ) -> None:
        self._bounding_box = bounding_box
        self._cluster = cluster

    @property
    def bounding_box(self) -> BoundingBox:
        """Source-scene bounding box in FITS pixel coordinates."""
        return self._bounding_box

    @property
    def cluster(self) -> Optional["Cluster"]:
        """The source Cluster this overlay represents, if any."""
        return self._cluster
