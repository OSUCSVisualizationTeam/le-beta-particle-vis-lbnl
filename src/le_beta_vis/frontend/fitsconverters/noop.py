import numpy as np
from PySide6 import QtGui
from typing import Tuple, Any
from .interface import Fits2QPixmapConverter, ScalingFunction, Colormap


class NoOpConverter(Fits2QPixmapConverter):
    """
    Placeholder converter that returns an empty QPixmap.
    """

    def convert(
        self,
        matrix: np.ndarray,
        colormap: Colormap,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> QtGui.QPixmap:
        return QtGui.QPixmap()

    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        return matrix

    def _scale(
        self, matrix: np.ndarray, scaling: ScalingFunction, max_val: float
    ) -> np.ndarray:
        return matrix

    def _normalize(self, matrix: np.ndarray, max_val: float) -> np.ndarray:
        return matrix

    def _colorize(self, matrix: np.ndarray, colormap: Colormap) -> Any:
        return matrix

    def _to_qpixmap(self, image_data: Any, width: int, height: int) -> QtGui.QPixmap:
        return QtGui.QPixmap()
