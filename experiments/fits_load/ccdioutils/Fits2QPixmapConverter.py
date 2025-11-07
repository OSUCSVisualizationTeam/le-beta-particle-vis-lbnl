import numpy as np
from abc import ABC, abstractmethod
from PySide6 import QtGui
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib import colormaps


class Fits2QPixmapConverter(ABC):
    """Fits image to QPixmap converter interface"""

    @abstractmethod
    def convert(self, matrix: np.matrix) -> QtGui.QPixmap:
        """Convert a numpy matrix into a QPixmap"""
        raise NotImplementedError


class MatplotlibBasedConverter(Fits2QPixmapConverter):
    """
    Converts a matrix coming from a FITS file into a QPixmap using matplotlib for intermediate
    pre-processing
    """

    def __init__(self, colormap: plt.Colormap, dpi: int = 100):
        self._colormap = colormap
        self._dpi = dpi

    def convert(self, matrix: np.matrix) -> QtGui.QPixmap:
        height, width = matrix.shape
        fig, ax = plt.subplots(
            figsize=(width / self._dpi, height / self._dpi), dpi=self._dpi
        )

        ax.matshow(matrix, cmap=colormaps[self._colormap])
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
