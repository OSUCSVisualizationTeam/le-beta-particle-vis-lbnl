import numpy as np
from abc import ABC, abstractmethod
from skimage.filters import gaussian  # Import gaussian filter


class UniformVizFilter(ABC):
    """A filter that is to be applied uniformly to all pixels in the capture"""

    @abstractmethod
    def filter(self, matrix: np.matrix) -> np.matrix:
        return matrix


class PerPixelFilter(ABC):
    """A filter that is to be applied to a single pixel value at a specified location"""

    @abstractmethod
    def filter(self, row: int, col: int, value: float) -> float:
        return value


class PerValueFilter(ABC):
    """A filter that is to be applied to specific values"""

    @abstractmethod
    def filter(self, value: float) -> float:
        return value


class UniformFilter:

    class ScalarMultiply(UniformVizFilter):
        """Dot product filter, applies to all values in the matrix at once"""

        def __init__(self, factor: float):
            self.__factor = factor

        def filter(self, omatrix: np.matrix) -> np.matrix:
            matrix = omatrix.copy()
            return self.__factor * matrix

    class Add(UniformVizFilter):
        """Additive filter, adds a value to all pixels"""

        def __init__(self, value: float):
            self.__value = value

        def filter(self, matrix: np.matrix) -> np.matrix:
            return self.__value + matrix

    class SubstituteInRange(UniformVizFilter):
        """Substitutes values in a range by a given value"""

        def __init__(self, start: float, end: float, value: float):
            self.__value = value
            self.__start = start
            self.__end = end

        def filter(self, omatrix: np.matrix) -> np.matrix:
            matrix = omatrix.copy()
            matrix[(matrix >= self.__start) & (matrix <= self.__end)] = self.__value
            return matrix

    class SubstituteOutOfRange(UniformVizFilter):
        """Substitutes values out of a range by a given value"""

        def __init__(self, start: float, end: float, value: float):
            self.__value = value
            self.__start = start
            self.__end = end

        def filter(self, omatrix: np.matrix) -> np.matrix:
            matrix = omatrix.copy()
            matrix[(matrix < self.__start) | (matrix > self.__end)] = self.__value
            return matrix

    class Gaussian(UniformVizFilter):
        """Applies a Gaussian filter to the matrix for smoothing."""

        def __init__(self, sigma: float):
            """
            Initializes the Gaussian filter.

            Args:
                sigma (float): Standard deviation for Gaussian kernel. Larger values mean more
                blurring.
            """
            self.__sigma = sigma

        def filter(self, omatrix: np.matrix) -> np.matrix:
            return gaussian(omatrix, sigma=self.__sigma)
