from typing import Tuple

import numpy as np

from .fast import FastPixmapConverter
from .interface import Colormap


def generate_cluster_thumbnail(
    data: np.ndarray,
    fallback_size: Tuple[int, int] = (48, 48),
) -> np.ndarray:
    """Generates a grayscale uint8 buffer from cluster energy data.

    Uses FastPixmapConverter for auto-leveled grayscale rendering.
    The result is suitable for QImage(Format_Grayscale8) construction.

    Args:
        data: 2D numpy array of energy values from ClusteredEventInfo.
        fallback_size: (height, width) returned when data is None or empty.

    Returns:
        A contiguous uint8 numpy array (2D, grayscale).
    """
    if data is None or data.size == 0:
        return np.zeros(fallback_size, dtype=np.uint8)

    converter = FastPixmapConverter()
    buffer = converter.convert(
        data.astype(float),
        Colormap.VIRIDIS,
        (0.0, float("inf")),
    )
    return buffer
