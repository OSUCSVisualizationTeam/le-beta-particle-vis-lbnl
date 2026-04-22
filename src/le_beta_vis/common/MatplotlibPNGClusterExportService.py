"""Matplotlib-backed PNG renderer for single-cluster export (issue #56).

Renders a figure matching the reference layout:
  * Left panel: pcolormesh of the cluster data in ABSOLUTE HDU
    coordinates (the bounding box carries the offset).
  * Colorbar: configurable label (``labels.colorbar``), values via
    ``PhysicsConversionManager.adu_to_kev``.
  * Right panel: metadata (Energy, Num. pixels, σx/σy, Full width,
    Energy per pixel, Peak xy, Selection summary). Cluster id lives in
    the title, not the metadata panel.

Uses the 'Agg' backend so it is safe to call from a worker thread —
no Qt, no display server.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Tuple

import matplotlib

matplotlib.use("Agg", force=False)

import numpy as np  # noqa: E402

from .Cluster import Cluster  # noqa: E402
from .ClusterExportService import (  # noqa: E402
    ClusterExportContext,
    ClusterExportMetadata,
    ClusterExportService,
    ClusterMetadataLabels,
)
from .Colormap import Colormap  # noqa: E402


class MatplotlibPNGClusterExportService(ClusterExportService):
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(logger=logger)

    def export(
        self,
        cluster: Cluster,
        out_path: Path,
        *,
        context: ClusterExportContext,
        colormap: Colormap,
    ) -> None:
        import matplotlib.pyplot as plt

        data_kev = np.asarray(
            context.physics.adu_to_kev(np.asarray(cluster.data, dtype=np.float64))
        )
        metadata = self.build_metadata(cluster, context)
        fig = plt.figure(figsize=(10, 5), dpi=120)
        try:
            gs = fig.add_gridspec(1, 2, width_ratios=[3, 1], wspace=0.3)
            ax = fig.add_subplot(gs[0, 0])
            self._render_cluster(ax, cluster, data_kev, colormap, context.labels, fig)
            meta_ax = fig.add_subplot(gs[0, 1])
            meta_ax.axis("off")
            self.render_metadata(meta_ax, metadata, context.labels)
            try:
                fig.savefig(out_path, format="png", bbox_inches="tight")
            except Exception:
                self._logger.exception(
                    "Failed to save cluster PNG to %s", out_path
                )
                raise
            self._logger.debug(
                "Exported cluster %s → %s", cluster.clusterId, out_path
            )
        finally:
            plt.close(fig)

    @staticmethod
    def _render_cluster(
        ax: Any,
        cluster: Cluster,
        data_kev: np.ndarray,
        colormap: Colormap,
        labels: ClusterMetadataLabels,
        fig: Any,
    ) -> None:
        x_edges, y_edges = _absolute_edges(cluster, data_kev.shape)
        mesh = ax.pcolormesh(
            x_edges, y_edges, data_kev, cmap=colormap.value, shading="flat"
        )
        ax.set_xlabel(labels.x_axis)
        ax.set_ylabel(labels.y_axis)
        ax.set_title(_title(cluster))
        ax.set_aspect("equal")
        ax.grid(True, which="both", alpha=0.15)
        cbar = fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(labels.colorbar)

    def render_metadata(
        self,
        canvas: Any,
        metadata: ClusterExportMetadata,
        labels: ClusterMetadataLabels,
    ) -> None:
        lines = _format_metadata(metadata, labels)
        canvas.text(
            0.0,
            1.0,
            "\n".join(lines),
            va="top",
            ha="left",
            family="monospace",
            fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "#f4f4f4", "edgecolor": "#b0b0b0"},
        )


def _absolute_edges(
    cluster: Cluster, shape: Tuple[int, int]
) -> Tuple[np.ndarray, np.ndarray]:
    rows, cols = shape
    bbox = cluster.boundingBox
    x0 = bbox.left - 0.5
    y0 = bbox.top - 0.5
    x_edges = x0 + np.arange(cols + 1)
    y_edges = y0 + np.arange(rows + 1)
    return x_edges, y_edges


def _title(cluster: Cluster) -> str:
    cid = cluster.clusterId if cluster.clusterId is not None else "-"
    return f"Cluster Id: {cid}"


def _format_metadata(
    metadata: ClusterExportMetadata, labels: ClusterMetadataLabels
) -> list[str]:
    peak_x, peak_y = metadata.peak_xy_absolute
    lines = [
        f"{labels.energy}: {metadata.total_energy_kev:.2f} {labels.kev_unit}",
        f"{labels.pixels}: {metadata.pixel_count}",
        "",
        f"{labels.sigma_x}: {metadata.sigma_x:.1f}",
        f"{labels.sigma_y}: {metadata.sigma_y:.1f}",
        f"{labels.full_width_x}: {metadata.full_width_x}",
        f"{labels.full_width_y}: {metadata.full_width_y}",
        f"{labels.energy_per_pixel}: {metadata.energy_per_pixel_kev:.2f} {labels.kev_unit}",
        f"{labels.peak_xy}: ({peak_x}, {peak_y})",
    ]
    if metadata.selection_summary:
        lines.append("")
        lines.append(f"{labels.selection}:")
        lines.append(metadata.selection_summary)
    return lines
