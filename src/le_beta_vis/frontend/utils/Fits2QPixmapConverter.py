import numpy as np
from abc import ABC, abstractmethod
from PySide6 import QtGui
from typing import Tuple


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
