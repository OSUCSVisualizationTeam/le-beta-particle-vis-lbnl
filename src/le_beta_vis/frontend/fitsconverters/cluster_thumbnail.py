from typing import Optional, Tuple

import numpy as np

from .fast import FastPixmapConverter
from .interface import Colormap
from .opencv import OpenCVBasedConverter


def _pad_to_square(
    buffer: np.ndarray, target_side: Optional[int] = None,
) -> np.ndarray:
    """Centers *buffer* inside a square canvas filled with zeros.

    Callers are expected to pass the raw float energy buffer — the
    colormap then paints zero-energy pixels with its own "bottom of
    range" shade, so padded borders blend naturally with the darkest
    real pixels rather than rendering as literal RGB black.

    When ``target_side`` is given, pads to that size instead of
    ``max(h, w)``; useful for rendering a grid of clusters against a
    shared canvas so relative spatial sizes are preserved. The
    caller is responsible for choosing a side no smaller than
    ``max(h, w)``.
    """
    h, w = buffer.shape[:2]
    side = target_side if target_side is not None else max(h, w)
    if h == side and w == side:
        return buffer
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
    target_side: Optional[int] = None,
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
            so the result is square. Padding is applied in energy
            space before the colormap is sampled, so padded pixels
            inherit the colormap's zero-value shade instead of
            rendering as literal black.
        target_side: When given together with ``pad_to_square``,
            pads to exactly this side length. Lets callers align
            many clusters against a shared canvas so relative sizes
            are preserved across a grid. Must be no smaller than
            ``max(data.shape[:2])``.

    Returns:
        A contiguous uint8 numpy array (2D grayscale or 3D RGB).
    """
    if data is None or data.size == 0:
        if colormap is not None:
            buffer = np.zeros((*fallback_size, 3), dtype=np.uint8)
        else:
            buffer = np.zeros(fallback_size, dtype=np.uint8)
        if pad_to_square:
            return _pad_to_square(buffer, target_side=target_side)
        return buffer

    float_data = data.astype(float)
    if pad_to_square:
        float_data = _pad_to_square(float_data, target_side=target_side)

    if colormap is not None:
        converter = OpenCVBasedConverter()
        vmax = float(np.max(float_data))
        if vmax <= 0:
            vmax = 1.0
        return converter.convert(float_data, colormap, (0.0, vmax))

    converter = FastPixmapConverter()
    return converter.convert(
        float_data, Colormap.VIRIDIS, (0.0, float("inf")),
    )
