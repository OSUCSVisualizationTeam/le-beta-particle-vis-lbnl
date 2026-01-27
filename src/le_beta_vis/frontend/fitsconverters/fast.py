import numpy as np
from PySide6 import QtGui
from typing import Tuple
from .interface import Fits2QPixmapConverter, ScalingFunction

class FastPixmapConverter(Fits2QPixmapConverter):
    """
    Converts a FITS matrix into an 8-bit grayscale image.
    Optimized for thumbnail generation using auto-scaling (Auto-Levels).
    Ignores colormap argument (always grayscale).
    """

    def convert(
        self, 
        matrix: np.ndarray, 
        colormap: str, 
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR
    ) -> QtGui.QPixmap:
        if matrix is None:
            return QtGui.QPixmap()

        height, width = matrix.shape
        vmin, _ = vrange # Ignore vmax for thumbnails (use auto-levels)

        # 1. Clip floor to remove noise
        if vmin > 0:
            clipped = np.where(matrix < vmin, 0, matrix)
        else:
            clipped = np.where(matrix < 0, 0, matrix)
            
        # 2. Prepare for Scaling (Shift to 0)
        data = np.maximum(clipped - vmin, 0)
        
        # 3. Apply Scaling Function (Auto-leveled)
        local_max = data.max()
        if local_max <= 0: local_max = 1.0

        if scaling == ScalingFunction.LOG:
            scaled = np.log1p(data) / np.log1p(local_max)
        elif scaling == ScalingFunction.SQRT:
            scaled = np.sqrt(data) / np.sqrt(local_max)
        else:
            scaled = data / local_max

        # 4. Normalize to 0-255
        scaled = np.clip(scaled * 255, 0, 255).astype(np.uint8)
        
        # Ensure contiguous array for QImage
        scaled = np.ascontiguousarray(scaled)

        # 5. Create QImage (Grayscale8)
        q_image = QtGui.QImage(
            scaled.data,
            width,
            height,
            width,
            QtGui.QImage.Format_Grayscale8,
        )

        return QtGui.QPixmap.fromImage(q_image.copy())
