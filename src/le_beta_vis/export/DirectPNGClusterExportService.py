"""Direct-to-PNG cluster card renderer.

Produces the same visual artefact as the previous matplotlib-based
renderer — plot panel, colorbar, metadata panel, title — but without
ever creating a matplotlib Figure or Axes. Rendering is pure
``numpy`` + ``Pillow``, which is several times faster per card and
safe to call from any thread (no GIL-heavy figure construction and
no GUI backend).

Colormap LUTs are built once per ``Colormap`` value via
``cv2.applyColorMap`` on a 0-255 ramp, and the DejaVu fonts used for
axis/metadata text are loaded from ``export/fonts/`` (bundled with the
package). No matplotlib imports live in this module or its call chain.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..common.Cluster import Cluster
from ..common.ColormapLUT import colormap_lut as _colormap_lut  # noqa: F401 — re-export
from ..common.Colormap import Colormap
from .ClusterExportService import (
    ClusterExportContext,
    ClusterExportMetadata,
    ClusterExportService,
    ClusterMetadataLabels,
)


logger = logging.getLogger(__name__)


# Canvas geometry. Matches the previous 10"x5" @ 120 dpi figure.
_CANVAS_W = 1200
_CANVAS_H = 600
_BG_COLOR = (255, 255, 255)

# Plot panel (the pcolormesh-equivalent area).
_PLOT_X0, _PLOT_Y0 = 95, 70
_PLOT_X1, _PLOT_Y1 = 760, 520

# Colorbar strip + its tick / label columns.
_CBAR_X0, _CBAR_Y0 = 790, 70
_CBAR_X1, _CBAR_Y1 = 815, 520
_CBAR_TICK_X = 820
_CBAR_LABEL_X = 895

# Metadata panel.
_META_X0, _META_Y0 = 940, 70
_META_X1, _META_Y1 = 1180, 520
_META_PAD = 10

_AXIS_COLOR = (0, 0, 0)
_GRID_COLOR = (220, 220, 220)
_METADATA_BOX_FILL = (244, 244, 244)
_METADATA_BOX_EDGE = (176, 176, 176)

_TITLE_FONT_SIZE = 14
_LABEL_FONT_SIZE = 11
_TICK_FONT_SIZE = 9
_META_FONT_SIZE = 10

# Path to the bundled font directory (shipped via package-data).
_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_SANS = "DejaVuSans.ttf"
_FONT_SANS_MONO = "DejaVuSansMono.ttf"


class DirectPNGClusterExportService(ClusterExportService):
    """Pillow-backed PNG renderer for single-cluster export."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Pass an optional logger for log-chain propagation from the orchestrator."""
        super().__init__(logger=logger)

    def export(
        self,
        cluster: Cluster,
        out_path: Path,
        *,
        context: ClusterExportContext,
        colormap: Colormap,
    ) -> None:
        """Render ``cluster`` pixel data and metadata to a PNG file at ``out_path``."""
        data_kev = self._compute_kev_array(cluster, context)
        lut = _colormap_lut(colormap)
        metadata = self.build_metadata(cluster, context)
        vmin, vmax = _value_range(data_kev)

        canvas = Image.new("RGB", (_CANVAS_W, _CANVAS_H), _BG_COLOR)
        draw = ImageDraw.Draw(canvas)

        self._render_title(draw, cluster)
        self._render_plot_panel(
            canvas, draw, cluster, data_kev, lut, context.labels, vmin, vmax
        )
        self._render_colorbar(canvas, draw, lut, context.labels, vmin, vmax)
        self._render_metadata_panel(canvas, metadata, context.labels)
        self._save_png(canvas, out_path, cluster)

    def render_metadata(
        self,
        canvas: Any,
        metadata: ClusterExportMetadata,
        labels: ClusterMetadataLabels,
    ) -> None:
        """Paint the metadata panel onto a pre-allocated Pillow canvas.

        ``canvas`` must be an ``Image.Image`` sized to the standard
        export layout; the panel is drawn at the fixed bounding box
        used by ``export()``.
        """
        draw = ImageDraw.Draw(canvas)
        self._draw_metadata_box(draw)
        lines = _format_metadata(metadata, labels)
        self._draw_metadata_text(draw, lines)

    @staticmethod
    def _compute_kev_array(
        cluster: Cluster, context: ClusterExportContext
    ) -> np.ndarray:
        data = np.asarray(cluster.data, dtype=np.float64)
        return np.asarray(context.physics.adu_to_kev(data), dtype=np.float64)

    def _render_title(self, draw: ImageDraw.ImageDraw, cluster: Cluster) -> None:
        font = _load_font(_TITLE_FONT_SIZE, monospace=False)
        text = _title(cluster)
        x = (_PLOT_X0 + _PLOT_X1) // 2
        y = 20
        _draw_text_centered(draw, (x, y), text, font, _AXIS_COLOR)

    def _render_plot_panel(
        self,
        canvas: Image.Image,
        draw: ImageDraw.ImageDraw,
        cluster: Cluster,
        data_kev: np.ndarray,
        lut: np.ndarray,
        labels: ClusterMetadataLabels,
        vmin: float,
        vmax: float,
    ) -> None:
        self._paste_heatmap(canvas, data_kev, lut, vmin, vmax)
        self._draw_plot_border(draw)
        self._draw_axis_ticks(draw, cluster)
        self._draw_axis_labels(draw, labels)

    @staticmethod
    def _paste_heatmap(
        canvas: Image.Image,
        data_kev: np.ndarray,
        lut: np.ndarray,
        vmin: float,
        vmax: float,
    ) -> None:
        """Normalize ``data_kev`` to uint8 LUT indices, apply the colormap, and paste the
        resulting RGB image into the plot area. Uses ``NEAREST`` resampling to preserve
        per-pixel values without interpolation artifacts on small cluster footprints.
        """
        indices = _normalize_to_indices(data_kev, vmin, vmax)
        rgb = lut[indices]  # (H, W, 3) uint8
        # Pillow coords: origin top-left, matching numpy row-major layout.
        heat = Image.fromarray(rgb, mode="RGB")
        width = _PLOT_X1 - _PLOT_X0
        height = _PLOT_Y1 - _PLOT_Y0
        heat = heat.resize((width, height), resample=Image.NEAREST)
        canvas.paste(heat, (_PLOT_X0, _PLOT_Y0))

    @staticmethod
    def _draw_plot_border(draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle(
            [(_PLOT_X0, _PLOT_Y0), (_PLOT_X1, _PLOT_Y1)],
            outline=_AXIS_COLOR,
            width=1,
        )

    def _draw_axis_ticks(self, draw: ImageDraw.ImageDraw, cluster: Cluster) -> None:
        """Draw X and Y axis ticks using the cluster bounding-box coordinates as the world-space range mapped to plot-area '
        pixels."""
        font = _load_font(_TICK_FONT_SIZE, monospace=False)
        rows, cols = np.asarray(cluster.data).shape
        x_min = cluster.boundingBox.left
        x_max = cluster.boundingBox.left + cols
        y_min = cluster.boundingBox.top
        y_max = cluster.boundingBox.top + rows

        for value, px in _tick_positions(x_min, x_max, _PLOT_X0, _PLOT_X1):
            draw.line([(px, _PLOT_Y1), (px, _PLOT_Y1 + 4)], fill=_AXIS_COLOR)
            _draw_text_centered(
                draw, (px, _PLOT_Y1 + 12), str(value), font, _AXIS_COLOR
            )
        for value, py in _tick_positions(y_min, y_max, _PLOT_Y0, _PLOT_Y1):
            draw.line([(_PLOT_X0 - 4, py), (_PLOT_X0, py)], fill=_AXIS_COLOR)
            _draw_text_right_aligned(
                draw, (_PLOT_X0 - 6, py), str(value), font, _AXIS_COLOR
            )

    @staticmethod
    def _draw_axis_labels(
        draw: ImageDraw.ImageDraw, labels: ClusterMetadataLabels
    ) -> None:
        font = _load_font(_LABEL_FONT_SIZE, monospace=False)
        x_label_pos = ((_PLOT_X0 + _PLOT_X1) // 2, _PLOT_Y1 + 34)
        _draw_text_centered(draw, x_label_pos, labels.x_axis, font, _AXIS_COLOR)
        _draw_vertical_text(
            draw,
            (_PLOT_X0 - 46, (_PLOT_Y0 + _PLOT_Y1) // 2),
            labels.y_axis,
            font,
            _AXIS_COLOR,
        )

    def _render_colorbar(
        self,
        canvas: Image.Image,
        draw: ImageDraw.ImageDraw,
        lut: np.ndarray,
        labels: ClusterMetadataLabels,
        vmin: float,
        vmax: float,
    ) -> None:
        self._paste_colorbar_strip(canvas, lut)
        self._draw_colorbar_border(draw)
        self._draw_colorbar_ticks(draw, vmin, vmax)
        self._draw_colorbar_label(draw, labels.colorbar)

    @staticmethod
    def _paste_colorbar_strip(canvas: Image.Image, lut: np.ndarray) -> None:
        """Paste the colormap gradient into the colorbar area. The LUT is reversed so LUT index 0 (vmin) appears at the bottom
        and index 255 (vmax) at the top, matching the conventional low-to-high colorbar orientation.
        """
        # Bottom → top: LUT index 0 at vmin, 255 at vmax.
        column = lut[::-1].reshape(256, 1, 3)
        strip = Image.fromarray(column, mode="RGB")
        width = _CBAR_X1 - _CBAR_X0
        height = _CBAR_Y1 - _CBAR_Y0
        strip = strip.resize((width, height), resample=Image.BILINEAR)
        canvas.paste(strip, (_CBAR_X0, _CBAR_Y0))

    @staticmethod
    def _draw_colorbar_border(draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle(
            [(_CBAR_X0, _CBAR_Y0), (_CBAR_X1, _CBAR_Y1)],
            outline=_AXIS_COLOR,
            width=1,
        )

    def _draw_colorbar_ticks(
        self, draw: ImageDraw.ImageDraw, vmin: float, vmax: float
    ) -> None:
        """Draw 5 evenly spaced ticks on the right edge of the colorbar, mapping each keV value to its fractional pixel
        position within the colorbar height."""
        font = _load_font(_TICK_FONT_SIZE, monospace=False)
        ticks = _linear_ticks(vmin, vmax, count=5)
        height = _CBAR_Y1 - _CBAR_Y0
        span = vmax - vmin if vmax > vmin else 1.0
        for value in ticks:
            frac = (value - vmin) / span
            py = int(round(_CBAR_Y1 - frac * height))
            draw.line([(_CBAR_X1, py), (_CBAR_X1 + 4, py)], fill=_AXIS_COLOR)
            _draw_text_left_aligned(
                draw,
                (_CBAR_TICK_X + 2, py),
                _format_tick(value),
                font,
                _AXIS_COLOR,
            )

    @staticmethod
    def _draw_colorbar_label(draw: ImageDraw.ImageDraw, text: str) -> None:
        font = _load_font(_LABEL_FONT_SIZE, monospace=False)
        _draw_vertical_text(
            draw,
            (_CBAR_LABEL_X, (_CBAR_Y0 + _CBAR_Y1) // 2),
            text,
            font,
            _AXIS_COLOR,
        )

    def _render_metadata_panel(
        self,
        canvas: Image.Image,
        metadata: ClusterExportMetadata,
        labels: ClusterMetadataLabels,
    ) -> None:
        self.render_metadata(canvas, metadata, labels)

    @staticmethod
    def _draw_metadata_box(draw: ImageDraw.ImageDraw) -> None:
        draw.rounded_rectangle(
            [(_META_X0, _META_Y0), (_META_X1, _META_Y1)],
            radius=8,
            fill=_METADATA_BOX_FILL,
            outline=_METADATA_BOX_EDGE,
            width=1,
        )

    @staticmethod
    def _draw_metadata_text(draw: ImageDraw.ImageDraw, lines: List[str]) -> None:
        font = _load_font(_META_FONT_SIZE, monospace=True)
        text = "\n".join(lines)
        draw.multiline_text(
            (_META_X0 + _META_PAD, _META_Y0 + _META_PAD),
            text,
            fill=_AXIS_COLOR,
            font=font,
            spacing=4,
        )

    def _save_png(self, canvas: Image.Image, out_path: Path, cluster: Cluster) -> None:
        try:
            canvas.save(out_path, format="PNG", optimize=False)
        except Exception:
            self._logger.exception("Failed to save cluster PNG to %s", out_path)
            raise
        self._logger.debug("Exported cluster %s → %s", cluster.clusterId, out_path)


# --- module-level helpers ---------------------------------------------------


@lru_cache(maxsize=8)
def _load_font(size: int, monospace: bool) -> ImageFont.ImageFont:
    """Load a bundled DejaVu TTF; fall back to PIL's default on packaging failures."""
    filename = _FONT_SANS_MONO if monospace else _FONT_SANS
    path = _FONT_DIR / filename
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        logger.warning(
            "Bundled font %s not found at %s; falling back to PIL default. "
            "This usually indicates a packaging regression.",
            filename,
            path,
        )
        return ImageFont.load_default()


def _value_range(data_kev: np.ndarray) -> Tuple[float, float]:
    """Return ``(vmin, vmax)`` for ``data_kev``. Handles empty arrays, non-finite values, and the degenerate case where
    ``vmax <= vmin`` by adding a 1.0 span."""
    if data_kev.size == 0:
        return 0.0, 1.0
    vmin = float(np.nanmin(data_kev))
    vmax = float(np.nanmax(data_kev))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return vmin, vmin + 1.0
    return vmin, vmax


def _normalize_to_indices(data_kev: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    """Clip-normalize ``data_kev`` to ``[vmin, vmax]`` and return uint8 LUT indices in ``[0, 255]`` using rounding to avoid
    systematic bias at the boundaries."""
    span = vmax - vmin if vmax > vmin else 1.0
    normalized = np.clip((data_kev - vmin) / span, 0.0, 1.0)
    return (normalized * 255.0 + 0.5).astype(np.uint8)


def _tick_positions(
    value_min: int, value_max: int, pixel_min: int, pixel_max: int
) -> List[Tuple[int, int]]:
    """Return ``(value, pixel)`` pairs for ~5 evenly spaced axis ticks."""
    span_value = max(1, value_max - value_min)
    span_pixels = pixel_max - pixel_min
    target = min(5, span_value + 1)
    step = max(1, span_value // max(1, target - 1))
    out: List[Tuple[int, int]] = []
    v = value_min
    while v <= value_max:
        frac = (v - value_min) / span_value
        px = int(round(pixel_min + frac * span_pixels))
        out.append((v, px))
        v += step
    if out and out[-1][0] != value_max:
        frac = 1.0
        out.append((value_max, pixel_min + int(round(frac * span_pixels))))
    return out


def _linear_ticks(vmin: float, vmax: float, count: int) -> List[float]:
    if count < 2:
        return [vmin, vmax]
    step = (vmax - vmin) / (count - 1)
    return [vmin + i * step for i in range(count)]


def _format_tick(value: float) -> str:
    """
    Format a tick value as scientific notation when ``|value| >= 1000`` or ``|value| < 0.01``, otherwise as two-decimal fixed.
    """
    if abs(value) >= 1000 or (value != 0 and abs(value) < 0.01):
        return f"{value:.2e}"
    return f"{value:.2f}"


def _title(cluster: Cluster) -> str:
    cid = cluster.clusterId if cluster.clusterId is not None else "-"
    return f"Cluster Id: {cid}"


def _format_metadata(
    metadata: ClusterExportMetadata, labels: ClusterMetadataLabels
) -> List[str]:
    peak_x, peak_y = metadata.peak_xy_absolute
    lines = [
        f"{labels.energy}: {metadata.total_energy_kev:.2f} {labels.kev_unit}",
        f"{labels.pixels}: {metadata.pixel_count}",
        "",
        f"{labels.sigma_x}: {metadata.sigma_x:.1f}",
        f"{labels.sigma_y}: {metadata.sigma_y:.1f}",
        f"{labels.full_width_x}: {metadata.full_width_x}",
        f"{labels.full_width_y}: {metadata.full_width_y}",
        (
            f"{labels.energy_per_pixel}: "
            f"{metadata.energy_per_pixel_kev:.2f} {labels.kev_unit}"
        ),
        f"{labels.peak_xy}: ({peak_x}, {peak_y})",
    ]
    if metadata.selection_summary:
        lines.append("")
        lines.append(f"{labels.selection}:")
        lines.append(metadata.selection_summary)
    return lines


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    anchor: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
) -> None:
    draw.text(anchor, text, fill=fill, font=font, anchor="mm")


def _draw_text_left_aligned(
    draw: ImageDraw.ImageDraw,
    anchor: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
) -> None:
    draw.text(anchor, text, fill=fill, font=font, anchor="lm")


def _draw_text_right_aligned(
    draw: ImageDraw.ImageDraw,
    anchor: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
) -> None:
    draw.text(anchor, text, fill=fill, font=font, anchor="rm")


def _draw_vertical_text(
    draw: ImageDraw.ImageDraw,
    anchor: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
) -> None:
    """Paint vertically-oriented text centred on ``anchor`` (reads bottom-to-top)."""
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad = 2
    strip_w = text_w + pad * 2
    strip_h = text_h + pad * 2
    strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
    strip_draw = ImageDraw.Draw(strip)
    strip_draw.text((pad - bbox[0], pad - bbox[1]), text, fill=fill, font=font)
    rotated = strip.rotate(90, expand=True)
    cx, cy = anchor
    dest = (cx - rotated.width // 2, cy - rotated.height // 2)
    target: Image.Image = draw._image  # type: ignore[attr-defined]
    target.paste(rotated, dest, rotated)
