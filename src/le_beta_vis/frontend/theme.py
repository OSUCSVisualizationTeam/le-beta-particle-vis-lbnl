# Centralized dark-theme color constants.
#
# Deep dark — cell/item backgrounds, placeholder fills
COLOR_BACKGROUND_DEEP = "#1e1e1e"

# Surface dark — panels, toolbars, container backgrounds
COLOR_BACKGROUND_SURFACE = "#2d2d2d"

# Primary foreground text
COLOR_TEXT_PRIMARY = "#eeeeee"

# Clickable links on dark background
COLOR_ACCENT_LINK = "#4fc3f7"


class ProgressOverlayColors:
    """Colors for ProgressOverlay and its subclasses."""

    DIM_RGBA = (0, 0, 0, 80)
    CARD_BACKGROUND = "rgba(255, 255, 255, 64)"
    CARD_TEXT = "#000000"
    PROGRESS_BACKGROUND = "rgba(0, 0, 0, 40)"
    PROGRESS_CHUNK = "#3daee9"
    ACTION_BUTTON_BACKGROUND = "rgba(0, 0, 0, 180)"


class EventGridSectionHeaderColors:
    """Colors for EventGridSectionHeaderWidget."""

    BACKGROUND = "#000000"
    TEXT = "#bbbbbb"
    TEXT_FILENAME = "#999999"
    NAV_TEXT = "#888888"
    NAV_TEXT_DISABLED = "#555555"
    NAV_HOVER_BACKGROUND = "#4a4a4a"


class LiveModeColors:
    """Colors for the Live Mode screensaver."""

    BACKGROUND = "#000000"
    PANEL_LEFT = "#0d0d0d"
    GRADIENT_LABEL = "#ffffff"
    STATS_BACKGROUND = "#0a1628"
    STATS_TEXT = "#e0f0ff"
    HISTOGRAM_BACKGROUND = "#1a0a0a"
    HISTOGRAM_BG_DARK = "#111111"
    HISTOGRAM_FG_DARK = "#dddddd"
    TITLE_TEXT = "#ffffff"


class MainWindowStatusBarColors:
    """Colors for the global MainWindow QStatusBar."""

    TEXT_INFO = "#d0d0d0"
    TEXT_WARNING = "#f0b000"
    TEXT_ERROR = "#ff5a5a"
    PROGRESS_LABEL = "#bbbbbb"
    PROGRESS_CHUNK = "#3daee9"
    PROGRESS_BACKGROUND = "rgba(0, 0, 0, 40)"


class ExportButtonColors:
    """Colors for the Historical filter bar Save/Cancel toggle button (#56).

    Material-spec shades chosen for WCAG-AA contrast with white foreground
    (SAVE: ~6.5:1, CANCEL: ~6.4:1). Do not reuse the lighter
    ParticleType.TRITIUM badge green (#2ecc71) — it fails contrast on
    white text.
    """

    SAVE_BACKGROUND = "#2E7D32"
    SAVE_FOREGROUND = "#FFFFFF"
    CANCEL_BACKGROUND = "#C62828"
    CANCEL_FOREGROUND = "#FFFFFF"


class TooltipStyle:
    """Shared QToolTip stylesheet snippets.

    ``BODY`` is the property body — usable inside a ``QToolTip { ... }``
    rule embedded in a widget stylesheet, or inside an HTML
    ``<span style='...'>`` wrapper for ``QToolTip.showText`` calls.
    ``QSS`` is the convenience full rule for embedding directly into
    a widget stylesheet.

    ``font-weight: normal`` defeats inheritance from any bold parent
    widget so tooltips render with a consistent weight regardless of
    where they are anchored.
    """

    BODY = (
        "color: black; background-color: white; padding: 2px;"
        " border: 1px solid #ccc; font-weight: normal;"
    )
    QSS = f"QToolTip {{ {BODY} }}"
