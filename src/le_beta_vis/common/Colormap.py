"""Colormap enum — single source of truth for false-color rendering.

Lives in ``common`` so both ViewModel/service layers and frontend render
helpers can reference the same enum without creating a frontend → common
layering inversion.
"""
from enum import Enum


class Colormap(str, Enum):
    """Available colormaps for false-color visualization."""

    VIRIDIS = "viridis"
    PLASMA = "plasma"
    INFERNO = "inferno"
    MAGMA = "magma"
    JET = "jet"
    BONE = "bone"
    HOT = "hot"
    COOL = "cool"
    GRAYSCALE = "grayscale"
