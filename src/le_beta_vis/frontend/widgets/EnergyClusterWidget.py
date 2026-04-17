from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QCursor, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QToolTip, QWidget

from le_beta_vis.frontend.fitsconverters import generate_cluster_thumbnail
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.theme import TooltipStyle


class EnergyClusterWidget(QLabel):
    """Displays a cluster's energy data as a false-color thumbnail.

    Encapsulates the full ndarray-to-QImage-to-QPixmap conversion
    pipeline used across the Historical and Raw-Data views.

    Use the ``to_pixmap()`` static method when only a QPixmap is
    needed (e.g. inside a delegate's ``paint()``), or instantiate
    the widget directly for a self-contained thumbnail label.

    When ``enable_hover_tooltip`` is True, hovering over a data pixel
    shows a tooltip with that pixel's keV value. Callers must also
    provide an ADU→keV converter via :meth:`set_kev_converter`.
    """

    def __init__(
        self,
        size: int = 256,
        parent: Optional[QWidget] = None,
        enable_hover_tooltip: bool = False,
    ) -> None:
        super().__init__(parent)
        self._size = size
        self._data: Optional[np.ndarray] = None
        self._colormap: Optional[Colormap] = None
        self._kev_converter: Optional[Callable[[float], float]] = None
        self._hover_enabled = enable_hover_tooltip
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        if enable_hover_tooltip:
            self.setMouseTracking(True)

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
        self._data = data
        self._colormap = colormap
        pixmap = self.to_pixmap(data, colormap, self._size)
        self.setPixmap(pixmap)
        self._refreshTooltipAtCursor()

    def setDisplaySize(self, size: int) -> None:
        """Resize the widget and re-render the cached cluster at the new size.

        Args:
            size: Side length in pixels for the square thumbnail.
        """
        if size <= 0 or size == self._size:
            return
        self._size = size
        self.setFixedSize(size, size)
        if self._data is not None:
            pixmap = self.to_pixmap(self._data, self._colormap, size)
            self.setPixmap(pixmap)

    @staticmethod
    def to_pixmap(
        data: np.ndarray,
        colormap: Optional[Colormap] = None,
        size: Optional[int] = None,
        target_side: Optional[int] = None,
    ) -> QPixmap:
        """Converts cluster energy data to a QPixmap.

        This is the single source of truth for the ndarray-to-QPixmap
        conversion pipeline.  Usable without instantiating a widget
        (e.g. from a ``QStyledItemDelegate``).

        Args:
            data: 2D numpy array of energy values.
            colormap: Colormap enum or None for grayscale.
            size: If given, scales the pixmap to this square size.
            target_side: Shared square canvas side for the padding
                step; lets callers align a grid of clusters against a
                common reference so relative sizes are preserved.

        Returns:
            A QPixmap ready for display.
        """
        buffer = generate_cluster_thumbnail(
            data,
            colormap=colormap,
            pad_to_square=True,
            target_side=target_side,
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

    def set_kev_converter(
        self, converter: Optional[Callable[[float], float]],
    ) -> None:
        """Sets the ADU→keV converter used by the hover tooltip.

        Callers should pass ``physicsManager.adu_to_kev``. The
        converter is only consulted when ``enable_hover_tooltip`` was
        set on the constructor; otherwise it is ignored.

        Args:
            converter: Callable mapping a scalar ADU value to keV, or
                ``None`` to disable tooltip rendering.
        """
        self._kev_converter = converter

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._hover_enabled:
            self._renderTooltipAt(
                event.position(), event.globalPosition().toPoint(),
            )
        super().mouseMoveEvent(event)

    def _renderTooltipAt(
        self, local_pos: QPointF, global_pos: QPoint,
    ) -> None:
        """Shows or hides the keV tooltip for a given cursor position."""
        if (
            self._data is None
            or self._kev_converter is None
            or self._size <= 0
        ):
            return
        h, w = self._data.shape[:2]
        if h == 0 or w == 0:
            return
        side = max(h, w)
        off_y = (side - h) // 2
        off_x = (side - w) // 2
        row = int(local_pos.y() * side / self._size) - off_y
        col = int(local_pos.x() * side / self._size) - off_x
        if 0 <= row < h and 0 <= col < w:
            adu = float(self._data[row, col])
            kev = float(self._kev_converter(adu))
            html = (
                f"<span style='{TooltipStyle.BODY}'>"
                f"{kev:.3f} keV</span>"
            )
            QToolTip.showText(global_pos, html, self)
        else:
            QToolTip.hideText()

    def _refreshTooltipAtCursor(self) -> None:
        """Re-renders the tooltip at the current cursor if hovered.

        Called after the displayed data changes so a tooltip already
        on screen reflects the new cluster instead of showing stale
        values from the previous one.
        """
        if not self._hover_enabled or not self.underMouse():
            return
        global_pos = QCursor.pos()
        local_posf = QPointF(self.mapFromGlobal(global_pos))
        self._renderTooltipAt(local_posf, global_pos)

    def leaveEvent(self, event) -> None:
        if self._hover_enabled:
            QToolTip.hideText()
        super().leaveEvent(event)

    def clear(self) -> None:
        """Clears the thumbnail label."""
        self._data = None
        self._colormap = None
        super().clear()
