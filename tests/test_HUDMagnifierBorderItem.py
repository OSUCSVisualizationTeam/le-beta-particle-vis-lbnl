import math
import sys

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.widgets._HUDMagnifierBorderItem import (
    _HUDMagnifierBorderItem,
)

app = QApplication.instance() or QApplication(sys.argv)


def test_initial_state_invisible():
    item = _HUDMagnifierBorderItem()
    assert not item.isVisible()
    assert item.boundingRect() == QRectF()


def test_set_state_visible():
    item = _HUDMagnifierBorderItem()
    item.setState(
        QRectF(5, 6, 127, 127),
        "keV",
        3.0,
        (0.1, 0.9, 0.5),
        ["tip"],
    )
    assert item.isVisible()
    br = item.boundingRect()
    # Must extend past the widget rect to include the label panel.
    assert br.right() > 5 + 127


def test_clear_hides():
    item = _HUDMagnifierBorderItem()
    item.setState(
        QRectF(0, 0, 10, 10), "keV", 1.0, (0.0, 0.0, 0.0), []
    )
    item.setState(None, "", 1.0, (math.nan, math.nan, math.nan), [])
    assert not item.isVisible()


def test_font_scale_grows_bounding_rect():
    state_args = (
        QRectF(5, 6, 127, 127),
        "keV",
        3.0,
        (0.1, 0.9, 0.5),
        ["tip"],
    )
    normal = _HUDMagnifierBorderItem(fontScale=1.0)
    normal.setState(*state_args)
    scaled = _HUDMagnifierBorderItem(fontScale=2.0)
    scaled.setState(*state_args)

    scaledRect = scaled.boundingRect()
    normalRect = normal.boundingRect()
    assert scaledRect.height() > normalRect.height()
    assert scaledRect.width() > normalRect.width()
