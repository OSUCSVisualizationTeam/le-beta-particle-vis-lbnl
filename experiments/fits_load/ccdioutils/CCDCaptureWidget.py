from PySide6 import QtWidgets
from . import CCDCaptureModel


class CCDCaptureWidget(QtWidgets.QWidget):
    """A PyQT widget aimed at displaying CCD captured data"""

    class ViewModel:
        def __init__(self):
            self.__capture = CCDCaptureModel()

    def __init__(self):
        self._vbox = QtWidgets.QVBoxLayout(self)

        self.setLayout(self._vbox)
