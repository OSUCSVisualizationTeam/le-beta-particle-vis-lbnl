from typing import Optional, Tuple

import numpy as np

from .fast import FastPixmapConverter
from .interface import Colormap
from .opencv import OpenCVBasedConverter


def generate_cluster_thumbnail(
    data: np.ndarray,
    colormap: Optional[Colormap] = None,
    fallback_size: Tuple[int, int] = (48, 48),
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

    Returns:
        A contiguous uint8 numpy array (2D grayscale or 3D RGB).
    """
    if data is None or data.size == 0:
        if colormap is not None:
            return np.zeros((*fallback_size, 3), dtype=np.uint8)
        return np.zeros(fallback_size, dtype=np.uint8)

    if colormap is not None:
        converter = OpenCVBasedConverter()
        vmax = float(np.max(data))
        if vmax <= 0:
            vmax = 1.0
        return converter.convert(
            data.astype(float),
            colormap,
            (0.0, vmax),
        )

    converter = FastPixmapConverter()
    return converter.convert(
        data.astype(float),
        Colormap.VIRIDIS,
        (0.0, float("inf")),
    )
