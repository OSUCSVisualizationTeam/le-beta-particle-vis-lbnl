from .BoundingBox import BoundingBox
from . import CCDCaptureModel
from . import VizFilter
from typing import List


class CCDCaptureViewModel:
    """View Model for CCDCaptureModel models"""

    def __init__(
        self,
        ccdCapture: CCDCaptureModel,
        cropBox: BoundingBox = BoundingBox.unbounded(),
    ):
        self.__cropBox = cropBox
        self.__ccdCapture = ccdCapture
        self.__ccdVizCapture = ccdCapture

    def crop(self, cropBox: BoundingBox):
        """Crops the current visualization by the specified BoundingBox"""
        self.__cropBox = cropBox

    def reset(self):
        """Restores displayed CCD capture visualization"""
        self.__ccdVizCapture = self.__ccdCapture

    def applyFilter(self, filter: VizFilter):
        """Apply a filter to the current visualization"""
        self.__ccdVizCapture = filter.filter(self.__ccdVizCapture)

    def extractClusters(self) -> List[BoundingBox]:
        """Extract a list of relevant bounding boxes containing relevant features"""
        result = list()
        return result
