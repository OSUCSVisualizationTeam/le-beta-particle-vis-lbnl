from typing import List, Optional, Sequence, Tuple

import numpy as np

from le_beta_vis.common.VizFilter import UniformVizFilter

from .interface import Colormap, Fits2QPixmapConverter, ScalingFunction
from .opencv import OpenCVBasedConverter


class _Stage:
    """Base class for render-pipeline stages (matrix-in / matrix-out)."""

    def apply(self, data: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class ScaleStage(_Stage):
    """Clips values to ``vrange`` and applies the scaling function.

    Output is a float array in the closed interval ``[0, 1]`` (modulo
    floating-point drift). This is the same math the monolithic
    :class:`OpenCVBasedConverter` ran in steps 1–2 of its pipeline,
    extracted so the filter chain can sit between scaling and
    colormapping.
    """

    def __init__(
        self, scaling: ScalingFunction, vrange: Tuple[float, float]
    ) -> None:
        self._scaling = scaling
        self._vrange = vrange

    def apply(self, data: np.ndarray) -> np.ndarray:
        vmin, vmax = self._vrange
        denom = vmax - vmin
        if denom <= 0:
            denom = 1.0

        if vmin > 0:
            clipped = np.where(data < vmin, vmin, data)
        else:
            clipped = np.where(data < 0, 0, data)
        clipped = np.where(clipped > vmax, vmax, clipped)

        shifted = np.maximum(clipped - vmin, 0)

        if self._scaling == ScalingFunction.LOG:
            return np.log1p(shifted) / np.log1p(denom)
        if self._scaling == ScalingFunction.SQRT:
            return np.sqrt(shifted) / np.sqrt(denom)
        return shifted / denom


class FilterStage(_Stage):
    """Runs an ordered chain of :class:`UniformVizFilter` instances.

    Empty chain is identity. This is the seam the Interactive Filter
    Stack plugs into — issue #31's Gaussian Blur and any future
    user-authored filters take their turn here.
    """

    def __init__(self, filters: Sequence[UniformVizFilter]) -> None:
        self._filters = list(filters)

    def apply(self, data: np.ndarray) -> np.ndarray:
        result = data
        for filt in self._filters:
            result = filt.filter(result)
        return result


class ColormapStage(_Stage):
    """Final stage that produces an RGB ``uint8`` buffer.

    When ``enabled`` is ``True`` (default), delegates the colormap
    application to :class:`OpenCVBasedConverter` so the kernel stays
    aligned with cluster-thumbnail rendering. Input is expected in
    ``[0, 1]``; an identity vrange is passed because the data has
    already been scaled by :class:`ScaleStage` (and possibly modified
    by :class:`FilterStage`).

    When ``enabled`` is ``False``, min/max-normalises the input to a
    ``[0, 255]`` grayscale ramp, returned as a 3-channel ``uint8``
    buffer for ``QImage.Format_RGB888`` compatibility. This is the
    "colormap off" path: scientists see the raw shape of post-filter
    data without colormap interpretation.
    """

    def __init__(
        self,
        colormap: Colormap,
        enabled: bool = True,
        converter: Optional[Fits2QPixmapConverter] = None,
    ) -> None:
        self._colormap = colormap
        self._enabled = enabled
        self._converter = converter if converter is not None else OpenCVBasedConverter()

    def apply(self, data: np.ndarray) -> np.ndarray:
        if self._enabled:
            return self._converter.convert(
                data, self._colormap, (0.0, 1.0), ScalingFunction.LINEAR,
            )
        return self._normalize_to_grayscale(data)

    @staticmethod
    def _normalize_to_grayscale(data: np.ndarray) -> np.ndarray:
        if data.size == 0:
            return np.array([], dtype=np.uint8)
        dmin = float(np.min(data))
        dmax = float(np.max(data))
        denom = dmax - dmin
        if denom <= 0:
            normalized = np.zeros_like(data, dtype=float)
        else:
            normalized = (data - dmin) / denom
        as_uint8 = np.clip(normalized * 255, 0, 255).astype(np.uint8)
        rgb = np.dstack([as_uint8, as_uint8, as_uint8])
        return np.ascontiguousarray(rgb)


class RenderPipeline:
    """Composable render pipeline for the Raw Data View.

    Stages: ``ScaleStage`` → ``FilterStage`` → ``ColormapStage``. The
    filter chain is the Interactive Filter Stack — callers (currently
    :class:`RawDataViewModel`) pass a snapshot of the active
    :class:`UniformVizFilter` list at render time. An empty chain is
    identity, preserving pre-pipeline rendering output.
    """

    def __init__(
        self,
        scaling: ScalingFunction,
        vrange: Tuple[float, float],
        filters: Sequence[UniformVizFilter],
        colormap: Colormap,
        colormap_enabled: bool = True,
        converter: Optional[Fits2QPixmapConverter] = None,
    ) -> None:
        self._stages: List[_Stage] = [
            ScaleStage(scaling, vrange),
            FilterStage(filters),
            ColormapStage(
                colormap, enabled=colormap_enabled, converter=converter,
            ),
        ]

    def render(self, data: np.ndarray) -> np.ndarray:
        if data is None:
            return np.array([], dtype=np.uint8)
        result = data
        for stage in self._stages:
            result = stage.apply(result)
        return result
