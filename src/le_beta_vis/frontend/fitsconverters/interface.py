from abc import ABC, abstractmethod
import numpy as np
from PySide6 import QtGui
from typing import Tuple, Any
from enum import Enum


class ScalingFunction(str, Enum):
    """Available scaling functions for data visualization."""

    LINEAR = "linear"
    LOG = "log"
    SQRT = "sqrt"


class Fits2QPixmapConverter(ABC):
    """
    Interface for converting raw FITS data (keV matrices) into Qt Pixmaps for display.
    Enforces a consistent pipeline structure: Clip -> Scale -> Normalize -> Colorize -> Pixmap.
    """

    @abstractmethod
    def convert(
        self,
        matrix: np.ndarray,
        colormap: str,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> QtGui.QPixmap:
        """
        Orchestrates the conversion pipeline.
        """
        raise NotImplementedError

    @abstractmethod
    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        """Step 1: Clip data to the specified range/thresholds."""
        raise NotImplementedError

    @abstractmethod
    def _scale(
        self, matrix: np.ndarray, scaling: ScalingFunction, max_val: float
    ) -> np.ndarray:
        """Step 2: Apply the scaling function (Linear, Log, Sqrt)."""
        raise NotImplementedError

    @abstractmethod
    def _normalize(self, matrix: np.ndarray, max_val: float) -> np.ndarray:
        """Step 3: Normalize scaled data to 8-bit integer range (0-255)."""
        raise NotImplementedError

    @abstractmethod
    def _colorize(self, matrix: np.ndarray, colormap: str) -> Any:
        """
        Step 4: Apply false color map (or keep grayscale).
        Returns image data compatible with QImage.
        """
        raise NotImplementedError

    @abstractmethod
    def _to_qpixmap(self, image_data: Any, width: int, height: int) -> QtGui.QPixmap:
        """Step 5: Convert processed image data into a Qt QPixmap."""
        raise NotImplementedError
