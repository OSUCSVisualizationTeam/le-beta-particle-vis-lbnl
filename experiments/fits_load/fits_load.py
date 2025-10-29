from astropy.io import fits
from sys import argv
import numpy as py


def low(data: py.matrix):
    print(f" Dimensions: {py.ndim(data)}")
    print(f" Shape: {py.shape(data)}")
    row, col = py.shape(data)
    low = data[0][0]
    max = low
    for i in range(row):
        for j in range(col):
            if data[i][j] < low:
                low = data[i][j]
            if data[i][j] > max:
                max = data[i][j]
    print(f" Lowest value: {low}")
    print(f" Max value: {max}")


if __name__ == "__main__":
    with fits.open(argv[1]) as hduList:
        print(f"File: {argv[1]}")
        hduList.info()
        # print(hduList[0].data)
        i = 0
        for hdu in hduList:
            print(f"hdu[{i}]: {type(hdu)}")
            # for header in sorted(hdu.header):
            #    print(f" {header}: {hdu.header[header]}")

            low(hdu.data)
            i += 1
