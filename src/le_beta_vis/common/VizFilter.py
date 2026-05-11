from abc import ABC, abstractmethod

import numpy as np
from skimage.filters import gaussian

from .FilterSpec import FilterSpec, ParameterSpec, ParameterType


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

        def __init__(self, start: float = 0.0, end: float = 1000.0, value: float = 0.0):
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

        def __init__(self, start: float = 0.0, end: float = 65535.0, value: float = 0.0):
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
            step=1.0,
            default=0.0,
            units="ADU",
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
                      step=1.0, default=0.0, units="ADU"),
        ParameterSpec(name="end", label="End", type=ParameterType.FLOAT,
                      step=1.0, default=1000.0, units="ADU"),
        ParameterSpec(name="value", label="Value", type=ParameterType.FLOAT,
                      step=1.0, default=0.0, units="ADU"),
    ],
    filter_class=UniformFilter.SubstituteInRange,
)

UniformFilter.SubstituteOutOfRange.SPEC = FilterSpec(
    type_id="substitute_out_of_range",
    display_name="Clip to Range",
    parameters=[
        ParameterSpec(name="start", label="Start", type=ParameterType.FLOAT,
                      step=1.0, default=0.0, units="ADU"),
        ParameterSpec(name="end", label="End", type=ParameterType.FLOAT,
                      step=1.0, default=65535.0, units="ADU"),
        ParameterSpec(name="value", label="Value", type=ParameterType.FLOAT,
                      step=1.0, default=0.0, units="ADU"),
    ],
    filter_class=UniformFilter.SubstituteOutOfRange,
)
