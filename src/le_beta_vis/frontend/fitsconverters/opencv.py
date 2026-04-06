import numpy as np
from typing import Tuple, Any
from .interface import Fits2QPixmapConverter, ScalingFunction, Colormap
from .colormaps import get_cv2_colormap_id


class OpenCVBasedConverter(Fits2QPixmapConverter):
    """
    High-performance converter using OpenCV to generate false-color buffers.
    Uses lazy import for cv2 to avoid CI dependency issues.
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

        # 5. Buffer
        return self._to_buffer(colorized)

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

    def _colorize(self, matrix: np.ndarray, colormap: Colormap) -> np.ndarray:
        if colormap == Colormap.GRAYSCALE:
            return np.dstack([matrix, matrix, matrix])

        import cv2

        cmap_id = get_cv2_colormap_id(colormap)
        color_img = cv2.applyColorMap(matrix, cmap_id)

        # Convert BGR (OpenCV) to RGB (Qt)
        color_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        return color_img

    def _to_buffer(self, image_data: Any) -> np.ndarray:
        return np.ascontiguousarray(image_data)
