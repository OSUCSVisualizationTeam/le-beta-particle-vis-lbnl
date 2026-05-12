from typing import List, Optional, Sequence

import numpy as np

from le_beta_vis.common.VizFilter import ScalingFunction, UniformVizFilter

from .interface import Colormap, Fits2QPixmapConverter
from .opencv import OpenCVBasedConverter


class _Stage:
    """Base class for render-pipeline stages (matrix-in / matrix-out)."""

    def apply(self, data: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class FilterStage(_Stage):
    """Runs an ordered chain of :class:`UniformVizFilter` instances.

    The chain is authoritative: ADU→keV, user filters, ScalePreset and
    Window all live here. The last filter (Window) is responsible for
    producing output in ``[0, 1]`` so the downstream colormap can rely
    on that LUT input contract. An empty chain is identity, which would
    leave raw input passing through unchanged — useful for tests.
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
    ``[0, 1]`` — the pinned Window filter at the end of FilterStage
    owns this contract; the converter is invoked with an identity
    vrange.

    When ``enabled`` is ``False``, emits a grayscale ramp from the same
    ``[0, 1]`` input (multiply by 255, cast to ``uint8``, broadcast to
    three channels). No per-frame min/max stretch — Window has already
    normalised, so applying another stretch here would silently override
    the user's chosen window.
    """

    def __init__(
        self,
        colormap: Colormap,
        enabled: bool = True,
        converter: Optional[Fits2QPixmapConverter] = None,
    ) -> None:
        self._colormap = colormap
        self._enabled = enabled
        self._converter = (
            converter if converter is not None else OpenCVBasedConverter()
        )

    def apply(self, data: np.ndarray) -> np.ndarray:
        if self._enabled:
            return self._converter.convert(
                data, self._colormap, (0.0, 1.0), ScalingFunction.LINEAR,
            )
        return self._unit_interval_to_grayscale(data)

    @staticmethod
    def _unit_interval_to_grayscale(data: np.ndarray) -> np.ndarray:
        if data.size == 0:
            return np.array([], dtype=np.uint8)
        as_uint8 = np.clip(data * 255.0, 0, 255).astype(np.uint8)
        rgb = np.dstack([as_uint8, as_uint8, as_uint8])
        return np.ascontiguousarray(rgb)


class RenderPipeline:
    """Composable render pipeline for the Raw Data View.

    Stages: ``FilterStage`` → ``ColormapStage``. The filter chain is
    the full Interactive Filter Stack — pinned (ADU→keV, ScalePreset,
    Window) plus user filters — passed in render order. The pinned
    Window at the end of the chain is what normalises into ``[0, 1]``
    for the colormap.
    """

    def __init__(
        self,
        filters: Sequence[UniformVizFilter],
        colormap: Colormap,
        colormap_enabled: bool = True,
        converter: Optional[Fits2QPixmapConverter] = None,
    ) -> None:
        self._stages: List[_Stage] = [
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
