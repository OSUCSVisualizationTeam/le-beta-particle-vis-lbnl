import io
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class HistogramRenderer(ABC):
    """Abstract interface for rendering energy distribution histograms."""

    @abstractmethod
    def render_energy_histogram(
        self,
        data: np.ndarray,
        bins: int,
        width: int,
        height: int,
        dpi: int,
        x_label: str = "Energy (ADU)",
        colormap: Optional[str] = None,
    ) -> bytes:
        """Renders pixel energy distribution to PNG bytes.

        Args:
            data: 2D/3D pixel array (values > 0 are plotted).
            bins: Number of histogram bins.
            width: Output image width in pixels.
            height: Output image height in pixels.
            dpi: Output resolution.
            x_label: Label for the x-axis.
            colormap: Optional matplotlib colormap name. When set,
                bars are colored using the colormap; otherwise a
                solid ``#3498db`` fill is used.

        Returns:
            PNG image as bytes.
        """
        ...


class MatplotlibHistogramRenderer(HistogramRenderer):
    """Renders energy histograms using matplotlib's Agg backend."""

    def render_energy_histogram(
        self,
        data: np.ndarray,
        bins: int,
        width: int,
        height: int,
        dpi: int,
        x_label: str = "Energy (ADU)",
        colormap: Optional[str] = None,
    ) -> bytes:
        """Renders pixel energy distribution to PNG bytes.

        Uses matplotlib with the non-interactive Agg backend so
        this can safely run on a background thread.

        Args:
            data: 2D/3D pixel array (values > 0 are plotted).
            bins: Number of histogram bins.
            width: Output image width in pixels.
            height: Output image height in pixels.
            dpi: Output resolution.
            x_label: Label for the x-axis.
            colormap: Optional matplotlib colormap name. When set,
                bars are colored using the colormap; otherwise a
                solid ``#3498db`` fill is used.

        Returns:
            PNG image as bytes.
        """
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(
            figsize=(width / dpi, height / dpi),
            dpi=dpi,
        )
        flat = data.flatten()
        flat = flat[flat > 0]
        if len(flat) > 0:
            if colormap is not None:
                self._render_colormap_bars(
                    ax, flat, bins, colormap,
                )
            else:
                ax.hist(
                    flat,
                    bins=bins,
                    color="#3498db",
                    edgecolor="#2c3e50",
                )
        ax.set_xlabel(x_label)
        ax.set_ylabel("Count")
        ax.set_title("Pixel Energy Distribution")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def _render_colormap_bars(
        ax: object,
        flat: np.ndarray,
        bins: int,
        colormap: str,
    ) -> None:
        """Draws histogram bars colored by a matplotlib colormap."""
        import matplotlib
        import matplotlib.pyplot as plt

        counts, edges = np.histogram(flat, bins=bins)
        centers = 0.5 * (edges[:-1] + edges[1:])
        bar_width = edges[1] - edges[0]

        cmap = matplotlib.colormaps.get_cmap(colormap)
        norm = plt.Normalize(vmin=centers.min(), vmax=centers.max())
        colors = cmap(norm(centers))

        ax.bar(
            centers, counts,
            width=bar_width,
            color=colors,
            edgecolor="#2c3e50",
            align="center",
        )
