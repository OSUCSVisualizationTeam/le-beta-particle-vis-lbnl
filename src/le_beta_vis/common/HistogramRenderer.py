import io
from abc import ABC, abstractmethod

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
    ) -> bytes:
        """Renders pixel energy distribution to PNG bytes.

        Args:
            data: 2D/3D pixel array (values > 0 are plotted).
            bins: Number of histogram bins.
            width: Output image width in pixels.
            height: Output image height in pixels.
            dpi: Output resolution.
            x_label: Label for the x-axis.

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
