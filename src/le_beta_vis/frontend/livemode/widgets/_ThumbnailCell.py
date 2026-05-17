"""Private widget: single thumbnail cell for the Live Mode grid.

The cell renders a cluster pixmap and, when conditions allow,
composites particle/confidence/energy badges on top of it. Badge
composition runs on a separate transparent ``QPixmap`` and is then
drawn over the cluster pixmap, so the cluster scaling logic in
``EnergyClusterWidget.to_pixmap`` is never altered.
"""

from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QWidget

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ParticleType import (
    CLASSIFICATION_THRESHOLD,
    ParticleType,
    classify_particle,
)
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.theme import LiveModeBadgeColors
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)


_BADGE_FONT_SIZE = 9
_BADGE_RADIUS = 4
_BADGE_PAD_X = 4
_BADGE_PAD_Y = 2
_BADGE_MARGIN = 4


def _pickBadgeFg(bg: QColor) -> QColor:
    """Returns black or white text — whichever clears WCAG AA against *bg*.

    Uses WCAG 2.1 relative-luminance:
    https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
    """
    def _channel(c: int) -> float:
        s = c / 255.0
        if s <= 0.03928:
            return s / 12.92
        return ((s + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * _channel(bg.red())
        + 0.7152 * _channel(bg.green())
        + 0.0722 * _channel(bg.blue())
    )
    contrast_vs_black = (luminance + 0.05) / 0.05
    contrast_vs_white = 1.05 / (luminance + 0.05)
    if contrast_vs_black >= contrast_vs_white:
        return QColor(LiveModeBadgeColors.TEXT_DARK)
    return QColor(LiveModeBadgeColors.TEXT_LIGHT)


def _badge_font() -> QFont:
    font = QFont()
    font.setPointSize(_BADGE_FONT_SIZE)
    font.setBold(True)
    return font


class _ThumbnailCell(QLabel):
    """Single thumbnail cell, positioned absolutely in the grid."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)

    def setClusterPixmap(
        self,
        cluster: Optional[Cluster],
        colormap: Optional[Colormap],
        cell_size: int,
        empty_pixmap: Optional[QPixmap] = None,
        target_side: Optional[int] = None,
        physics: Optional[PhysicsConversionManager] = None,
        classifiers_enabled: bool = True,
        min_cell_size_px: int = 0,
    ) -> None:
        """Renders a cluster thumbnail (with optional badges) into this cell.

        Args:
            cluster: Cluster data, or None for an empty cell.
            colormap: Colormap for rendering.
            cell_size: Target side length in pixels.
            empty_pixmap: Pre-rendered pixmap for empty cells.
            target_side: Shared bbox side across all cells in the
                same repaint so small clusters are not upscaled to
                fill the cell, preserving relative spatial scale.
            physics: Conversion manager for the keV badge. Badges
                are skipped when this is None.
            classifiers_enabled: Gate for particle + confidence badges.
                When False, only the keV badge is rendered.
            min_cell_size_px: Suppress *all* badges below this side.
        """
        if cluster is None or cluster.data is None:
            if empty_pixmap is not None:
                self.setPixmap(empty_pixmap)
            else:
                pm = QPixmap(cell_size, cell_size)
                pm.fill(Qt.black)
                self.setPixmap(pm)
            return

        cluster_pm = EnergyClusterWidget.to_pixmap(
            cluster.data, colormap, cell_size, target_side=target_side,
        )

        if physics is not None and cell_size >= min_cell_size_px:
            cluster_pm = self._addBadges(
                cluster_pm, cluster, physics, classifiers_enabled,
            )

        self.setPixmap(cluster_pm)

    # --- Badge composition ---

    def _addBadges(
        self,
        base: QPixmap,
        cluster: Cluster,
        physics: PhysicsConversionManager,
        classifiers_enabled: bool,
    ) -> QPixmap:
        """Composites badges over *base* and returns the new pixmap.

        The keV badge is always drawn. Particle + confidence badges
        are drawn only when ``classifiers_enabled`` is True and the
        cluster's best classifier score is strictly positive.
        """
        particle_type, confidence = classify_particle(
            cluster, CLASSIFICATION_THRESHOLD,
        )
        show_classifier_badges = classifiers_enabled and confidence > 0.0

        overlay = QPixmap(base.size())
        overlay.fill(Qt.transparent)
        painter = QPainter(overlay)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            area = QRect(0, 0, base.width(), base.height())
            if show_classifier_badges:
                self._drawParticleBadge(painter, area, particle_type)
                self._drawConfidenceBadge(painter, area, confidence)
            self._drawEnergyBadge(painter, area, cluster, physics)
        finally:
            painter.end()

        composed = QPixmap(base)
        compositor = QPainter(composed)
        try:
            compositor.drawPixmap(0, 0, overlay)
        finally:
            compositor.end()
        return composed

    @staticmethod
    def _drawBadge(
        painter: QPainter,
        x: int,
        y: int,
        text: str,
        bg: QColor,
        fg: QColor,
    ) -> QRect:
        """Renders a 1 px bordered, rounded-rect badge."""
        painter.setFont(_badge_font())
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 2 * _BADGE_PAD_X
        h = fm.height() + 2 * _BADGE_PAD_Y

        painter.setPen(
            QPen(
                QColor(LiveModeBadgeColors.BORDER),
                LiveModeBadgeColors.BORDER_WIDTH_PX,
            )
        )
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(x, y, w, h, _BADGE_RADIUS, _BADGE_RADIUS)

        painter.setPen(fg)
        painter.drawText(
            x + _BADGE_PAD_X,
            y + _BADGE_PAD_Y + fm.ascent(),
            text,
        )
        return QRect(x, y, w, h)

    def _drawParticleBadge(
        self,
        painter: QPainter,
        area: QRect,
        particle_type: ParticleType,
    ) -> None:
        bg = QColor(particle_type.badge_color)
        self._drawBadge(
            painter,
            area.x() + _BADGE_MARGIN,
            area.y() + _BADGE_MARGIN,
            particle_type.symbol,
            bg,
            _pickBadgeFg(bg),
        )

    def _drawConfidenceBadge(
        self,
        painter: QPainter,
        area: QRect,
        confidence: float,
    ) -> None:
        text = self.tr("{pct:.0f}%").format(pct=confidence * 100)
        if confidence >= CLASSIFICATION_THRESHOLD:
            bg = QColor(LiveModeBadgeColors.CONFIDENCE_HIGH_BG)
        elif confidence >= 0.5:
            bg = QColor(LiveModeBadgeColors.CONFIDENCE_MID_BG)
        else:
            bg = QColor(LiveModeBadgeColors.CONFIDENCE_LOW_BG)

        painter.setFont(_badge_font())
        fm = painter.fontMetrics()
        badge_w = fm.horizontalAdvance(text) + 2 * _BADGE_PAD_X
        self._drawBadge(
            painter,
            area.right() - badge_w - _BADGE_MARGIN,
            area.y() + _BADGE_MARGIN,
            text,
            bg,
            _pickBadgeFg(bg),
        )

    def _drawEnergyBadge(
        self,
        painter: QPainter,
        area: QRect,
        cluster: Cluster,
        physics: PhysicsConversionManager,
    ) -> None:
        kev = float(physics.adu_to_kev(cluster.energy))
        text = self.tr("{kev:.3f} keV").format(kev=kev)

        painter.setFont(_badge_font())
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 2 * _BADGE_PAD_X
        h = fm.height() + 2 * _BADGE_PAD_Y
        x = area.x() + (area.width() - w) // 2
        y = area.bottom() - h - _BADGE_MARGIN
        self._drawBadge(
            painter,
            x,
            y,
            text,
            QColor(LiveModeBadgeColors.ENERGY_BG),
            QColor(LiveModeBadgeColors.ENERGY_FG),
        )
