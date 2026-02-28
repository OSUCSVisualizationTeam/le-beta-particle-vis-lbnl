# Citation for Unit Tests: MockHistogramRenderer returning dummy PNG bytes
# Date: 28/02/2026
# Adapted from Claude Code:
# Create a MockHistogramRenderer for tests that returns a minimal valid PNG.
from pathlib import Path
from typing import Optional

import numpy as np

from le_beta_vis.common.HistogramRenderer import HistogramRenderer


class MockHistogramRenderer(HistogramRenderer):
    """Returns a tiny valid PNG for testing without matplotlib."""

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
        """Returns a minimal valid PNG image.

        Args:
            data: Ignored.
            bins: Ignored.
            width: Ignored.
            height: Ignored.
            dpi: Ignored.
            x_label: Ignored.
            colormap: Ignored.

        Returns:
            A minimal valid PNG as bytes.
        """
        png_path = Path(__file__).parent / "mock_histogram.png"
        return png_path.read_bytes()
