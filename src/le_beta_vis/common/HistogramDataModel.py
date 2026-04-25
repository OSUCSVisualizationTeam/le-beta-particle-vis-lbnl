"""Pure-Python data model for histogram display.

Encapsulates the output of ``numpy.histogram`` together with
presentation metadata (axis label, colormap).  This is a frozen
dataclass so it can be safely passed between threads and tested
without any Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class HistogramDataModel:
    """Immutable container for histogram bar data.

    Attributes:
        counts: Number of occurrences per bin.
        bin_edges: Bin edge values (length = len(counts) + 1).
        x_label: Label for the horizontal axis.
        colormap: Optional Colormap enum value (string form) for bar
            colouring.  ``None`` means a solid default colour.
        x_unit: Optional unit suffix for tooltip display
            (e.g. ``"keV"``, ``"ADU"``).  ``None`` omits the unit.
    """

    counts: np.ndarray
    bin_edges: np.ndarray
    x_label: str
    colormap: Optional[str] = None
    x_unit: Optional[str] = None

    @property
    def bin_centers(self) -> np.ndarray:
        """Midpoint of each bin."""
        return 0.5 * (self.bin_edges[:-1] + self.bin_edges[1:])

    @property
    def bin_widths(self) -> np.ndarray:
        """Width of each bin."""
        return np.diff(self.bin_edges)

    @staticmethod
    def from_pixel_data(
        data: np.ndarray,
        bins: int,
        x_label: str,
        colormap: Optional[str] = None,
        x_unit: Optional[str] = None,
    ) -> Optional[HistogramDataModel]:
        """Builds a model from raw pixel data.

        Flattens the input, discards zeros, and computes
        ``numpy.histogram``.  Returns ``None`` when no non-zero
        pixels remain.

        Args:
            data: 1-D, 2-D, or 3-D pixel array.
            bins: Number of histogram bins.
            x_label: Axis label (e.g. ``"Energy (keV)"``).
            colormap: Optional Colormap enum value (string form).
            x_unit: Optional unit suffix for tooltip display.

        Returns:
            A populated ``HistogramDataModel``, or ``None`` if
            *data* contains only zeros.
        """
        flat = data.flatten()
        flat = flat[flat > 0]
        if len(flat) == 0:
            return None
        counts, bin_edges = np.histogram(flat, bins=bins)
        return HistogramDataModel(
            counts=counts,
            bin_edges=bin_edges,
            x_label=x_label,
            colormap=colormap,
            x_unit=x_unit,
        )
