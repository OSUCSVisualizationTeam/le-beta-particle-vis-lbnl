from copy import deepcopy
from .BoundingBox import BoundingBox
from . import CCDCaptureModel
from .VizFilter import UniformVizFilter, UniformFilter
from typing import List, Tuple
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

    @abstractmethod
    def valueAt(self, row: int, col: int) -> float:
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
        self.__ccdVizCapture = deepcopy(ccdCapture)
        self.__defaultColorMap = defaultColorMap
        self.__currentColorMap = defaultColorMap
        self.__vizRange = (round(ccdCapture.info().min), round(ccdCapture.info().max))

    def crop(self, cropBox: BoundingBox):
        """Crops the current visualization by the specified BoundingBox"""
        self.__cropBox = cropBox

    def reset(self):
        """Restores displayed CCD capture visualization"""
        self.__ccdVizCapture = deepcopy(self.__ccdCapture)
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
        ax.axis("off")
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        buf = BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap

    def setCurrentColormap(self, colormap_name: str):
        """Set colormap state"""
        self.__currentColorMap = colormap_name

    def getCurrentColormap(self) -> str:
        """Get colormap state"""
        return self.__currentColorMap

    def valueAt(self, row: int, col: int) -> float:
        """Get value at row,col in the CCD capture matrix"""
        return self.__ccdVizCapture.rawData()[row][col]

    def captureInfo(self) -> CCDCaptureModel.Info:
        """Returns the currently visualized capture information"""
        return self.__ccdVizCapture.info()

    def setVisualizationRange(self, value: Tuple[int, int]):
        """Records the visualization range we are interested in visualizing"""
        self.__vizRange = value

    def getVisualizationRange(self) -> Tuple[int, int]:
        """Return the current visualization range"""
        return self.__vizRange

    def restrictVisualizationToRange(self, blankValue: float = 0):
        """Updates the visualization data to only reflect values in the visualization range"""
        filter = UniformFilter.SubstituteOutOfRange(
            self.__vizRange[0], self.__vizRange[1], 0
        )
        self.applyFilter(filter)
