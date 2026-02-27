from enum import Enum

import numpy as np


class Colormap(str, Enum):
    """Available colormaps for false-color visualization."""

    VIRIDIS = "viridis"
    PLASMA = "plasma"
    INFERNO = "inferno"
    MAGMA = "magma"
    JET = "jet"
    BONE = "bone"
    HOT = "hot"
    COOL = "cool"


def get_cv2_colormap_id(name: str) -> int:
    """
    Returns the OpenCV colormap ID for the given string name.
    Lazily imports cv2 to ensure headless compatibility.
    """
    import cv2

    mapping = {
        Colormap.VIRIDIS: cv2.COLORMAP_VIRIDIS,
        Colormap.PLASMA: cv2.COLORMAP_PLASMA,
        Colormap.INFERNO: cv2.COLORMAP_INFERNO,
        Colormap.MAGMA: cv2.COLORMAP_MAGMA,
        Colormap.JET: cv2.COLORMAP_JET,
        Colormap.BONE: cv2.COLORMAP_BONE,
        Colormap.HOT: cv2.COLORMAP_HOT,
        Colormap.COOL: cv2.COLORMAP_COOL,
    }
    # Default to Viridis if unknown
    return mapping.get(name, cv2.COLORMAP_VIRIDIS)


def generate_gradient_pixmap(name: str, width: int = 20, height: int = 256):
    """
    Generates a vertical gradient QPixmap for the specified colormap.
    Used for UI widgets (legends/sliders).
    PySide6 is imported lazily to keep this module headless-safe.
    """
    import cv2
    from PySide6.QtGui import QImage, QPixmap

    ramp = np.linspace(255, 0, height, dtype=np.uint8)
    ramp = np.tile(ramp[:, np.newaxis], (1, width))

    cmap_id = get_cv2_colormap_id(name)
    color_img = cv2.applyColorMap(ramp, cmap_id)
    color_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

    h, w, ch = color_img.shape
    bytes_per_line = ch * w
    q_img = QImage(
        color_img.data,
        w,
        h,
        bytes_per_line,
        QImage.Format_RGB888,
    )
    return QPixmap.fromImage(q_img.copy())
