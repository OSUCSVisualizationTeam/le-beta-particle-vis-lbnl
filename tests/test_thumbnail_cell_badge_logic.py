"""WCAG contrast tests for the Live Mode badge foreground picker.

The helper is pure-Python (operates on integer RGB channels via
``QColor``) and does not require a ``QApplication``, so it stays
CI-safe.
"""

from PySide6.QtGui import QColor

from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.frontend.livemode.widgets._ThumbnailCell import (
    _pickBadgeFg,
)
from le_beta_vis.frontend.theme import LiveModeBadgeColors


def _luminance(color: QColor) -> float:
    def _ch(c: int) -> float:
        s = c / 255.0
        if s <= 0.03928:
            return s / 12.92
        return ((s + 0.055) / 1.055) ** 2.4
    return (
        0.2126 * _ch(color.red())
        + 0.7152 * _ch(color.green())
        + 0.0722 * _ch(color.blue())
    )


def _contrast(a: QColor, b: QColor) -> float:
    la = _luminance(a)
    lb = _luminance(b)
    lighter, darker = (la, lb) if la >= lb else (lb, la)
    return (lighter + 0.05) / (darker + 0.05)


class TestPickBadgeFg:
    def test_returns_dark_text_on_bright_background(self) -> None:
        assert _pickBadgeFg(QColor("#2ecc71")) == QColor(
            LiveModeBadgeColors.TEXT_DARK,
        )

    def test_returns_light_text_on_dark_background(self) -> None:
        assert _pickBadgeFg(QColor("#0d0d0d")) == QColor(
            LiveModeBadgeColors.TEXT_LIGHT,
        )

    def test_returns_light_text_on_deep_navy(self) -> None:
        assert _pickBadgeFg(QColor(LiveModeBadgeColors.ENERGY_BG)) == QColor(
            LiveModeBadgeColors.TEXT_LIGHT,
        )


class TestParticleBadgeContrast:
    """Every ParticleType badge color must clear WCAG AA (>= 4.5:1)."""

    def test_all_particle_badges_meet_aa(self) -> None:
        for pt in ParticleType:
            bg = QColor(pt.badge_color)
            fg = _pickBadgeFg(bg)
            ratio = _contrast(bg, fg)
            assert ratio >= 4.5, (
                f"{pt.name} badge {pt.badge_color} contrast "
                f"{ratio:.2f}:1 < 4.5:1"
            )


class TestConfidencePaletteContrast:
    def test_high_confidence_bg_meets_aa(self) -> None:
        bg = QColor(LiveModeBadgeColors.CONFIDENCE_HIGH_BG)
        assert _contrast(bg, _pickBadgeFg(bg)) >= 4.5

    def test_mid_confidence_bg_meets_aa(self) -> None:
        bg = QColor(LiveModeBadgeColors.CONFIDENCE_MID_BG)
        assert _contrast(bg, _pickBadgeFg(bg)) >= 4.5

    def test_low_confidence_bg_meets_aa(self) -> None:
        bg = QColor(LiveModeBadgeColors.CONFIDENCE_LOW_BG)
        assert _contrast(bg, _pickBadgeFg(bg)) >= 4.5


class TestEnergyBadgeContrast:
    def test_energy_bg_fg_meets_aa(self) -> None:
        bg = QColor(LiveModeBadgeColors.ENERGY_BG)
        fg = QColor(LiveModeBadgeColors.ENERGY_FG)
        assert _contrast(bg, fg) >= 4.5
