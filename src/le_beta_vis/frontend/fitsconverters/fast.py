import numpy as np
from PySide6 import QtGui
from typing import Tuple, Any
from .interface import Fits2QPixmapConverter, ScalingFunction


class FastPixmapConverter(Fits2QPixmapConverter):
    """
    Converts a FITS matrix into an 8-bit grayscale image.
    Optimized for thumbnail generation using auto-scaling (Auto-Levels).
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
        vmin, _ = vrange  # Ignore vmax for thumbnails (auto-levels)

        # 1. Clip
        clipped = self._clip(matrix, vmin, float("inf"))

        # Determine local max for auto-scaling
        # Shift data so vmin becomes 0 for the math
        # We work with positive values only
        data_shifted = np.maximum(clipped - vmin, 0)
        local_max = data_shifted.max()
        if local_max <= 0:
            local_max = 1.0

        # 2. Scale
        scaled = self._scale(data_shifted, scaling, local_max)

        # 3. Normalize
        normalized = self._normalize(
            scaled, 1.0
        )  # Scaled is already 0-1 relative to max

        # 4. Colorize (Grayscale Identity)
        colorized = self._colorize(normalized, colormap)

        # 5. Pixmap
        return self._to_qpixmap(colorized, width, height)

    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        if vmin > 0:
            return np.where(matrix < vmin, 0, matrix)
        else:
            return np.where(matrix < 0, 0, matrix)

    def _scale(
        self, matrix: np.ndarray, scaling: ScalingFunction, max_val: float
    ) -> np.ndarray:
        # matrix is already shifted (clipped - vmin)
        if scaling == ScalingFunction.LOG:
            return np.log1p(matrix) / np.log1p(max_val)
        elif scaling == ScalingFunction.SQRT:
            return np.sqrt(matrix) / np.sqrt(max_val)
        else:
            return matrix / max_val

    def _normalize(self, matrix: np.ndarray, max_val: float) -> np.ndarray:
        # matrix is 0-1 float. max_val is 1.0.
        # Scale to 0-255 uint8
        return np.clip(matrix * 255, 0, 255).astype(np.uint8)

    def _colorize(self, matrix: np.ndarray, colormap: str) -> Any:
        # Fast converter forces grayscale
        # Ensure contiguous array for QImage
        return np.ascontiguousarray(matrix)

    def _to_qpixmap(self, image_data: Any, width: int, height: int) -> QtGui.QPixmap:
        # image_data is uint8 grayscale buffer
        q_image = QtGui.QImage(
            image_data.data,
            width,
            height,
            width,  # bytesPerLine
            QtGui.QImage.Format_Grayscale8,
        )
        return QtGui.QPixmap.fromImage(q_image.copy())
