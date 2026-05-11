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
        """Dot product filter, applies to all values in the matrix at once."""

        def __init__(self, factor: float):
            self.__factor = factor

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            matrix = omatrix.copy()
            return self.__factor * matrix

    class Add(UniformVizFilter):
        """Additive filter, adds a value to all pixels."""

        def __init__(self, value: float):
            self.__value = value

        def filter(self, matrix: np.ndarray) -> np.ndarray:
            return self.__value + matrix

    class SubstituteInRange(UniformVizFilter):
        """Substitutes values in a range by a given value."""

        def __init__(self, start: float, end: float, value: float):
            self.__value = value
            self.__start = start
            self.__end = end

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            matrix = omatrix.copy()
            matrix[(matrix >= self.__start) & (matrix <= self.__end)] = self.__value
            return matrix

    class SubstituteOutOfRange(UniformVizFilter):
        """Substitutes values out of a range by a given value."""

        def __init__(self, start: float, end: float, value: float):
            self.__value = value
            self.__start = start
            self.__end = end

        def filter(self, omatrix: np.ndarray) -> np.ndarray:
            matrix = omatrix.copy()
            matrix[(matrix < self.__start) | (matrix > self.__end)] = self.__value
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
