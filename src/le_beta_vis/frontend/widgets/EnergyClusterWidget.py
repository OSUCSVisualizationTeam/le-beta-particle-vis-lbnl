from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from le_beta_vis.frontend.fitsconverters import generate_cluster_thumbnail
from le_beta_vis.frontend.fitsconverters.interface import Colormap


class EnergyClusterWidget(QLabel):
    """Displays a cluster's energy data as a false-color thumbnail.

    Encapsulates the full ndarray-to-QImage-to-QPixmap conversion
    pipeline used across the Historical and Raw-Data views.

    Use the ``to_pixmap()`` static method when only a QPixmap is
    needed (e.g. inside a delegate's ``paint()``), or instantiate
    the widget directly for a self-contained thumbnail label.
    """

    def __init__(
        self, size: int = 256, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)

    def setCluster(
        self,
        data: np.ndarray,
        colormap: Optional[Colormap] = None,
    ) -> None:
        """Renders *data* with *colormap* and sets the label pixmap.

        Args:
            data: 2D numpy array of energy values.
            colormap: Colormap enum or None for grayscale.
        """
        pixmap = self.to_pixmap(data, colormap, self._size)
        self.setPixmap(pixmap)

    @staticmethod
    def to_pixmap(
        data: np.ndarray,
        colormap: Optional[Colormap] = None,
        size: Optional[int] = None,
    ) -> QPixmap:
        """Converts cluster energy data to a QPixmap.

        This is the single source of truth for the ndarray-to-QPixmap
        conversion pipeline.  Usable without instantiating a widget
        (e.g. from a ``QStyledItemDelegate``).

        Args:
            data: 2D numpy array of energy values.
            colormap: Colormap enum or None for grayscale.
            size: If given, scales the pixmap to this square size.

        Returns:
            A QPixmap ready for display.
        """
        buffer = generate_cluster_thumbnail(
            data, colormap=colormap, pad_to_square=True
        )
        h, w = buffer.shape[:2]
        if buffer.ndim == 3:
            q_img = QImage(
                buffer.data, w, h, 3 * w, QImage.Format_RGB888
            )
        else:
            q_img = QImage(
                buffer.data, w, h, w, QImage.Format_Grayscale8
            )
        pixmap = QPixmap.fromImage(q_img.copy())
        if size is not None:
            pixmap = pixmap.scaled(
                size, size,
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
        return pixmap

    def clear(self) -> None:
        """Clears the thumbnail label."""
        super().clear()
