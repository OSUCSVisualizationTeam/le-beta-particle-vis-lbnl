import numpy as np
from typing import Tuple, Any
from .interface import Fits2QPixmapConverter, ScalingFunction, Colormap


class NoOpConverter(Fits2QPixmapConverter):
    """
    Placeholder converter that returns an empty buffer.
    """

    def convert(
        self,
        matrix: np.ndarray,
        colormap: Colormap,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> np.ndarray:
        return np.array([], dtype=np.uint8)

    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        return matrix

    def _scale(
        self, matrix: np.ndarray, scaling: ScalingFunction, max_val: float
    ) -> np.ndarray:
        return matrix

    def _normalize(self, matrix: np.ndarray, max_val: float) -> np.ndarray:
        return matrix

    def _colorize(self, matrix: np.ndarray, colormap: Colormap) -> np.ndarray:
        return matrix

    def _to_buffer(self, image_data: Any) -> np.ndarray:
        return np.array([], dtype=np.uint8)
