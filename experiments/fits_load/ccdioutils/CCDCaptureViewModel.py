from copy import deepcopy
import numpy as np
from .BoundingBox import BoundingBox
from . import CCDCaptureModel
from .VizFilter import UniformVizFilter, UniformFilter
from .Fits2QPixmapConverter import Fits2QPixmapConverter, FastPixmapConverter
from typing import List, Tuple, Callable, Optional
from PySide6 import QtGui
from abc import ABC, abstractmethod


class BaseCCDCaptureViewModel(ABC):
    """View Model for CCDCaptureModel models"""

    @abstractmethod
    def _fits2QPixmapConverter(self) -> Fits2QPixmapConverter:
        raise NotImplementedError

    @abstractmethod
    def _getRawData(self) -> np.matrix:
        raise NotImplementedError

    @abstractmethod
    def crop(self, cropBox: BoundingBox):
        """Crops the current visualization by the specified BoundingBox"""
        raise NotImplementedError

    @abstractmethod
    def reset(self):
        """Restores displayed CCD capture visualization"""
        raise NotImplementedError

    @abstractmethod
    def applyFilter(self, filter: UniformVizFilter, useVizModel: bool = True):
        """Apply a filter to the current visualization"""
        raise NotImplementedError

    @abstractmethod
    def extractClusters(self) -> List[BoundingBox]:
        """Extract a list of relevant bounding boxes containing relevant features"""
        raise NotImplementedError

    def getQPixmap(self) -> QtGui.QPixmap:
        """Obtain a QPixmap using a Fits2QPixmapConverter"""
        return self._fits2QPixmapConverter().convert(self._getRawData())

    @abstractmethod
    def setCurrentColormap(self, colormap_name: str):
        """Set colormap state"""
        raise NotImplementedError

    @abstractmethod
    def getCurrentColormap(self) -> str:
        """Get colormap state"""
        raise NotImplementedError

    @abstractmethod
    def valueAt(self, row: int, col: int) -> float:
        """Get value at row,col in the CCD capture matrix"""
        raise NotImplementedError

    @abstractmethod
    def captureInfo(self) -> CCDCaptureModel.Info:
        """Returns the currently visualized capture information"""
        raise NotImplementedError

    @abstractmethod
    def setVisualizationRange(self, value: Tuple[int, int]):
        """Records the visualization range we are interested in visualizing"""
        raise NotImplementedError

    @abstractmethod
    def getVisualizationRange(self) -> Tuple[int, int]:
        """Return the current visualization range"""
        raise NotImplementedError

    @abstractmethod
    def restrictVisualizationToRange(self, blankValue: float = 0):
        """Updates the visualization data to only reflect values in the visualization range"""
        raise NotImplementedError

    @abstractmethod
    def isUsingAFastQPixmapConverter(self) -> bool:
        """Tells whether a fast FITS to QPixmao converter is being used"""
        raise NotImplementedError


class CCDCaptureViewModel(BaseCCDCaptureViewModel):
    """View Model for CCDCaptureModel models"""

    def __init__(
        self,
        ccdCapture: CCDCaptureModel,
        fits2QPixmapConverter: Fits2QPixmapConverter,
        cropBox: BoundingBox = BoundingBox.unbounded(),
        defaultColorMap: str = "Greys_r",
        conversionFunc: Optional[Callable[[float], float]] = None,
    ):
        self.__cropBox = cropBox
        self.__ccdCapture = ccdCapture
        self.__ccdVizCapture = ccdCapture.copy()
        self.__defaultColorMap = defaultColorMap
        self.__currentColorMap = defaultColorMap
        self._resetVizRange()
        self.__conversionFunc = conversionFunc
        self.__fits2QPixmapConverter = fits2QPixmapConverter

    def _fits2QPixmapConverter(self) -> Fits2QPixmapConverter:
        return self.__fits2QPixmapConverter

    def _getRawData(self) -> np.matrix:
        return self.__ccdVizCapture.rawData()

    def crop(self, cropBox: BoundingBox):
        self.__cropBox = cropBox

    def _resetVizRange(self):
        self.__vizRange = (
            self.__ccdVizCapture.rawData().min(),
            self.__ccdVizCapture.rawData().max(),
        )

    def reset(self):
        self.__ccdVizCapture = deepcopy(self.__ccdCapture)
        self.setCurrentColormap(self.__defaultColorMap)
        self._resetVizRange()

    def applyFilter(self, filter: UniformVizFilter, useVizModel: bool = True):
        if useVizModel:
            self.__ccdVizCapture.applyFilter(filter)
        else:
            self.__ccdVizCapture = deepcopy(self.__ccdCapture)
            self.__ccdVizCapture.applyFilter(filter)

    def extractClusters(self) -> List[BoundingBox]:
        result = list()
        return result

    def setCurrentColormap(self, colormap_name: str):
        self.__currentColorMap = colormap_name
        self.__fits2QPixmapConverter._colormap = colormap_name

    def getCurrentColormap(self) -> str:
        return self.__currentColorMap

    def valueAt(self, row: int, col: int) -> float:
        value = self.__ccdVizCapture.rawData()[row][col]
        if self.__conversionFunc is not None:
            value = self.__conversionFunc(value)
        return value

    def captureInfo(self) -> CCDCaptureModel.Info:
        return self.__ccdVizCapture.info()

    def setVisualizationRange(self, value: Tuple[int, int]):
        self.__vizRange = value

    def getVisualizationRange(self) -> Tuple[int, int]:
        return self.__vizRange

    def restrictVisualizationToRange(self, blankValue: float = 0):
        filter = UniformFilter.SubstituteOutOfRange(
            self.__vizRange[0], self.__vizRange[1], blankValue
        )
        self.applyFilter(filter, useVizModel=False)

    def isUsingAFastQPixmapConverter(self) -> bool:
        if self._fits2QPixmapConverter().isFast():
            return True
        return False
