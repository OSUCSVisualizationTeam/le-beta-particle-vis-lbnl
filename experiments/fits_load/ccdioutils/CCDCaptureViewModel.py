from .BoundingBox import BoundingBox
from . import CCDCaptureModel
from .VizFilter import UniformVizFilter
from typing import List
from PySide6 import QtGui


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

    def applyFilter(self, filter: UniformVizFilter):
        """Apply a filter to the current visualization"""
        self.__ccdVizCapture.applyFilter(filter)

    def extractClusters(self) -> List[BoundingBox]:
        """Extract a list of relevant bounding boxes containing relevant features"""
        result = list()
        return result

    def getDisplayPixmap(self) -> QtGui.QPixmap:
        """Convert visualizable data into a QPixmap"""
        image_data = self.__ccdVizCapture.rawData()
        height, width = image_data.shape
        q_image = QtGui.QImage(
            image_data.data,
            width,
            height,
            image_data.strides[0],
            QtGui.QImage.Format_Grayscale8,
        )
        return QtGui.QPixmap.fromImage(q_image)
