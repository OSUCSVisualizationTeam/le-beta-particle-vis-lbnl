from typing import Optional

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from le_beta_vis.common.ParticleType import (
    CLASSIFICATION_THRESHOLD,
    classify_particle,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.frontend.theme import COLOR_BACKGROUND_DEEP

CLUSTER_ROLE = Qt.UserRole + 1
THUMBNAIL_ROLE = Qt.UserRole + 2


class _EventItemDelegate(QStyledItemDelegate):
    """Paints grid items with thumbnail + badge overlays."""

    BADGE_FONT_SIZE = 9
    BADGE_RADIUS = 4
    BADGE_PAD_X = 4
    BADGE_PAD_Y = 2
    BORDER_WIDTH = 2

    def __init__(
        self,
        item_width: int = 140,
        item_height: int = 160,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._item_width = item_width
        self._item_height = item_height
        self._threshold: float = CLASSIFICATION_THRESHOLD
        self._physics: Optional[PhysicsConversionManager] = None
        self._displayKeV: bool = True
        self._smoothScaling: bool = False

    def setItemSize(self, width: int, height: int) -> None:
        """Updates the item dimensions used for sizeHint."""
        self._item_width = width
        self._item_height = height

    def setSmoothScaling(self, enabled: bool) -> None:
        """Enable or disable smooth (anti-aliased) thumbnail scaling."""
        self._smoothScaling = enabled

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        rect = option.rect
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        self._paint_background(painter, rect, is_selected)
        pixmap = index.data(THUMBNAIL_ROLE)
        badge_area = self._paint_thumbnail(painter, rect, pixmap)
        cluster = index.data(CLUSTER_ROLE)
        if cluster is not None:
            particle_type, confidence = classify_particle(cluster, self._threshold)
            self._draw_particle_badge(painter, badge_area, particle_type)
            self._draw_confidence_badge(painter, badge_area, confidence)
            self._draw_energy_label(painter, rect, cluster.energy)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(self._item_width, self._item_height)

    # ------------------------------------------------------------------ #
    # Background & thumbnail helpers                                       #
    # ------------------------------------------------------------------ #

    def _paint_background(
        self, painter: QPainter, rect: QRect, is_selected: bool
    ) -> None:
        """Fills the cell background and draws the selection border."""
        painter.fillRect(rect, QColor(COLOR_BACKGROUND_DEEP))
        if is_selected:
            pen = QPen(QColor("#0078d7"), self.BORDER_WIDTH)
        else:
            pen = QPen(QColor("#555555"), 1)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

    def _paint_thumbnail(
        self, painter: QPainter, rect: QRect, pixmap: Optional[QPixmap]
    ) -> QRect:
        """Draws the thumbnail pixmap and returns the badge area.

        Returns *rect* unchanged when no pixmap is available so badges
        still have a valid anchor.
        """
        if pixmap and not pixmap.isNull():
            thumb_rect = QRect(
                rect.x() + self.BORDER_WIDTH,
                rect.y() + self.BORDER_WIDTH,
                rect.width() - 2 * self.BORDER_WIDTH,
                rect.width() - 2 * self.BORDER_WIDTH,
            )
            painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform,
                self._smoothScaling,
            )
            painter.drawPixmap(thumb_rect, pixmap)
            return thumb_rect
        return rect

    # ------------------------------------------------------------------ #
    # Badge helpers                                                        #
    # ------------------------------------------------------------------ #

    def _draw_badge(
        self,
        painter: QPainter,
        x: int,
        y: int,
        text: str,
        bg_color: QColor,
        text_color: QColor,
    ) -> None:
        """Renders a rounded-rect badge with *text* at (x, y)."""
        font = QFont()
        font.setPointSize(self.BADGE_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        badge_w = fm.horizontalAdvance(text) + 2 * self.BADGE_PAD_X
        badge_h = fm.height() + 2 * self.BADGE_PAD_Y
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(x, y, badge_w, badge_h, self.BADGE_RADIUS, self.BADGE_RADIUS)
        painter.setPen(text_color)
        painter.drawText(x + self.BADGE_PAD_X, y + self.BADGE_PAD_Y + fm.ascent(), text)

    def _badge_width(self, painter: QPainter, text: str) -> int:
        """Returns the pixel width of a badge for the given *text*."""
        font = QFont()
        font.setPointSize(self.BADGE_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        return painter.fontMetrics().horizontalAdvance(text) + 2 * self.BADGE_PAD_X

    def _draw_particle_badge(
        self, painter: QPainter, area: QRect, particle_type
    ) -> None:
        """Draws the particle type symbol badge (top-left)."""
        self._draw_badge(
            painter,
            area.x() + 4,
            area.y() + 4,
            particle_type.symbol,
            QColor(particle_type.badge_color),
            QColor("white"),
        )

    def _draw_confidence_badge(
        self, painter: QPainter, area: QRect, confidence: float
    ) -> None:
        """Draws the confidence % badge (top-right)."""
        text = f"{confidence * 100:.0f}%"
        bw = self._badge_width(painter, text)
        x = area.right() - bw - 4
        y = area.y() + 4

        threshold = self._threshold
        bg_color = (
            QColor("#2ecc71")
            if confidence >= threshold
            else QColor("#f39c12") if confidence >= 0.5 else QColor("#95a5a6")
        )
        text_color = (
            QColor("white")
            if confidence >= threshold
            else QColor("#fff3cd") if confidence >= 0.5 else QColor("white")
        )
        self._draw_badge(painter, x, y, text, bg_color, text_color)

    def _draw_energy_label(self, painter: QPainter, rect: QRect, energy: float) -> None:
        """Draws a compact energy label at the bottom."""
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#cccccc"))
        if self._physics and self._displayKeV:
            energy_kev = self._physics.adu_to_kev(energy)
            text = f"E={energy_kev:.4f} keV"
        else:
            text = f"E={energy:.0f} ADU"
        painter.drawText(rect.x() + 4, rect.bottom() - 4, text)
