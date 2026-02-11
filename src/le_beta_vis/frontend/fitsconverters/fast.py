import numpy as np
from typing import Tuple, Any
from .interface import Fits2QPixmapConverter, ScalingFunction, Colormap


class FastPixmapConverter(Fits2QPixmapConverter):
    """
    Converts a FITS matrix into an 8-bit grayscale buffer.
    Optimized for thumbnail generation.
    """

    def convert(
        self,
        matrix: np.ndarray,
        colormap: Colormap,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> np.ndarray:
        if matrix is None:
            return np.array([], dtype=np.uint8)

        vmin, _ = vrange  # Ignore vmax for thumbnails (auto-levels)

        # 1. Clip
        clipped = self._clip(matrix, vmin, float("inf"))

        # Determine local max for auto-scaling
        data_shifted = np.maximum(clipped - vmin, 0)
        local_max = data_shifted.max()
        if local_max <= 0:
            local_max = 1.0

        # 2. Scale
        scaled = self._scale(data_shifted, scaling, local_max)

        # 3. Normalize
        normalized = self._normalize(scaled, 1.0)

        # 4. Colorize (Grayscale Identity)
        colorized = self._colorize(normalized, colormap)

        # 5. Buffer
        return self._to_buffer(colorized)

    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        if vmin > 0:
            return np.where(matrix < vmin, 0, matrix)
        else:
            return np.where(matrix < 0, 0, matrix)

    def _scale(
        self, matrix: np.ndarray, scaling: ScalingFunction, max_val: float
    ) -> np.ndarray:
        if scaling == ScalingFunction.LOG:
            return np.log1p(matrix) / np.log1p(max_val)
        elif scaling == ScalingFunction.SQRT:
            return np.sqrt(matrix) / np.sqrt(max_val)
        else:
            return matrix / max_val

    def _normalize(self, matrix: np.ndarray, max_val: float) -> np.ndarray:
        return np.clip(matrix * 255, 0, 255).astype(np.uint8)

    def _colorize(self, matrix: np.ndarray, colormap: Colormap) -> np.ndarray:
        return matrix

    def _to_buffer(self, image_data: Any) -> np.ndarray:
        # Return contiguous array for QImage consumption in the View
        return np.ascontiguousarray(image_data)
