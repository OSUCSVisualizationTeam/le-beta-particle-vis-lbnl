"""Shared 256-entry RGB LUTs for the project's ``Colormap`` enum.

Used by:
  * ``DirectPNGClusterExportService`` to colorise cluster card heatmaps.
  * ``InteractiveHistogramWidget`` to colour bar brushes without routing
    through pyqtgraph's matplotlib resolver.

OpenCV supplies the scientific colormaps (VIRIDIS, PLASMA, INFERNO,
MAGMA, JET, BONE, HOT, COOL) natively; ``Colormap.GRAYSCALE`` is built
from a plain numpy ramp since OpenCV does not ship one.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

import numpy as np

from .Colormap import Colormap


@lru_cache(maxsize=16)
def colormap_lut(colormap: Colormap) -> np.ndarray:
    """Return a ``(256, 3)`` uint8 RGB LUT for ``colormap``.

    Cached because LUT construction is invariant and hot on bulk
    renders. Raises ``KeyError`` if an enum value has no OpenCV
    equivalent registered in the mapping below.
    """
    if colormap == Colormap.GRAYSCALE:
        ramp = np.arange(256, dtype=np.uint8)
        return np.repeat(ramp.reshape(256, 1), 3, axis=1)

    import cv2

    cmap_id = _cv2_colormap_ids().get(colormap)
    if cmap_id is None:
        raise KeyError(f"No OpenCV colormap mapping for {colormap!r}")
    gradient = np.arange(256, dtype=np.uint8).reshape(1, 256)
    bgr = cv2.applyColorMap(gradient, cmap_id)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb.reshape(256, 3)


def resolve_colormap(name: Optional[str]) -> Optional[Colormap]:
    """Coerce a string colormap name into a ``Colormap`` enum value.

    Returns ``None`` if ``name`` is ``None`` or unrecognised. Callers
    that need a fallback should substitute their own default (usually
    ``Colormap.VIRIDIS``) on ``None``.
    """
    if name is None:
        return None
    try:
        return Colormap(name)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _cv2_colormap_ids() -> Dict[Colormap, int]:
    """Build the ``Colormap → cv2.COLORMAP_*`` mapping lazily.

    Importing cv2 at module top-level would force the dependency on any
    caller that merely imports this module; keeping the mapping behind
    a cached helper preserves the lazy-import pattern used elsewhere in
    the project (see ``frontend/fitsconverters/opencv.py``).
    """
    import cv2

    return {
        Colormap.VIRIDIS: cv2.COLORMAP_VIRIDIS,
        Colormap.PLASMA: cv2.COLORMAP_PLASMA,
        Colormap.INFERNO: cv2.COLORMAP_INFERNO,
        Colormap.MAGMA: cv2.COLORMAP_MAGMA,
        Colormap.JET: cv2.COLORMAP_JET,
        Colormap.BONE: cv2.COLORMAP_BONE,
        Colormap.HOT: cv2.COLORMAP_HOT,
        Colormap.COOL: cv2.COLORMAP_COOL,
    }
