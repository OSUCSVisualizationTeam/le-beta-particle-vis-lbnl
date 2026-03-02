"""Interactive energy histogram widget backed by pyqtgraph.

Replaces the static ``QLabel`` + matplotlib PNG approach with a
native Qt ``PlotWidget`` that supports hover tooltips.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pyqtgraph as pg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.HistogramDataModel import HistogramDataModel

logger = logging.getLogger(__name__)

_DEFAULT_BAR_COLOR = "#3498db"
_DEFAULT_EDGE_COLOR = "#1a1a2e"
_AXIS_FG = "#222222"
_GRID_ALPHA = 0.25
_PLOT_BG = "#ffffff"
_TOOLTIP_OFFSET_X = 12
_TOOLTIP_OFFSET_Y = -28


class _Style:
    PLACEHOLDER = "color: #999999; font-style: italic; padding: 20px;"
    TOOLTIP = (
        "background-color: rgba(44,62,80,220);"
        "color: #ffffff;"
        "padding: 4px 8px;"
        "border-radius: 3px;"
        "font-size: 11px;"
    )


_SUPERSCRIPTS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _format_value(value: float, bin_width: float) -> str:
    """Format a value with precision adapted to the bin width."""
    if bin_width <= 0:
        return f"{value:.2f}"
    decimals = max(2, -int(np.floor(np.log10(bin_width))) + 1)
    decimals = min(decimals, 10)
    return f"{value:.{decimals}f}"


def _log_tick_label(exp: int) -> str:
    """Convert an integer exponent to a Unicode superscript label.

    Example: ``3`` → ``"10³"``, ``12`` → ``"10¹²"``.
    """
    return f"10{str(exp).translate(_SUPERSCRIPTS)}"


class InteractiveHistogramWidget(QWidget):
    """Reusable energy histogram with hover-to-inspect tooltips.

    Uses ``pyqtgraph.PlotWidget`` + ``BarGraphItem`` for native Qt
    rendering — no background threads needed.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._model: Optional[HistogramDataModel] = None
        self._bar_item: Optional[pg.BarGraphItem] = None
        self._logarithmicBars = False
        self._display_heights: Optional[np.ndarray] = None
        self._initUI()

    # --- Public API ---

    def setData(self, model: Optional[HistogramDataModel]) -> None:
        """Updates the histogram bars from *model*.

        Pass ``None`` to show the placeholder text.
        """
        self._model = model
        if model is None:
            self._showPlaceholder()
            return
        self._showPlot()
        self._updateBars(model)

    def setPlaceholderText(self, text: str) -> None:
        """Configures the message shown when no data is available."""
        self._placeholder.setText(text)

    def setLogarithmicBars(self, useLogScale: bool) -> None:
        """Configures histogram bars to use a logarithmic scale."""
        self._logarithmicBars = useLogScale
        if self._model is not None:
            self._updateBars(self._model)

    # --- UI construction ---

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked layout toggles between placeholder and plot
        self._stack = QStackedLayout()
        layout.addLayout(self._stack)

        # Page 0: placeholder label
        self._placeholder = QLabel(self.tr("Draw an ROI to see energy distribution"))
        self._placeholder.setStyleSheet(_Style.PLACEHOLDER)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self._stack.addWidget(self._placeholder)

        # Page 1: pyqtgraph plot
        self._plot = pg.PlotWidget()
        self._plot.setBackground(_PLOT_BG)
        self._plot.showGrid(x=False, y=True, alpha=_GRID_ALPHA)
        self._plot.setLabel("left", "Count", color=_AXIS_FG)

        for axis_name in ("left", "bottom"):
            axis = self._plot.getAxis(axis_name)
            axis.setPen(pg.mkPen(_AXIS_FG, width=1))
            axis.setTextPen(pg.mkPen(_AXIS_FG))
            axis.setTickPen(pg.mkPen(_AXIS_FG, width=1))
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideButtons()
        self._stack.addWidget(self._plot)

        # Hover tooltip overlay
        self._tooltip = QLabel(self._plot)
        self._tooltip.setStyleSheet(_Style.TOOLTIP)
        self._tooltip.setVisible(False)
        self._tooltip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Rate-limited mouse tracking
        self._proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self._onMouseMoved,
        )

        self._stack.setCurrentIndex(0)

    # --- Plot updates ---

    def _updateBars(self, model: HistogramDataModel) -> None:
        """Clears the plot and draws new bars from *model*."""
        plot_item = self._plot.getPlotItem()
        plot_item.setLogMode(x=False, y=False)
        if self._bar_item is not None:
            plot_item.removeItem(self._bar_item)
            self._bar_item = None

        counts = model.counts
        if self._logarithmicBars:
            display_heights = np.where(
                counts > 0, np.log10(counts.astype(float)), 0.0,
            )
        else:
            display_heights = counts.astype(float)
        self._display_heights = display_heights

        brushes = self._buildBrushes(model)
        self._bar_item = pg.BarGraphItem(
            x=model.bin_centers,
            width=model.bin_widths * 0.95,
            height=display_heights,
            brushes=brushes,
            pen=pg.mkPen(_DEFAULT_EDGE_COLOR, width=0.8),
        )
        plot_item.addItem(self._bar_item)
        self._plot.setLabel("bottom", model.x_label, color=_AXIS_FG)

        y_axis = plot_item.getAxis("left")
        if self._logarithmicBars:
            max_exp = int(np.ceil(display_heights.max())) if display_heights.max() > 0 else 1
            ticks = [
                [(i, _log_tick_label(i)) for i in range(max_exp + 1)]
            ]
            y_axis.setTicks(ticks)
            self._plot.setLabel("left", "Count (log\u2081\u2080)", color=_AXIS_FG)
        else:
            y_axis.setTicks(None)
            self._plot.setLabel("left", "Count", color=_AXIS_FG)

    @staticmethod
    def _buildBrushes(
        model: HistogramDataModel,
    ) -> list:
        """Returns a per-bar brush list, optionally colormap-mapped."""
        if model.colormap is None:
            brush = pg.mkBrush(_DEFAULT_BAR_COLOR)
            return [brush] * len(model.counts)

        try:
            cmap = pg.colormap.get(
                model.colormap,
                source="matplotlib",
            )
        except Exception:
            logger.warning(
                "Colormap %r not found, using default",
                model.colormap,
            )
            brush = pg.mkBrush(_DEFAULT_BAR_COLOR)
            return [brush] * len(model.counts)

        centers = model.bin_centers
        lo, hi = float(centers.min()), float(centers.max())
        if hi <= lo:
            brush = pg.mkBrush(_DEFAULT_BAR_COLOR)
            return [brush] * len(model.counts)

        normed = (centers - lo) / (hi - lo)
        colors = cmap.mapToQColor(normed)
        return [pg.mkBrush(c) for c in colors]

    # --- Hover tooltip ---

    def _onMouseMoved(self, args: tuple) -> None:
        """Resolves the hovered bin and shows a tooltip."""
        if self._model is None or self._bar_item is None:
            self._tooltip.setVisible(False)
            return

        pos = args[0]
        vb = self._plot.getPlotItem().vb
        mouse_point = vb.mapSceneToView(pos)
        x_val = mouse_point.x()
        y_val = mouse_point.y()

        edges = self._model.bin_edges
        idx = int(np.searchsorted(edges, x_val)) - 1
        if idx < 0 or idx >= len(self._model.counts):
            self._tooltip.setVisible(False)
            return

        count = self._model.counts[idx]
        bar_top = (
            self._display_heights[idx]
            if self._display_heights is not None
            else count
        )
        if y_val < 0 or y_val > bar_top:
            self._tooltip.setVisible(False)
            return

        lo_edge = edges[idx]
        hi_edge = edges[idx + 1]
        bin_w = hi_edge - lo_edge
        unit_suffix = f" {self._model.x_unit}" if self._model.x_unit else ""
        self._tooltip.setText(
            f"Count: {count}\n"
            f"Range: {_format_value(lo_edge, bin_w)} \u2013 "
            f"{_format_value(hi_edge, bin_w)}{unit_suffix}"
        )
        self._tooltip.adjustSize()

        # Position tooltip near cursor in widget coordinates
        scene_pos = self._plot.mapFromScene(pos)
        tx = int(scene_pos.x()) + _TOOLTIP_OFFSET_X
        ty = int(scene_pos.y()) + _TOOLTIP_OFFSET_Y
        # Clamp inside widget bounds
        tx = max(0, min(tx, self._plot.width() - self._tooltip.width()))
        ty = max(0, min(ty, self._plot.height() - self._tooltip.height()))
        self._tooltip.move(tx, ty)
        self._tooltip.setVisible(True)

    # --- Visibility toggling ---

    def _showPlaceholder(self) -> None:
        """Switches the stacked layout to the placeholder."""
        self._tooltip.setVisible(False)
        if self._bar_item is not None:
            self._plot.getPlotItem().removeItem(self._bar_item)
            self._bar_item = None
        self._stack.setCurrentIndex(0)

    def _showPlot(self) -> None:
        """Switches the stacked layout to the plot widget."""
        self._stack.setCurrentIndex(1)
