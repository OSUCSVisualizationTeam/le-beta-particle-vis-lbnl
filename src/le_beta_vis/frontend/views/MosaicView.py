from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QScrollArea,
    QToolButton,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from ..viewmodels.MosaicViewModel import MosaicViewModel


class MosaicView(QWidget):
    """
    Displays a horizontal strip of HDU thumbnails.
    """

    def __init__(self, viewModel: MosaicViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.buttons = []
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setStyleSheet("background-color: #1e1e1e; border: none;")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: #1e1e1e;")
        self.containerLayout = QHBoxLayout(self.container)
        self.containerLayout.setContentsMargins(5, 5, 5, 5)
        self.containerLayout.setSpacing(10)
        self.containerLayout.setAlignment(Qt.AlignLeft)

        self.scrollArea.setWidget(self.container)
        layout.addWidget(self.scrollArea)

        self.setFixedHeight(130)

    def bindViewModel(self):
        self.viewModel.add_thumbnails_changed_callback(self.refreshThumbnails)
        self.viewModel.add_selection_changed_callback(self.updateSelection)

    def refreshThumbnails(self):
        for btn in self.buttons:
            self.containerLayout.removeWidget(btn)
            btn.deleteLater()
        self.buttons = []

        for i, pixmap in enumerate(self.viewModel.thumbnails):
            btn = QToolButton()
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(100, 100))
            btn.setCheckable(True)
            btn.setAutoExclusive(True)  # Only one can be checked
            btn.setFixedSize(110, 110)
            btn.setStyleSheet(
                """
                QToolButton {
                    background-color: #333;
                    border: 1px solid #555;
                    border-radius: 4px;
                }
                QToolButton:checked {
                    background-color: #444;
                    border: 2px solid #0078d7;
                }
                QToolButton:hover {
                    border: 1px solid #888;
                }
            """
            )

            btn.clicked.connect(lambda checked, idx=i: self.viewModel.selectIndex(idx))

            self.containerLayout.addWidget(btn)
            self.buttons.append(btn)

        # Set initial selection if any
        if self.viewModel.selectedIndex >= 0 and self.viewModel.selectedIndex < len(
            self.buttons
        ):
            self.buttons[self.viewModel.selectedIndex].setChecked(True)

    def updateSelection(self, index: int):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
