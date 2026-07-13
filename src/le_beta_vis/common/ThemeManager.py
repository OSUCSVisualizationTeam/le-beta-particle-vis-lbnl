from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional


class ColorScheme(Enum):
    LIGHT = "light"
    DARK = "dark"
    UNKNOWN = "unknown"


def detect_system_color_scheme() -> ColorScheme:
    """Query the live OS color scheme via Qt's platform theme integration.

    Requires a constructed QApplication/QGuiApplication. ThemeManager
    isolates this call behind an injectable provider so the rest of its
    logic is unit-testable without a live application instance.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    scheme = QGuiApplication.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return ColorScheme.DARK
    if scheme == Qt.ColorScheme.Light:
        return ColorScheme.LIGHT
    return ColorScheme.UNKNOWN


class ThemeManager:
    """Resolves and loads the QSS stylesheet for the current color scheme.

    ``color_scheme_provider`` defaults to the live OS probe but is
    injectable so tests can supply a fake and exercise resolution/loading
    logic without a QApplication. ``override`` takes precedence over
    detection entirely.
    """

    def __init__(
        self,
        color_scheme_provider: Optional[Callable[[], ColorScheme]] = None,
        override: Optional[ColorScheme] = None,
    ) -> None:
        self._color_scheme_provider = (
            color_scheme_provider or detect_system_color_scheme
        )
        self._override = override

    def resolve_color_scheme(self) -> ColorScheme:
        """Return the effective color scheme (override wins over detection)."""
        if self._override is not None:
            return self._override
        try:
            scheme = self._color_scheme_provider()
        except Exception:
            return ColorScheme.DARK
        return scheme if scheme != ColorScheme.UNKNOWN else ColorScheme.DARK

    def stylesheet_paths(self, qss_dir: Path) -> List[Path]:
        """Ordered list of QSS files to concatenate for the effective theme."""
        theme_dir = (
            "light" if self.resolve_color_scheme() == ColorScheme.LIGHT else "dark"
        )
        scheme_files = sorted((qss_dir / theme_dir).glob("*.qss"))
        return [qss_dir / "base.qss", *scheme_files]

    def load_stylesheet(self, qss_dir: Path) -> str:
        """Read and concatenate the resolved QSS files into one sheet string."""
        parts = [
            path.read_text(encoding="utf-8")
            for path in self.stylesheet_paths(qss_dir)
            if path.exists()
        ]
        return "\n".join(parts)
