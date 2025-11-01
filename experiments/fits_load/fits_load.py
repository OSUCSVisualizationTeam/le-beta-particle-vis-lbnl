from astropy.io import fits
from sys import argv
import numpy as np
import matplotlib.pyplot as plt


class VizFilter:
    def __init__(self):
        pass

    def kernel(self, input: float) -> float:
        return input


class SqrtFilter(VizFilter):
    def kernel(self, input: float) -> float:
        return np.sqrt(input)


class LogFilter(VizFilter):
    def kernel(self, input: float) -> float:
        return np.log(input)


class CCDState:
    def __init__(self, ccdData: np.matrix, pedestal: float = 0, kevFactor=1.02857e-5):
        self.__data = ccdData
        self.__pedestal = pedestal
        self.__kevFactor = kevFactor

    def rawData(self) -> np.matrix:
        return self.__data

    def computeKeV(self) -> np.matrix:
        return self.__kevFactor * self.__data

    def keVAt(self, i: int, j: int) -> float:
        return self.__kevFactor * (self.__data[i][j] + self.__pedestal)

    def applyVizFilter(self, filter: VizFilter) -> np.matrix:
        v = np.vectorize(filter.kernel)
        return v(self.__data)


kevFactor = 1.02857e-5


def info(data: np.matrix):
    print(f" Dimensions: {np.ndim(data)}")
    row, col = np.shape(data)
    print(f" Shape: {row}x{col}")
    max = data.max()
    min = data.min()
    print(f" Lowest value: {min}")
    print(f" Max value: {max}")


if __name__ == "__main__":
    with fits.open(argv[1]) as hduList:
        print(f"File: {argv[1]}")
        hduList.info()
        # print(hduList[0].data)
        i = 0
        for hdu in hduList:
            print(f"hdu[{i}]: {type(hdu)}")

            info(hdu.data)

            # Convert to keV
            # kevData = kevFactor * hdu.data
            raw_data = hdu.data
            kevData = raw_data
            if hdu.data.min() < 0:
                raw_data = raw_data + abs(hdu.data.min())
                kevData = raw_data

            # kevData = np.sqrt(raw_data)
            # kevData = np.log2(raw_data)

            # plt.matshow(kevData, cmap="binary_r")
            plt.matshow(kevData, cmap="grey")
            # plt.matshow(kevData)
            plt.title(f"HDU{i}")
            plt.colorbar()

            plt.show()
            i += 1
