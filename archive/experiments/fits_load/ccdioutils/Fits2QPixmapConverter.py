import numpy as np
from abc import ABC, abstractmethod
from PySide6 import QtGui
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.colors as colors


class Fits2QPixmapConverter(ABC):
    """Fits image to QPixmap converter interface"""

    @abstractmethod
    def convert(self, matrix: np.matrix) -> QtGui.QPixmap:
        """Convert a numpy matrix into a QPixmap"""
        raise NotImplementedError

    def isFast(self) -> bool:
        """
        Tells whether this converter is fast or not.

        A fast converter is able to convert a 3200x550 matrix in less than 25ms
        """
        return False


class MatplotlibBasedConverter(Fits2QPixmapConverter):
    """
    Converts a matrix coming from a FITS file into a QPixmap using matplotlib for intermediate
    pre-processing
    """

    def __init__(self, colormap: colors.Colormap, dpi: int = 100):
        self._colormap = colormap
        self._dpi = dpi

    def convert(self, matrix: np.matrix) -> QtGui.QPixmap:
        height, width = matrix.shape
        fig, ax = plt.subplots(
            figsize=(width / self._dpi, height / self._dpi), dpi=self._dpi
        )

        ax.matshow(matrix, cmap=self._colormap)
        ax.axis("off")
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        buf = BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap


class RawPixmapConverter(Fits2QPixmapConverter):
    """Converts a FITS matrix into an 8-bit grayscale image losing visual information"""

    def convert(self, matrix: np.matrix) -> QtGui.QPixmap:
        height, width = matrix.shape
        q_image = QtGui.QImage(
            matrix.data,
            width,
            height,
            matrix.strides[0],
            QtGui.QImage.Format_Grayscale8,
        )
        return QtGui.QPixmap.fromImage(q_image)


class FastPixmapConverter(Fits2QPixmapConverter):
    """
    Converts a FITS matrix into an 8-bit grayscale image

    This converter clears out negavite values and scales the data down to a range of 256
    levels of gray.
    """

    def convert(self, matrix: np.matrix) -> QtGui.QPixmap:
        height, width = matrix.shape
        if matrix.min() < 0:
            vmatrix = matrix.copy()
            vmatrix[vmatrix < 0] = 0
        else:
            vmatrix = matrix
        valueRange = vmatrix.max()

        vmatrix = vmatrix * 65536 / valueRange

        q_image = QtGui.QImage(
            matrix.data,
            width,
            height,
            matrix.strides[0],
            QtGui.QImage.Format_Grayscale16,
        )
        return QtGui.QPixmap.fromImage(q_image)

    def isFast(self):
        return True
