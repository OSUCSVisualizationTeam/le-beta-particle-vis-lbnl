import sys

import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.widgets.MagnifierGraphicsItem import (
    MagnifierGraphicsItem,
)

# QApplication must exist before creating any QPixmap
app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def magnifier():
    return MagnifierGraphicsItem(
        fixedDisplaySize=127,
        initialMagnificationFactor=3.0,
    )


@pytest.fixture
def source_data():
    """Returns a (QPixmap, np.ndarray) tuple for a 100x100 image."""
    raw = np.arange(10000, dtype=np.float64).reshape(100, 100)
    pixmap = QPixmap(100, 100)
    pixmap.fill()
    return pixmap, raw


def test_bounding_rect_no_source(magnifier):
    """Test boundingRect returns empty when no source pixmap is set."""
    rect = magnifier.boundingRect()
    assert rect == QRectF()


def test_bounding_rect_with_source(magnifier, source_data):
    """Test boundingRect includes display area and label space."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)
    rect = magnifier.boundingRect()
    assert rect.width() == 127 + 10 + 120  # display + padding + label
    assert rect.height() == 127


def test_display_size_property(magnifier):
    """Test the displaySize property returns the configured value."""
    assert magnifier.displaySize == 127


def test_set_pixel_pos_clamped(magnifier, source_data):
    """Test setPixelPos clamps to image bounds."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)

    magnifier.setPixelPos(200, 200)
    assert magnifier._currentPixelPos.x() == 99
    assert magnifier._currentPixelPos.y() == 99

    magnifier.setPixelPos(-5, -5)
    assert magnifier._currentPixelPos.x() == 0
    assert magnifier._currentPixelPos.y() == 0


def test_set_pixel_pos_no_source(magnifier):
    """Test setPixelPos is a no-op without source data."""
    magnifier.setPixelPos(10, 10)
    assert magnifier._currentPixelPos.x() == -1


def test_calculate_source_rect_center(magnifier, source_data):
    """Test _calculateSourceRect centers on the current pixel."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)
    magnifier.setPixelPos(50, 50)

    rect = magnifier._calculateSourceRect()
    effective_side = 127 / 3.0
    expected_x = 50 - effective_side / 2
    expected_y = 50 - effective_side / 2
    assert abs(rect.x() - expected_x) < 1.0
    assert abs(rect.y() - expected_y) < 1.0
    assert abs(rect.width() - effective_side) < 0.01


def test_calculate_source_rect_edge_clamping(magnifier, source_data):
    """Test _calculateSourceRect clamps at image edges."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)
    magnifier.setPixelPos(0, 0)

    rect = magnifier._calculateSourceRect()
    assert rect.x() >= 0
    assert rect.y() >= 0


def test_compute_figures_with_conversion(magnifier, source_data):
    """Test _computeFigures applies conversion function correctly."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, lambda v: v * 2.0)
    magnifier.setPixelPos(50, 50)

    sub = raw[48:52, 48:52]
    min_val, max_val, central_val = magnifier._computeFigures(sub)
    assert min_val == np.min(sub) * 2.0
    assert max_val == np.max(sub) * 2.0
    assert central_val == raw[50, 50] * 2.0


def test_compute_figures_without_conversion(magnifier, source_data):
    """Test _computeFigures returns raw values when no conversion func."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)
    magnifier.setPixelPos(50, 50)

    sub = raw[48:52, 48:52]
    min_val, max_val, central_val = magnifier._computeFigures(sub)
    assert min_val == np.min(sub)
    assert max_val == np.max(sub)
    assert central_val == raw[50, 50]


def test_set_unit_label(magnifier):
    """Test setUnitLabel changes the stored unit label."""
    magnifier.setUnitLabel("eV")
    assert magnifier._unitLabel == "eV"


def test_set_magnification_factor(magnifier):
    """Test setMagnificationFactor updates the stored factor."""
    magnifier.setMagnificationFactor(5.0)
    assert magnifier._magnificationFactor == 5.0


def test_set_hint_lines(magnifier):
    """Test setHintLines stores the hint lines."""
    magnifier.setHintLines(["Line A", "Line B"])
    assert magnifier._hintLines == ["Line A", "Line B"]


def test_bounding_rect_zoom_line_accounted(magnifier, source_data):
    """Test boundingRect accounts for the Zoom label (4 data lines)."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)
    # With 0 hints: totalLines = 4, labelAreaHeight = 4*14+4 = 60 < 127
    rect = magnifier.boundingRect()
    assert rect.height() == 127  # display size still dominates
    # With 10 hints: totalLines = 4 + 11 = 15, height = 15*14+4 = 214 > 127
    magnifier.setHintLines([f"H{i}" for i in range(10)])
    rect_tall = magnifier.boundingRect()
    assert rect_tall.height() > 127


def test_bounding_rect_grows_with_hints(magnifier, source_data):
    """Test boundingRect height accounts for hint lines."""
    pixmap, raw = source_data
    magnifier.setSourceData(pixmap, raw, None)
    rect_no_hints = magnifier.boundingRect()

    magnifier.setHintLines(["A", "B", "C", "D", "E", "F", "G", "H"])
    rect_with_hints = magnifier.boundingRect()
    assert rect_with_hints.height() >= rect_no_hints.height()
    assert rect_with_hints.width() == rect_no_hints.width()
