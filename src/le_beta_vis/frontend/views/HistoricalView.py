from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ..viewmodels.HistoricalViewModel import HistoricalViewModel, HistoricalMode


class HistoricalView(QWidget):
    def __init__(self, viewModel: HistoricalViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        self.layout = QVBoxLayout()
        # self.tr() marks the string for translation
        self.label = QLabel(self.tr("Historical Event Analysis Mode"))
        self.modeLabel = QLabel(self.tr("Current Mode: Historical"))
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.modeLabel)
        self.setLayout(self.layout)

    def bindViewModel(self):
        self.viewModel.add_mode_changed_callback(self.updateModeLabel)
        # Set initial
        self.updateModeLabel(self.viewModel.mode)

    def updateModeLabel(self, mode: HistoricalMode):
        if mode == HistoricalMode.LIVE:
            self.modeLabel.setText(self.tr("Current Mode: LIVE MONITORING"))
            self.modeLabel.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.modeLabel.setText(self.tr("Current Mode: Historical Analysis"))
            self.modeLabel.setStyleSheet("color: black;")
