from abc import ABC, abstractmethod
import numpy as np
from typing import Tuple, Any

from le_beta_vis.common.filter_pipeline import ScalingFunction
from .colormaps import Colormap

__all__ = [
    "Colormap",
    "Fits2QPixmapConverter",
    "ScalingFunction",
]


class Fits2QPixmapConverter(ABC):
    """
    Interface for converting raw FITS data (keV matrices) into renderable buffers.
    Enforces a consistent pipeline structure: Clip -> Scale -> Normalize -> Colorize -> Buffer.
    The output is a NumPy array (uint8) suitable for QImage creation.
    """

    @abstractmethod
    def convert(
        self,
        matrix: np.ndarray,
        colormap: Colormap,
        vrange: Tuple[float, float],
        scaling: ScalingFunction = ScalingFunction.LINEAR,
    ) -> np.ndarray:
        """
        Orchestrates the conversion pipeline. Returns a NumPy RGB or Grayscale buffer.
        """
        raise NotImplementedError

    @abstractmethod
    def _clip(self, matrix: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        """Step 1: Clip data to the specified range/thresholds."""
        raise NotImplementedError

    @abstractmethod
    def _scale(
        self, matrix: np.ndarray, scaling: ScalingFunction, max_val: float
    ) -> np.ndarray:
        """Step 2: Apply the scaling function (Linear, Log, Sqrt)."""
        raise NotImplementedError

    @abstractmethod
    def _normalize(self, matrix: np.ndarray, max_val: float) -> np.ndarray:
        """Step 3: Normalize scaled data to 8-bit integer range (0-255)."""
        raise NotImplementedError

    @abstractmethod
    def _colorize(self, matrix: np.ndarray, colormap: Colormap) -> np.ndarray:
        """Step 4: Apply false color map (or keep grayscale). Returns RGB or Grayscale buffer."""
        raise NotImplementedError

    @abstractmethod
    def _to_buffer(self, image_data: Any) -> np.ndarray:
        """Step 5: Finalize the data as a contiguous NumPy uint8 array."""
        raise NotImplementedError
