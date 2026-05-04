from .BoundingBox import BoundingBox


class AnnotationOverlay:
    """A region of scientific interest to be highlighted on the HUD.

    The bounding_box is expressed in source-scene (FITS pixel) coordinates.
    Additional display fields (label, color override, confidence) may be
    added without changing the HUD API.
    """

    def __init__(self, bounding_box: BoundingBox) -> None:
        self._bounding_box = bounding_box

    @property
    def bounding_box(self) -> BoundingBox:
        """Source-scene bounding box in FITS pixel coordinates."""
        return self._bounding_box
