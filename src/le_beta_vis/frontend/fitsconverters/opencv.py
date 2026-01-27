import numpy as np
from PySide6 import QtGui
from typing import Tuple
from .interface import Fits2QPixmapConverter, ScalingFunction


class OpenCVBasedConverter(Fits2QPixmapConverter):
    """
    High-performance converter using OpenCV to generate false-color bitmaps.
    Uses lazy import for cv2 to avoid CI dependency issues.
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

        # Lazy import to prevent crashes in headless environments lacking libGL
        import cv2

        height, width = matrix.shape
        vmin, vmax = vrange

        # 1. Clip to Range
        if vmin > 0:
            clipped = np.where(matrix < vmin, vmin, matrix)
        else:
            clipped = np.where(matrix < 0, 0, matrix)

        clipped = np.where(clipped > vmax, vmax, clipped)

        # 2. Prepare for Scaling
        data = np.maximum(clipped - vmin, 0)
        denom = vmax - vmin
        if denom <= 0:
            denom = 1.0

        # 3. Apply Scaling Function
        if scaling == ScalingFunction.LOG:
            scaled = np.log1p(data) / np.log1p(denom)
        elif scaling == ScalingFunction.SQRT:
            scaled = np.sqrt(data) / np.sqrt(denom)
        else:
            scaled = data / denom

        # 4. Normalize to 0-255 uint8
        img_8bit = np.clip(scaled * 255, 0, 255).astype(np.uint8)

        # 5. Apply Colormap
        # Map string to OpenCV constant
        # Default to VIRIDIS if unknown
        cmap_id = cv2.COLORMAP_VIRIDIS
        lname = colormap.lower()
        if lname == "plasma":
            cmap_id = cv2.COLORMAP_PLASMA
        elif lname == "inferno":
            cmap_id = cv2.COLORMAP_INFERNO
        elif lname == "magma":
            cmap_id = cv2.COLORMAP_MAGMA
        elif lname == "jet":
            cmap_id = cv2.COLORMAP_JET
        elif lname == "bone":
            cmap_id = cv2.COLORMAP_BONE
        elif lname == "hot":
            cmap_id = cv2.COLORMAP_HOT
        elif lname == "cool":
            cmap_id = cv2.COLORMAP_COOL

        color_img = cv2.applyColorMap(img_8bit, cmap_id)

        # 6. Convert BGR (OpenCV) to RGB (Qt)
        color_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        # Ensure contiguous
        color_img = np.ascontiguousarray(color_img)

        # 7. Create QImage
        # Format_RGB888 expects 3 bytes per pixel
        bytes_per_line = 3 * width
        q_image = QtGui.QImage(
            color_img.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888
        )

        return QtGui.QPixmap.fromImage(q_image.copy())
