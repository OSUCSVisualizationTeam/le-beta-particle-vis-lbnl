from PySide6 import QtWidgets, QtCore
from .CCDCaptureViewModel import BaseCCDCaptureViewModel
import matplotlib.pyplot as plt


class CCDCaptureWidget(QtWidgets.QWidget):
    """A PyQT widget aimed at displaying CCD captured data"""

    def __init__(self, viewModel: BaseCCDCaptureViewModel, parent=None):
        super().__init__(parent)
        self.__viewModel = viewModel
        self._vbox = QtWidgets.QVBoxLayout(self)

        self._toolbar = QtWidgets.QToolBar()
        self._vbox.addWidget(self._toolbar)

        self._addColormapSelectionWidget()
        self._addResetButton()

        self._visualizationWidget = QtWidgets.QLabel()
        self._visualizationWidget.setAlignment(QtCore.Qt.AlignCenter)
        self._vbox.addWidget(self._visualizationWidget)

        self.setLayout(self._vbox)
        self._updateVisualization()

    # Widget building

    def _addColormapSelectionWidget(self):
        colormapContainer = QtWidgets.QWidget()
        colormapLayout = QtWidgets.QHBoxLayout(colormapContainer)
        colormapLayout.setContentsMargins(0, 0, 0, 0)

        colormapLabel = QtWidgets.QLabel("Colormap")
        colormapLayout.addWidget(colormapLabel)

        self._colormapComboBox = QtWidgets.QComboBox()
        for cmap in plt.colormaps():
            self._colormapComboBox.addItem(cmap)

        default_colormap_index = self._colormapComboBox.findText("Greys_r")
        if default_colormap_index != -1:
            self._colormapComboBox.setCurrentIndex(default_colormap_index)

        self._colormapComboBox.currentIndexChanged.connect(self._onColormapChanged)
        colormapLayout.addWidget(self._colormapComboBox)
        self._toolbar.addWidget(colormapContainer)

    def _addResetButton(self):
        resetButton = QtWidgets.QToolButton()
        resetButton.setText("Reset")
        resetButton.clicked.connect(self._resetViewModel)
        self._toolbar.addWidget(resetButton)

    # Callbacks

    def _onColormapChanged(self, index: int):
        """Callback invoked whenever the user selects a different colormap"""
        selected_colormap = self._colormapComboBox.itemText(index)
        self.__viewModel.setCurrentColormap(selected_colormap)
        self._updateVisualization()

    def _updateVisualization(self):
        """Obtain data visualizable data from the view model"""
        display_data = self.__viewModel.getMatplotPixmap()
        if display_data:
            self._visualizationWidget.setPixmap(display_data)

    def _resetViewModel(self):
        """Resets view model state"""
        self.__viewModel.reset()
        self._updateVisualization()
