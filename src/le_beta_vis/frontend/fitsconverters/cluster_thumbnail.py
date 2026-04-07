from typing import Optional, Tuple

import numpy as np

from .fast import FastPixmapConverter
from .interface import Colormap
from .opencv import OpenCVBasedConverter


def _pad_to_square(buffer: np.ndarray) -> np.ndarray:
    """Centers *buffer* inside a square canvas filled with zeros.

    Handles both 2D grayscale and 3D ``(H, W, 3)`` RGB buffers.
    Returns ``buffer`` unchanged when it is already square.
    Zero is the correct fill value: both the grayscale and the
    OpenCV colormap pipelines map a zero-energy pixel to black,
    so padded pixels are visually indistinguishable from a real
    empty cell.
    """
    h, w = buffer.shape[:2]
    if h == w:
        return buffer
    side = max(h, w)
    pad_top = (side - h) // 2
    pad_bottom = side - h - pad_top
    pad_left = (side - w) // 2
    pad_right = side - w - pad_left
    if buffer.ndim == 3:
        pad_width = ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0))
    else:
        pad_width = ((pad_top, pad_bottom), (pad_left, pad_right))
    return np.pad(buffer, pad_width, mode="constant", constant_values=0)


def generate_cluster_thumbnail(
    data: np.ndarray,
    colormap: Optional[Colormap] = None,
    fallback_size: Tuple[int, int] = (48, 48),
    pad_to_square: bool = False,
) -> np.ndarray:
    """Generates a uint8 buffer from cluster energy data.

    When *colormap* is ``None``, produces a grayscale buffer (2-D)
    via :class:`FastPixmapConverter`.  When a colormap is given,
    produces an RGB buffer (3-D, shape H x W x 3) via
    :class:`OpenCVBasedConverter`.

    Args:
        data: 2D numpy array of energy values from ClusteredEventInfo.
        colormap: Optional colormap for false-color rendering.
        fallback_size: (height, width) returned when data is
            None or empty.
        pad_to_square: When True, pads the shorter axis with zeros
            (black) so the result is square. Useful when the consumer
            paints the thumbnail into a square cell without aspect
            preservation, since pre-squaring the buffer prevents
            stretching downstream.

    Returns:
        A contiguous uint8 numpy array (2D grayscale or 3D RGB).
    """
    if data is None or data.size == 0:
        if colormap is not None:
            buffer = np.zeros((*fallback_size, 3), dtype=np.uint8)
        else:
            buffer = np.zeros(fallback_size, dtype=np.uint8)
        if pad_to_square:
            return _pad_to_square(buffer)
        return buffer

    if colormap is not None:
        converter = OpenCVBasedConverter()
        vmax = float(np.max(data))
        if vmax <= 0:
            vmax = 1.0
        buffer = converter.convert(
            data.astype(float),
            colormap,
            (0.0, vmax),
        )
    else:
        converter = FastPixmapConverter()
        buffer = converter.convert(
            data.astype(float),
            Colormap.VIRIDIS,
            (0.0, float("inf")),
        )

    if pad_to_square:
        return _pad_to_square(buffer)
    return buffer
