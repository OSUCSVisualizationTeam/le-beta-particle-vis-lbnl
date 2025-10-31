from astropy.io import fits
from sys import argv
import numpy as np
import matplotlib.pyplot as plt

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
            kevData = kevFactor * hdu.data

            plt.matshow(kevData, cmap="binary_r")
            plt.title(f"HDU{i}")
            plt.colorbar()

            plt.show()
            i += 1
