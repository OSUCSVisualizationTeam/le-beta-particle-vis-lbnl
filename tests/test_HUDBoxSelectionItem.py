import sys

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.widgets._HUDBoxSelectionItem import (
    _HUDBoxSelectionItem,
)

app = QApplication.instance() or QApplication(sys.argv)


def test_initial_state_invisible():
    item = _HUDBoxSelectionItem()
    assert item.boundingRect() == QRectF()
    assert not item.isVisible()


def test_set_widget_rect_shows_item():
    item = _HUDBoxSelectionItem()
    item.setWidgetRect(QRectF(10, 20, 30, 40), "30 x 40")
    assert item.isVisible()
    br = item.boundingRect()
    assert br.left() <= 10
    assert br.right() >= 40
    assert br.bottom() >= 60  # includes label gap + height


def test_clearing_hides_item():
    item = _HUDBoxSelectionItem()
    item.setWidgetRect(QRectF(0, 0, 10, 10), "10 x 10")
    item.setWidgetRect(None)
    assert not item.isVisible()
    assert item.boundingRect() == QRectF()


def test_border_width_clamps_to_one():
    item = _HUDBoxSelectionItem()
    item.setBorderWidth(0)
    assert item._borderWidth == 1
    item.setBorderWidth(3)
    assert item._borderWidth == 3
