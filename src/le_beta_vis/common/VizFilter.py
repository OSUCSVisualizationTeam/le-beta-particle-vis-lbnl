from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
from skimage.filters import gaussian

from .FilterSpec import FilterSpec, ParameterSpec, ParameterType


class ScalingFunction(str, Enum):
    """Available scaling functions for data visualization.

    Used by ``UniformFilter.ScalePreset`` and (historically) by
    ``Fits2QPixmapConverter`` in ``frontend/fitsconverters/interface.py``.
    Defined in ``common`` so filters can reference it without inverting
    the dependency direction (common must not depend on frontend).
    """

    LINEAR = "linear"
    LOG = "log"
    SQRT = "sqrt"


class UniformVizFilter(ABC):
    """A filter that is to be applied uniformly to all pixels in the capture."""

    @abstractmethod
    def filter(self, matrix: np.ndarray) -> np.ndarray:
        return matrix


class PerPixelFilter(ABC):
    """A filter that is to be applied to a single pixel value at a specified location."""

    @abstractmethod
    def filter(self, row: int, col: int, value: float) -> float:
        return value


class PerValueFilter(ABC):
    """A filter that is to be applied to specific values."""

    @abstractmethod
    def filter(self, value: float) -> float:
        return value


class UniformFilter:

    class ScalarMultiply(UniformVizFilter):
        """Dot product filter, applies to all values in the matrix at once.

        ``factor`` is a public attribute so the IFS parameter popover can
        read and write it directly via ``getattr`` / ``setattr``.
        """

        def __init__(self, factor: float = 1.0):
            self.factor = factor

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            matrix = omatrix.copy()
            return self.factor * matrix

    class Add(UniformVizFilter):
        """Additive filter, adds a value to all pixels.

        ``value`` is a public attribute so the IFS parameter popover can
        read and write it directly via ``getattr`` / ``setattr``.
        """

        def __init__(self, value: float = 0.0):
            self.value = value

        def filter(self, matrix: np.ndarray) -> np.ndarray:
            return self.value + matrix

    class SubstituteInRange(UniformVizFilter):
        """Substitutes values in a range by a given value.

        ``start``, ``end``, and ``value`` are public attributes so the IFS
        parameter popover can read and write them via ``getattr`` / ``setattr``.
        """

        def __init__(self, start: float = 0.0, end: float = 1.0, value: float = 0.0):
            self.start = start
            self.end = end
            self.value = value

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            matrix = omatrix.copy()
            matrix[(matrix >= self.start) & (matrix <= self.end)] = self.value
            return matrix

    class SubstituteOutOfRange(UniformVizFilter):
        """Substitutes values out of a range by a given value.

        ``start``, ``end``, and ``value`` are public attributes so the IFS
        parameter popover can read and write them via ``getattr`` / ``setattr``.
        """

        def __init__(self, start: float = 0.0, end: float = 20.0, value: float = 0.0):
            self.start = start
            self.end = end
            self.value = value

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            matrix = omatrix.copy()
            matrix[(matrix < self.start) | (matrix > self.end)] = self.value
            return matrix

    class Gaussian(UniformVizFilter):
        """Applies a Gaussian filter to the matrix for smoothing.

        ``sigma`` is a public attribute so the IFS parameter popover can
        read and write it directly via ``getattr`` / ``setattr``.
        """

        def __init__(self, sigma: float = 1.5):
            self.sigma = sigma

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            return gaussian(omatrix, sigma=self.sigma)

    class ADUtoKeV(UniformVizFilter):
        """Pinned: converts raw ADU to keV via a scalar conversion factor.

        Sits at position 0 in the filter stack. The conversion factor is
        a calibration constant sourced from PhysicsConversionManager at
        seed time and is not exposed as a user-editable parameter.
        """

        def __init__(self, factor: float = 1.02857e-5):
            self.factor = factor

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            return omatrix * self.factor

    class ScalePreset(UniformVizFilter):
        """Pinned: applies Linear / Log / Sqrt to the post-filter buffer.

        Replaces the right-sidebar scaling combo. Sits between user
        filters and Window. Non-linear modes clamp negatives to zero so
        the downstream Window normalize never sees NaN.

        ``mode`` is a public attribute so the IFS parameter popover can
        read and write it directly via ``getattr`` / ``setattr``.
        """

        def __init__(self, mode: ScalingFunction = ScalingFunction.LINEAR):
            self.mode = mode

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            if self.mode == ScalingFunction.LOG:
                return np.log1p(np.maximum(omatrix, 0.0))
            if self.mode == ScalingFunction.SQRT:
                return np.sqrt(np.maximum(omatrix, 0.0))
            return omatrix

    class Window(UniformVizFilter):
        """Pinned: clips to [vmin, vmax] and normalizes to [0, 1].

        Always the last filter before the colormap. Owns the LUT input
        contract: ColormapStage assumes its input lies in [0, 1] and
        Window is the only producer of that range. vmin/vmax are in the
        post-ScalePreset domain — so Log/Sqrt modes interpret vmin/vmax
        in their transformed space.

        ``vmin`` and ``vmax`` are public attributes so the IFS parameter
        popover (and VerticalRangeControl) can read and write them via
        ``getattr`` / ``setattr``.
        """

        def __init__(self, vmin: float = 0.0, vmax: float = 1.0):
            self.vmin = vmin
            self.vmax = vmax

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            denom = self.vmax - self.vmin
            if denom <= 0.0:
                return np.zeros_like(omatrix, dtype=np.float64)
            return np.clip((omatrix - self.vmin) / denom, 0.0, 1.0)


UniformFilter.Gaussian.SPEC = FilterSpec(
    type_id="gaussian_blur",
    display_name="Gaussian Blur",
    parameters=[
        ParameterSpec(
            name="sigma",
            label="σ",
            type=ParameterType.FLOAT,
            min_value=0.1,
            max_value=10.0,
            step=0.1,
            default=1.5,
        ),
    ],
    filter_class=UniformFilter.Gaussian,
)

UniformFilter.Add.SPEC = FilterSpec(
    type_id="add",
    display_name="Offset",
    parameters=[
        ParameterSpec(
            name="value",
            label="Value",
            type=ParameterType.FLOAT,
            step=0.01,
            default=0.0,
            units="keV",
        ),
    ],
    filter_class=UniformFilter.Add,
)

UniformFilter.ScalarMultiply.SPEC = FilterSpec(
    type_id="scalar_multiply",
    display_name="Scale",
    parameters=[
        ParameterSpec(
            name="factor",
            label="Factor",
            type=ParameterType.FLOAT,
            min_value=0.0,
            max_value=10.0,
            step=0.01,
            default=1.0,
        ),
    ],
    filter_class=UniformFilter.ScalarMultiply,
)

UniformFilter.SubstituteInRange.SPEC = FilterSpec(
    type_id="substitute_in_range",
    display_name="Replace In Range",
    parameters=[
        ParameterSpec(name="start", label="Start", type=ParameterType.FLOAT,
                      step=0.01, default=0.0, units="keV"),
        ParameterSpec(name="end", label="End", type=ParameterType.FLOAT,
                      step=0.01, default=1.0, units="keV"),
        ParameterSpec(name="value", label="Value", type=ParameterType.FLOAT,
                      step=0.01, default=0.0, units="keV"),
    ],
    filter_class=UniformFilter.SubstituteInRange,
)

UniformFilter.SubstituteOutOfRange.SPEC = FilterSpec(
    type_id="substitute_out_of_range",
    display_name="Clip to Range",
    parameters=[
        ParameterSpec(name="start", label="Start", type=ParameterType.FLOAT,
                      step=0.01, default=0.0, units="keV"),
        ParameterSpec(name="end", label="End", type=ParameterType.FLOAT,
                      step=0.01, default=20.0, units="keV"),
        ParameterSpec(name="value", label="Value", type=ParameterType.FLOAT,
                      step=0.01, default=0.0, units="keV"),
    ],
    filter_class=UniformFilter.SubstituteOutOfRange,
)

UniformFilter.ADUtoKeV.SPEC = FilterSpec(
    type_id="adu_to_kev",
    display_name="ADU → keV",
    parameters=[],
    filter_class=UniformFilter.ADUtoKeV,
    pinned=True,
)

UniformFilter.ScalePreset.SPEC = FilterSpec(
    type_id="scale_preset",
    display_name="Scaling Mode",
    parameters=[
        ParameterSpec(
            name="mode",
            label="Mode",
            type=ParameterType.ENUM,
            default=ScalingFunction.LINEAR,
            enum_values=[s.value for s in ScalingFunction],
        ),
    ],
    filter_class=UniformFilter.ScalePreset,
    pinned=True,
)

UniformFilter.Window.SPEC = FilterSpec(
    type_id="window",
    display_name="Window",
    parameters=[
        ParameterSpec(name="vmin", label="Min", type=ParameterType.FLOAT,
                      step=0.01, default=0.0),
        ParameterSpec(name="vmax", label="Max", type=ParameterType.FLOAT,
                      step=0.01, default=1.0),
    ],
    filter_class=UniformFilter.Window,
    pinned=True,
)
