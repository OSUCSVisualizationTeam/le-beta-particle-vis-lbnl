from abc import ABC, abstractmethod
import numpy as np
from PySide6 import QtGui
from typing import Tuple
from enum import Enum

class ScalingFunction(str, Enum):
    """Available scaling functions for data visualization."""
    LINEAR = "linear"
    LOG = "log"
    SQRT = "sqrt"

class Fits2QPixmapConverter(ABC):
    """
    Interface for converting raw FITS data (keV matrices) into Qt Pixmaps for display.
    """

    @abstractmethod
    def convert(
        self, 
        matrix: np.ndarray, 
        colormap: str, 
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR
    ) -> QtGui.QPixmap:
        """
        Convert a numpy matrix into a QPixmap.

        Args:
            matrix (np.ndarray): The raw energy data (keV).
            colormap (str): Name of the colormap to apply.
            vrange (Tuple[float, float]): The (min, max) range for normalization.
            scaling (ScalingFunction): The transfer function to apply (Linear, Log, Sqrt).
        """
        raise NotImplementedError
