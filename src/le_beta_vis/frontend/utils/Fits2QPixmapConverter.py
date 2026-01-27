import numpy as np
from abc import ABC, abstractmethod
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
    FITS image to QPixmap converter interface.
    Responsibility: Nick
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
        Convert a numpy matrix into a QPixmap.

        Args:
            matrix (np.ndarray): The raw energy data (keV).
            colormap (str): Name of the colormap to apply.
            vrange (Tuple[float, float]): The (min, max) range for normalization.
            scaling (ScalingFunction): The transfer function to apply (Linear, Log, Sqrt).
        """
        raise NotImplementedError


class NoOpConverter(Fits2QPixmapConverter):
    """Temporary placeholder until Nick implements the OpenCV converter."""

    def convert(
        self,
        matrix: np.ndarray,
        colormap: str,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> QtGui.QPixmap:
        return QtGui.QPixmap()


class FastPixmapConverter(Fits2QPixmapConverter):
    """
    Converts a FITS matrix into an 8-bit grayscale image.
    Optimized for thumbnail generation.
    Supports Linear, Logarithmic, and Square Root scaling for HDR data.
    """

    def convert(
        self,
        matrix: np.ndarray,
        colormap: str,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> QtGui.QPixmap:
        if matrix is None:
            return QtGui.QPixmap()

        height, width = matrix.shape
        vmin, vmax = vrange

        # 1. Clip Floor (Noise Reduction)
        if vmin > 0:
            clipped = np.where(matrix < vmin, 0, matrix)
        else:
            clipped = np.where(matrix < 0, 0, matrix)

        # 2. Prepare for Scaling
        # Shift data so vmin becomes 0 for the math
        # We work with positive values only
        data = np.maximum(clipped - vmin, 0)
        max_val = vmax - vmin
        if max_val <= 0:
            max_val = 1.0

        # 3. Apply Scaling Function
        if scaling == ScalingFunction.LOG:
            # log(x + 1) / log(max + 1)
            # Use np.log1p for numerical stability with small values
            scaled = np.log1p(data) / np.log1p(max_val)

        elif scaling == ScalingFunction.SQRT:
            # sqrt(x) / sqrt(max)
            scaled = np.sqrt(data) / np.sqrt(max_val)

        else:  # LINEAR
            # x / max
            scaled = data / max_val

        # 4. Normalize to 0-255 and Clip Ceiling
        # Ensure we don't exceed 255 if data > vmax
        scaled = np.clip(scaled * 255, 0, 255).astype(np.uint8)

        # Ensure contiguous array for QImage
        scaled = np.ascontiguousarray(scaled)

        # 5. Create QImage (Grayscale8)
        q_image = QtGui.QImage(
            scaled.data,
            width,
            height,
            width,
            QtGui.QImage.Format_Grayscale8,
        )

        return QtGui.QPixmap.fromImage(q_image.copy())
