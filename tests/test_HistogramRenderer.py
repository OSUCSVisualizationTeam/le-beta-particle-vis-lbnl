# Citation for Unit Tests: HistogramRenderer returning valid PNG images
# Date: 26/02/2026
# Adapted from Claude Code:
# Write pure Python unit tests for MatplotlibHistogramRenderer and MockHistogramRenderer verifying PNG generation.

"""Tests for HistogramRenderer service.

Pure Python tests — no QApplication instantiation.
"""
import numpy as np

from le_beta_vis.common.HistogramRenderer import (
    MatplotlibHistogramRenderer,
)
from MockHistogramRenderer import MockHistogramRenderer

_PNG_HEADER = b'\x89PNG'


def test_render_returns_png_bytes():
    """MatplotlibHistogramRenderer should return valid PNG bytes."""
    renderer = MatplotlibHistogramRenderer()
    data = np.random.rand(10, 10) * 1000
    result = renderer.render_energy_histogram(
        data, bins=20, width=300, height=200, dpi=100,
    )
    assert isinstance(result, bytes)
    assert result[:4] == _PNG_HEADER


def test_render_empty_data():
    """All-zero data should render without error."""
    renderer = MatplotlibHistogramRenderer()
    data = np.zeros((5, 5))
    result = renderer.render_energy_histogram(
        data, bins=10, width=200, height=150, dpi=72,
    )
    assert isinstance(result, bytes)
    assert result[:4] == _PNG_HEADER


def test_mock_returns_valid_png():
    """MockHistogramRenderer should return parseable PNG bytes."""
    renderer = MockHistogramRenderer()
    data = np.ones((3, 3))
    result = renderer.render_energy_histogram(
        data, bins=10, width=100, height=100, dpi=72,
    )
    assert isinstance(result, bytes)
    assert result[:4] == _PNG_HEADER


def test_render_1d_data():
    """Renderer should handle 1D data arrays."""
    renderer = MatplotlibHistogramRenderer()
    data = np.array([100, 200, 300, 0, 0, 500])
    result = renderer.render_energy_histogram(
        data, bins=5, width=300, height=200, dpi=100,
    )
    assert result[:4] == _PNG_HEADER
