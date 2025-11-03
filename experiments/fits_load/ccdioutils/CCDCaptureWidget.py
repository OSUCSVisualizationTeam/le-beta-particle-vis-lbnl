from PySide6 import QtWidgets, QtCore
from . import CCDCaptureViewModel


class CCDCaptureWidget(QtWidgets.QWidget):
    """A PyQT widget aimed at displaying CCD captured data"""

    def __init__(self, viewModel: CCDCaptureViewModel, parent=None):
        super().__init__(parent)
        self.__viewModel = viewModel
        self._vbox = QtWidgets.QVBoxLayout(self)

        self._toolbar = QtWidgets.QToolBar()
        self._vbox.addWidget(self._toolbar)

        self._visualizationWidget = QtWidgets.QLabel()
        self._visualizationWidget.setAlignment(QtCore.Qt.AlignCenter)
        self._vbox.addWidget(self._visualizationWidget)

        self.setLayout(self._vbox)
        self._updateVisualization()

    def _updateVisualization(self):
        """Obtain data visualizable data from the view model"""
        display_data = self.__viewModel.getDisplayPixmap()
        if display_data:
            self._visualizationWidget.setPixmap(display_data)
