import sys

import numpy as np
import shiboken6
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from le_beta_vis.frontend.widgets.CaptureGraphicsView import (
    CaptureGraphicsView,
)
from le_beta_vis.frontend.widgets.HDUVisualizationHUDWidget import (
    HDUVisualizationHUDWidget,
)
from le_beta_vis.frontend.widgets.MagnifierGraphicsItem import (
    MagnifierGraphicsItem,
)

app = QApplication.instance() or QApplication(sys.argv)


def test_reproject_magnifier_survives_deleted_item():
    """Issue #188: closing the app while the magnifier is bound must not
    raise when the C++ side of the MagnifierGraphicsItem is torn down
    before the HUD widget's viewport-changed slot stops firing."""
    sourceView = CaptureGraphicsView()
    hud = HDUVisualizationHUDWidget(sourceView)

    magnifier = MagnifierGraphicsItem(
        fixedDisplaySize=127, initialMagnificationFactor=3.0
    )
    pixmap = QPixmap(10, 10)
    pixmap.fill()
    magnifier.setSourceData(pixmap, np.zeros((10, 10)), None)
    magnifier.setPixelPos(5, 5)

    hud.bindMagnifier(magnifier)
    hud.setMagnifierVisible(True)

    shiboken6.delete(magnifier)

    hud._onViewportChanged()
