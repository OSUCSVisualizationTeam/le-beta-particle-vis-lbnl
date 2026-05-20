from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.frontend.fitsconverters import Colormap, FastPixmapConverter, ScalingFunction
from le_beta_vis.frontend.theme import ClusterLocationMapColors, HUDAnnotationOverlayColors

_BBOX_PEN_WIDTH = 2
_DEFAULT_RENDER_SIZE = 256


class ClusterLocationMapWidget(QWidget):
    """Display-only minimap showing a full HDU frame with a cluster bounding-box overlay.

    Renders the parent HDU as a grayscale image (no colormap, matching MosaicView)
    and draws a highlight rectangle at the cluster's pixel coordinates so operators
    can watch where detections land on the sensor in real time.
    """

    def __init__(
        self,
        physics: Optional[PhysicsConversionManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._physics = physics
        self._converter = FastPixmapConverter()
        self._pixmap: Optional[QPixmap] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_w: int = 0
        self._frame_h: int = 0
        self._bounding_box: Optional[BoundingBox] = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_hdu_frame(
        self,
        frame: np.ndarray,
        bounding_box: BoundingBox,
    ) -> None:
        """Render *frame* and mark *bounding_box* on it.

        Args:
            frame: Full 2-D HDU pixel array (H × W).
            bounding_box: Cluster extents in HDU pixel coordinates.
        """
        self._frame = frame
        self._frame_h, self._frame_w = frame.shape[:2]
        self._bounding_box = bounding_box
        self._render_pixmap()
        self.update()

    def clear(self) -> None:
        """Remove the current frame and bounding box."""
        self._frame = None
        self._pixmap = None
        self._bounding_box = None
        self._frame_w = 0
        self._frame_h = 0
        self.update()

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        border_pen = QPen(QColor(ClusterLocationMapColors.BORDER))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        if self._pixmap is None:
            painter.setPen(self.palette().color(self.foregroundRole()))
            painter.drawText(
                self.rect().adjusted(1, 1, -1, -1),
                Qt.AlignmentFlag.AlignCenter,
                self.tr("Loading HDU…"),
            )
            return

        px_w = self._pixmap.width()
        px_h = self._pixmap.height()
        inner_w = self.width() - 2
        inner_h = self.height() - 2
        ox = 1 + (inner_w - px_w) // 2
        oy = 1 + (inner_h - px_h) // 2
        painter.drawPixmap(ox, oy, self._pixmap)

        if self._bounding_box is not None and self._frame_w > 0:
            self._draw_bbox(painter, ox, oy, px_w, px_h)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._frame is not None:
            self._render_pixmap()
            self.update()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_pixmap(self) -> None:
        frame_f = np.asarray(self._frame, dtype=np.float64)
        if self._physics is not None:
            frame_f = self._physics.adu_to_kev(frame_f)
        gray_u8 = self._converter.convert(
            frame_f, Colormap.GRAYSCALE, (0.0, 20.0), scaling=ScalingFunction.LOG
        )
        gray_u8 = np.ascontiguousarray(gray_u8)

        h, w = gray_u8.shape
        q_img = QImage(gray_u8.data, w, h, w, QImage.Format_Grayscale8)
        raw_pixmap = QPixmap.fromImage(q_img.copy())

        widget_w = max(1, (self.width() or _DEFAULT_RENDER_SIZE) - 2)
        widget_h = max(1, (self.height() or _DEFAULT_RENDER_SIZE) - 2)
        self._pixmap = raw_pixmap.scaled(
            widget_w,
            widget_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _draw_bbox(
        self,
        painter: QPainter,
        ox: int,
        oy: int,
        px_w: int,
        px_h: int,
    ) -> None:
        bbox = self._bounding_box
        scale_x = px_w / self._frame_w
        scale_y = px_h / self._frame_h

        left = ox + bbox.left * scale_x
        right = ox + bbox.right * scale_x
        # bbox.bottom = lower row index = screen-top; bbox.top = higher = screen-bottom
        top = oy + bbox.bottom * scale_y
        bottom = oy + bbox.top * scale_y

        pen = QPen(QColor(HUDAnnotationOverlayColors.BORDER))
        pen.setWidth(_BBOX_PEN_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(left), int(top), int(right - left), int(bottom - top))
