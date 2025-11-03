from .BoundingBox import BoundingBox
from . import CCDCaptureModel
from .VizFilter import UniformVizFilter
from typing import List
from PySide6 import QtGui
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
from matplotlib import colormaps
from io import BytesIO


class BaseCCDCaptureViewModel(ABC):
    """View Model for CCDCaptureModel models"""

    @abstractmethod
    def crop(self, cropBox: BoundingBox):
        raise NotImplementedError

    @abstractmethod
    def reset(self):
        raise NotImplementedError

    @abstractmethod
    def applyFilter(self, filter: UniformVizFilter):
        raise NotImplementedError

    @abstractmethod
    def extractClusters(self) -> List[BoundingBox]:
        raise NotImplementedError

    @abstractmethod
    def getRawPixmap(self) -> QtGui.QPixmap:
        raise NotImplementedError

    @abstractmethod
    def getMatplotPixmap(self, dpi: int = 100) -> QtGui.QPixmap:
        raise NotImplementedError

    @abstractmethod
    def setCurrentColormap(self, colormap_name: str):
        raise NotImplementedError

    @abstractmethod
    def getCurrentColormap(self) -> str:
        raise NotImplementedError


class CCDCaptureViewModel(BaseCCDCaptureViewModel):
    """View Model for CCDCaptureModel models"""

    def __init__(
        self,
        ccdCapture: CCDCaptureModel,
        cropBox: BoundingBox = BoundingBox.unbounded(),
        defaultColorMap: str = "Greys_r",
    ):
        self.__cropBox = cropBox
        self.__ccdCapture = ccdCapture
        self.__ccdVizCapture = ccdCapture
        self.__defaultColorMap = defaultColorMap
        self.__currentColorMap = defaultColorMap

    def crop(self, cropBox: BoundingBox):
        """Crops the current visualization by the specified BoundingBox"""
        self.__cropBox = cropBox

    def reset(self):
        """Restores displayed CCD capture visualization"""
        self.__ccdVizCapture = self.__ccdCapture
        self.__currentColorMap = self.__defaultColorMap

    def applyFilter(self, filter: UniformVizFilter):
        """Apply a filter to the current visualization"""
        self.__ccdVizCapture.applyFilter(filter)

    def extractClusters(self) -> List[BoundingBox]:
        """Extract a list of relevant bounding boxes containing relevant features"""
        result = list()
        return result

    def getRawPixmap(self) -> QtGui.QPixmap:
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

    def getMatplotPixmap(self, dpi: int = 100) -> QtGui.QPixmap:
        """Convert visualizable data into a QPixmap using matplotlib for rendering"""
        image_data = self.__ccdVizCapture.rawData()

        height, width = image_data.shape
        fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)

        ax.matshow(image_data, cmap=colormaps[self.getCurrentColormap()])

        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", pad_inches="layout")
        buf.seek(0)
        plt.close(fig)

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap

    def setCurrentColormap(self, colormap_name: str):
        self.__currentColorMap = colormap_name

    def getCurrentColormap(self) -> str:
        return self.__currentColorMap
