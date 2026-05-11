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


class ExportOptionsDialogColors:
    """Colors for ExportOptionsDialog (cluster card export options)."""

    BACKGROUND = "#2d2d2d"
    TEXT_NOTE = "#aaaaaa"
    RADIO_FOREGROUND = "#eeeeee"
    EXPORT_BUTTON_BACKGROUND = "#0078d7"
    EXPORT_BUTTON_FOREGROUND = "#ffffff"
    EXPORT_BUTTON_HOVER = "#005fa3"
    CANCEL_BUTTON_BACKGROUND = "#3d3d3d"
    CANCEL_BUTTON_FOREGROUND = "#cccccc"
    CANCEL_BUTTON_BORDER = "#555555"
    CANCEL_BUTTON_HOVER = "#505050"


class HUDAnnotationOverlayColors:
    """Colors for AnnotationOverlay rectangles on HDUVisualizationHUDWidget."""

    BORDER = "#FFFF00"


class RawDataManipulationToolbarColors:
    """Colors for RawDataManipulationToolbar."""

    HDU_LABEL = "#aaaaaa"


class MosaicThumbnailColors:
    """Colors for ThumbnailButton paintEvent overlay."""

    LABEL_TEXT = "#ffffff"
    LABEL_TEXT_SELECTED = "#4fc3f7"
    LABEL_BACKGROUND_RGBA = (0, 0, 0, 140)


class RawClusterLabelingDialogColors:
    """Colors for the raw-data cluster labeling / training export dialog."""

    CALLOUT_BACKGROUND = "#1a3a1a"
    CALLOUT_BORDER = "#2e7d32"
    CALLOUT_TEXT = "#c8e6c9"
    SUBMIT_BUTTON_BACKGROUND = "#0078d7"
    SUBMIT_BUTTON_FOREGROUND = "#ffffff"
    SUBMIT_BUTTON_HOVER = "#005fa3"
    CANCEL_BUTTON_BACKGROUND = "#3d3d3d"
    CANCEL_BUTTON_FOREGROUND = "#cccccc"
    CANCEL_BUTTON_BORDER = "#555555"
    RESULT_TEXT = "#c8e6c9"


class ClusteredEventWidgetColors:
    BUTTON_DISABLED_TEXT = "#a0a0a0"


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


class FilterPipelinePanelColors:
    """Colors for the Interactive Filter Stack UI in the right sidebar."""

    PANEL_BACKGROUND = "#F9F9F9"
    PANEL_BORDER = "#CCCCCC"
    SCROLL_AREA_BACKGROUND = "#D9D9D9"
    CARD_HEADER_BACKGROUND = "#2F2F2F"
    CARD_BODY_BACKGROUND = "#FFFFFF"
    PARAMETER_PILL_BACKGROUND = "#D9D9D9"
    PARAMETER_PILL_HOVER_BACKGROUND = "#C0C0C0"
    PARAMETER_PILL_BORDER = "#B8B8B8"
    PARAMETER_PILL_TEXT_ENABLED = "#1A1A1A"
    PARAMETER_PILL_TEXT_DISABLED = "#9A9A9A"
    FILTER_NAME_ENABLED = "#E8E8E8"
    FILTER_NAME_DISABLED = "#686868"
    GRABBER_ENABLED = "#AAAAAA"
    GRABBER_DISABLED = "#585858"
    DELETE_ICON = "#E55353"
    TOGGLE_ON = "#14AE5C"
    TOGGLE_OFF = "#BBBBBB"
    ADD_FILTER_BUTTON_BACKGROUND = "#99B1E9"
    COUNTER_TEXT = "#757575"
    TITLE_TEXT = "#000000"

    POPOVER_BACKGROUND = "#2A2A2A"
    POPOVER_BORDER = "#4A4A4A"
    POPOVER_HEADER_TEXT = "#E8E8E8"
    POPOVER_CONTROL_BACKGROUND = "#3A3A3A"
    POPOVER_CONTROL_FOREGROUND = "#E0E0E0"

    ADD_FILTER_MENU_BACKGROUND = "#2A2A2A"
    ADD_FILTER_MENU_TEXT = "#E8E8E8"
    ADD_FILTER_MENU_HOVER = "#3A3A3A"
    ADD_FILTER_MENU_DISABLED_TEXT = "#666666"
    ADD_FILTER_MENU_BORDER = "#4A4A4A"

    PILL_TOOLTIP_BACKGROUND = "#FFFFCC"
    PILL_TOOLTIP_TEXT = "#000000"
    PILL_TOOLTIP_BORDER = "#CCCCAA"
