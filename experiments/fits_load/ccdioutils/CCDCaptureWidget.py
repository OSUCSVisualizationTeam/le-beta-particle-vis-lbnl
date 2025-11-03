from PySide6 import QtWidgets, QtCore, QtGui
from .CCDCaptureViewModel import BaseCCDCaptureViewModel
import matplotlib.pyplot as plt


class _VizWidget(QtWidgets.QLabel):
    """A visualization widget aimed at displaying CCD event data on its pixmap"""

    mouseMoved = QtCore.Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)  # Enable mouse tracking for this widget

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        self.mouseMoved.emit(event.x(), event.y())
        super().mouseMoveEvent(event)  # Call base class implementation


class CCDCaptureWidget(QtWidgets.QWidget):
    """A PyQT widget aimed at displaying CCD captured data"""

    def __init__(self, viewModel: BaseCCDCaptureViewModel, parent=None):
        super().__init__(parent)
        self.__viewModel = viewModel
        self._vbox = QtWidgets.QVBoxLayout(self)

        self._toolbar = QtWidgets.QToolBar()
        self._vbox.addWidget(self._toolbar)

        self._addToolbarItems()

        self._vizWidget = _VizWidget()  # Use custom label
        self._vizWidget.setAlignment(QtCore.Qt.AlignCenter)
        self._vbox.addWidget(self._vizWidget)

        self.setLayout(self._vbox)
        self._updateVisualization()

        self._vizWidget.mouseMoved.connect(self._onVisualizationWidgetMouseMove)

    # Widget building

    def _addToolbarItems(self):
        self._addColormapSelectionWidget()
        self._addResetButton()
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        self._toolbar.addWidget(spacer)

        self._addCurrentValueLabel()

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

    def _addCurrentValueLabel(self):
        self._valueLabel = QtWidgets.QLabel()
        self._valueLabel.setText("Value: NaN")
        self._valueLabel.setMinimumWidth(128)
        self._toolbar.addWidget(self._valueLabel)

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
            self._vizWidget.setPixmap(display_data)

    def _resetViewModel(self):
        """Resets view model state"""
        self.__viewModel.reset()
        self._updateVisualization()

    def _onVisualizationWidgetMouseMove(self, x: int, y: int):
        coord = f"({y},{x})"
        value = self.__viewModel.valueAt(y, x)
        self._valueLabel.setText(f"Value: {coord}: {value:.2e} keV")
