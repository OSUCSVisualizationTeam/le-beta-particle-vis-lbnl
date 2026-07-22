from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from .ProgressOverlay import ProgressOverlay


class ClusteringProgressOverlay(ProgressOverlay):
    """Progress overlay with a Cancel button for cluster extraction.

    Extends ``ProgressOverlay`` by adding a Cancel button in the
    accessory slot.  Emits ``cancelRequested`` when the button is
    clicked.
    """

    cancelRequested = Signal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(title="Clustering", parent=parent)
        self._addCancelButton()

    def _addCancelButton(self) -> None:
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        self._cancelBtn = QPushButton(self.tr("Cancel"))
        self._cancelBtn.setFixedWidth(80)
        self._cancelBtn.clicked.connect(self.cancelRequested.emit)
        btn_row.addWidget(self._cancelBtn)
        self._accessoryLayout().addLayout(btn_row)
