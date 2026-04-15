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
    GRAYSCALE = "grayscale"


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


def generate_gradient_array(
    name: str,
    vmin_ratio: float = 0.0,
    vmax_ratio: float = 1.0,
    width: int = 20,
    height: int = 256,
) -> np.ndarray:
    """
    Generate a vertical gradient as an RGB uint8 NumPy array.

    The full colormap is compressed between ``vmin_ratio`` and
    ``vmax_ratio``.  Rows above ``vmax_ratio`` are filled with the
    top-end color; rows below ``vmin_ratio`` with the bottom-end color.

    :param name: Colormap name (member of ``Colormap``).
    :param vmin_ratio: Lower bound of the active range as a 0-1 ratio.
    :param vmax_ratio: Upper bound of the active range as a 0-1 ratio.
    :param width: Pixel width of the output array.
    :param height: Pixel height of the output array.
    :returns: ``(height, width, 3)`` RGB ``uint8`` array.
    """
    # Grayscale: produce a white-to-black gradient without cv2
    if name == Colormap.GRAYSCALE or name == "grayscale":
        vmin_ratio = float(np.clip(vmin_ratio, 0.0, 1.0))
        vmax_ratio = float(np.clip(vmax_ratio, 0.0, 1.0))
        if vmin_ratio > vmax_ratio:
            vmin_ratio, vmax_ratio = vmax_ratio, vmin_ratio
        positions = np.linspace(1.0, 0.0, height)
        span = vmax_ratio - vmin_ratio
        if span < 1e-9:
            gray_val = int(np.clip(vmin_ratio * 255, 0, 255))
            gray = np.full((height, width), gray_val, dtype=np.uint8)
        else:
            normalized = np.clip((positions - vmin_ratio) / span, 0.0, 1.0)
            gray = (normalized * 255).astype(np.uint8)
            gray = np.tile(gray[:, np.newaxis], (1, width))
        return np.dstack([gray, gray, gray])

    import cv2

    # Clamp to [0, 1] and ensure vmin <= vmax
    vmin_ratio = float(np.clip(vmin_ratio, 0.0, 1.0))
    vmax_ratio = float(np.clip(vmax_ratio, 0.0, 1.0))
    if vmin_ratio > vmax_ratio:
        vmin_ratio, vmax_ratio = vmax_ratio, vmin_ratio

    # positions: 1.0 at top row, 0.0 at bottom row
    positions = np.linspace(1.0, 0.0, height)

    span = vmax_ratio - vmin_ratio
    if span < 1e-9:
        # Degenerate: single color at the given ratio
        gray_val = int(np.clip(vmin_ratio * 255, 0, 255))
        gray = np.full((height, width), gray_val, dtype=np.uint8)
    else:
        normalized = np.clip(
            (positions - vmin_ratio) / span, 0.0, 1.0
        )
        gray_values = (normalized * 255).astype(np.uint8)
        gray = np.tile(gray_values[:, np.newaxis], (1, width))

    cmap_id = get_cv2_colormap_id(name)
    color_img = cv2.applyColorMap(gray, cmap_id)
    color_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)
    return color_img


def generate_gradient_pixmap(
    name: str,
    vmin_ratio: float = 0.0,
    vmax_ratio: float = 1.0,
    width: int = 20,
    height: int = 256,
):
    """
    Generate a vertical gradient QPixmap for the specified colormap.

    Delegates to ``generate_gradient_array`` for the pixel data, then
    wraps the result in a ``QPixmap``.  PySide6 is imported lazily to
    keep this module headless-safe.

    :param name: Colormap name (member of ``Colormap``).
    :param vmin_ratio: Lower bound of the active range as a 0-1 ratio.
    :param vmax_ratio: Upper bound of the active range as a 0-1 ratio.
    :param width: Pixel width of the output pixmap.
    :param height: Pixel height of the output pixmap.
    """
    from PySide6.QtGui import QImage, QPixmap

    color_img = generate_gradient_array(
        name, vmin_ratio, vmax_ratio, width, height
    )

    h, w, ch = color_img.shape
    bytes_per_line = ch * w
    q_img = QImage(
        color_img.data,
        w,
        h,
        bytes_per_line,
        QImage.Format_RGB888,
    )
    # q_img borrows color_img.data (a raw NumPy pointer). .copy() transfers
    # ownership to Qt before color_img goes out of scope.
    return QPixmap.fromImage(q_img.copy())
