import numpy as np
from abc import ABC, abstractmethod
from PySide6 import QtGui
from typing import Tuple, Optional


class Fits2QPixmapConverter(ABC):
    """
    FITS image to QPixmap converter interface.
    Responsibility: Nick
    """

    @abstractmethod
    def convert(
        self, matrix: np.ndarray, colormap: str, vrange: Tuple[float, float]
    ) -> QtGui.QPixmap:
        """
        Convert a numpy matrix into a QPixmap.

        Args:
            matrix (np.ndarray): The raw energy data (keV).
            colormap (str): Name of the colormap to apply.
            vrange (Tuple[float, float]): The (min, max) range for normalization.
        """
        raise NotImplementedError


class NoOpConverter(Fits2QPixmapConverter):
    """Temporary placeholder until Nick implements the OpenCV converter."""

    def convert(
        self, matrix: np.ndarray, colormap: str, vrange: Tuple[float, float]
    ) -> QtGui.QPixmap:
        return QtGui.QPixmap()


class FastPixmapConverter(Fits2QPixmapConverter):
    """
    Converts a FITS matrix into an 8-bit grayscale image.
    Optimized for thumbnail generation.
    Applies clipping based on vrange and normalizes to 0-255.
    """

    def convert(
        self, matrix: np.ndarray, colormap: str, vrange: Tuple[float, float]
    ) -> QtGui.QPixmap:
        if matrix is None:
            return QtGui.QPixmap()

        height, width = matrix.shape
        vmin, vmax = vrange

        # 1. Clip data to the specified range (Thresholding)
        # This allows filtering out noise or focusing on high-energy events
        clipped = np.clip(matrix, vmin, vmax)

        # 2. Normalize to 0-255
        if vmax == vmin:
            denom = 1.0
        else:
            denom = vmax - vmin

        # Scale: (val - min) / (max - min) * 255
        scaled = ((clipped - vmin) / denom * 255).astype(np.uint8)

        # 3. Create QImage (Grayscale8)
        # strides[0] is bytes per line. For uint8 (contiguous), it matches width.
        # We must use .copy() to ensure the QImage owns the data if the numpy array is garbage collected
        # or if memory layout isn't compatible.

        q_image = QtGui.QImage(
            scaled.data,
            width,
            height,
            width,  # bytesPerLine for 8-bit
            QtGui.QImage.Format_Grayscale8,
        )

        # Create QPixmap from the image (deep copy logic happens here usually)
        return QtGui.QPixmap.fromImage(q_image.copy())
