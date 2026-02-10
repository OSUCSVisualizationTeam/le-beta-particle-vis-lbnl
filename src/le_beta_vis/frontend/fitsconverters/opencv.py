import numpy as np
from PySide6 import QtGui
from typing import Tuple, Any, Dict, Optional
from .interface import Fits2QPixmapConverter, ScalingFunction, Colormap
from .colormaps import get_cv2_colormap_id


class OpenCVBasedConverter(Fits2QPixmapConverter):
    """
    High-performance converter using OpenCV to generate false-color bitmaps.
    Uses lazy import for cv2 to avoid CI dependency issues.
    """

    def convert(
        self,
        matrix: np.ndarray,
        colormap: Colormap,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> QtGui.QPixmap:
        if matrix is None:
            return QtGui.QPixmap()

        height, width = matrix.shape
        vmin, vmax = vrange

        # 1. Clip
        clipped = self._clip(matrix, vmin, vmax)

        # 2. Scale
        denom = vmax - vmin
        if denom <= 0:
            denom = 1.0
        data_shifted = np.maximum(clipped - vmin, 0)

        scaled = self._scale(data_shifted, scaling, denom)

        # 3. Normalize
        normalized = self._normalize(scaled, 1.0)

        # 4. Colorize
        colorized = self._colorize(normalized, colormap)

        # 5. Pixmap
        return self._to_qpixmap(colorized, width, height)

    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        if vmin > 0:
            clipped = np.where(matrix < vmin, vmin, matrix)
        else:
            clipped = np.where(matrix < 0, 0, matrix)
        return np.where(clipped > vmax, vmax, clipped)

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

    def _colorize(self, matrix: np.ndarray, colormap: Colormap) -> Any:
        import cv2

        cmap_id = get_cv2_colormap_id(colormap)
        color_img = cv2.applyColorMap(matrix, cmap_id)

        # Convert BGR (OpenCV) to RGB (Qt)
        color_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        return np.ascontiguousarray(color_img)

    def _to_qpixmap(self, image_data: Any, width: int, height: int) -> QtGui.QPixmap:
        # Format_RGB888 expects 3 bytes per pixel
        bytes_per_line = 3 * width
        q_image = QtGui.QImage(
            image_data.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888
        )
        return QtGui.QPixmap.fromImage(q_image.copy())
