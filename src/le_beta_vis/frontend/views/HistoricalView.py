from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class HistoricalView(QWidget):
    def __init__(self, viewModel=None):
        super().__init__()
        self.viewModel = viewModel
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        # self.tr() marks the string for translation
        label = QLabel(self.tr("Historical Event Analysis Mode"))
        layout.addWidget(label)
        self.setLayout(layout)
