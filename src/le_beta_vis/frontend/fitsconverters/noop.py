import numpy as np
from PySide6 import QtGui
from typing import Tuple
from .interface import Fits2QPixmapConverter, ScalingFunction

class NoOpConverter(Fits2QPixmapConverter):
    """
    Placeholder converter that returns an empty QPixmap.
    Useful for testing or when dependencies are missing.
    """

    def convert(
        self, 
        matrix: np.ndarray, 
        colormap: str, 
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR
    ) -> QtGui.QPixmap:
        return QtGui.QPixmap()
