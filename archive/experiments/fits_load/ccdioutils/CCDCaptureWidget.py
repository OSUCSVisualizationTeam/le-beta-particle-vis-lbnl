from PySide6 import QtWidgets, QtCore
from superqt.sliders import QLabeledRangeSlider
from .CCDCaptureViewModel import BaseCCDCaptureViewModel
from .CCDCaptureGraphicsView import CCDCaptureGraphicsView
from .CCDCaptureGraphicsViewModel import CCDCaptureGraphicsViewModel
import matplotlib.pyplot as plt


class CCDCaptureWidget(QtWidgets.QWidget):
    """A PyQT widget aimed at displaying CCD captured data"""

    def __init__(
        self,
        viewModel: BaseCCDCaptureViewModel,
        sliderScaleFactor: int = 10000,
        parent=None,
    ):
        super().__init__(parent)
        self.__viewModel = viewModel
        self.__sliderScaleFactor = sliderScaleFactor
        self._vbox = QtWidgets.QVBoxLayout(self)

        self._topToolbar = QtWidgets.QToolBar()
        self._vbox.addWidget(self._topToolbar)

        self._addTopToolbarItems()

        self.__graphicsViewModel = CCDCaptureGraphicsViewModel(self)
        self.__graphicsView = CCDCaptureGraphicsView(self)
        self.__graphicsView.setScene(self.__graphicsViewModel.scene())

        self._vbox.addWidget(self.__graphicsView)
        self._addLowerToolbar()

        self.setLayout(self._vbox)
        self._updateVisualization()

        self.__graphicsView.pixelHovered.connect(self._onPixelHovered)
        self.__graphicsView.magnificationFactorChanged.connect(
            self.__graphicsViewModel.changeMagnificationFactor
        )

    # Widget building

    def _addTopToolbarItems(self):
        self._addColormapSelectionWidget()
        self._addMagnifierButton()
        self._addResetButton()
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        self._topToolbar.addWidget(spacer)

        self._addCurrentValueLabel()

    def _addColormapSelectionWidget(self):
        if self.__viewModel.isUsingAFastQPixmapConverter():
            return
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
        self._topToolbar.addWidget(colormapContainer)

    def _addMagnifierButton(self):
        magnifierButton = QtWidgets.QToolButton()
        magnifierButton.setText("Magnifier")
        magnifierButton.setCheckable(True)
        magnifierButton.setToolTip(
            "Show a magnifier overlay, use left/right arrow keys to reduce/enlarge preview,"
            " up/down to zoom in/out"
        )
        magnifierButton.clicked.connect(self._showMagnifier)
        self._topToolbar.addWidget(magnifierButton)

    def _addResetButton(self):
        resetButton = QtWidgets.QToolButton()
        resetButton.setText("Reset")
        resetButton.clicked.connect(self._resetViewModel)
        self._topToolbar.addWidget(resetButton)

    def _addCurrentValueLabel(self):
        self._valueLabel = QtWidgets.QLabel()
        self._valueLabel.setText("Value: NaN")
        self._valueLabel.setMinimumWidth(128)
        self._topToolbar.addWidget(self._valueLabel)

    def _addLowerToolbar(self):
        self._lowerToolbar = QtWidgets.QToolBar()
        self._vbox.addWidget(self._lowerToolbar)
        self._addLowerToolbarItems()

    def _addLowerToolbarItems(self):
        if not self.__viewModel.isUsingAFastQPixmapConverter():
            applyButton = QtWidgets.QPushButton()
            applyButton.setText("Apply")
            applyButton.clicked.connect(self._onApplyExclusionClicked)
            self._lowerToolbar.addWidget(applyButton)
        self._addRangeSlider()

    def _addRangeSlider(self):
        self.__originalVizRange = self.__viewModel.getVisualizationRange()

        scaledMin = self._scaleValue(self.__originalVizRange[0])
        scaledMax = self._scaleValue(self.__originalVizRange[1])

        rangeSlider = QLabeledRangeSlider(QtCore.Qt.Horizontal)
        rangeSlider.setMinimum(scaledMin)
        rangeSlider.setMaximum(scaledMax)
        rangeSlider.setValue((scaledMin, scaledMax))
        rangeSlider.valueChanged.connect(self._onRangeSliderValueChanged)
        self.__rangeSlider = rangeSlider
        self._lowerToolbar.addWidget(rangeSlider)

    def _scaleValue(self, value: float) -> int:
        return int(value * self.__sliderScaleFactor)

    def _downscaleValue(self, scaled_value: int) -> float:
        return scaled_value / self.__sliderScaleFactor

    # Callbacks

    def _onColormapChanged(self, index: int):
        """Callback invoked whenever the user selects a different colormap"""
        selected_colormap = self._colormapComboBox.itemText(index)
        self.__viewModel.setCurrentColormap(selected_colormap)
        self._updateVisualization()

    def _onApplyExclusionClicked(self):
        self.__viewModel.restrictVisualizationToRange()
        self._updateVisualization()

    def _onRangeSliderValueChanged(self, value):
        scaledMin = self._downscaleValue(value[0])
        scaledMax = self._downscaleValue(value[1])
        self.__viewModel.setVisualizationRange((scaledMin, scaledMax))
        if self.__viewModel.isUsingAFastQPixmapConverter():
            self._onApplyExclusionClicked()

    def _updateVisualization(self):
        """Obtain data visualizable data from the view model and update the graphics view."""
        display_data = self.__viewModel.getQPixmap()
        raw_data = self.__viewModel.getRawData()
        if display_data and raw_data is not None:
            self.__graphicsViewModel.updateImage(
                display_data, raw_data, self.__viewModel.getConversionFunc()
            )

    def _resetViewModel(self):
        """Resets view model state"""
        self.__viewModel.reset()
        oMin = self.__originalVizRange[0]
        oMax = self.__originalVizRange[1]
        scaledMin = self._scaleValue(oMin)
        scaledMax = self._scaleValue(oMax)
        self.__rangeSlider.setValue((scaledMin, scaledMax))
        self._updateVisualization()

    def _showMagnifier(self):
        """Toggles the magnifier overlay and sets focus to the graphics view."""
        self.__graphicsViewModel.toggleMagnifier()
        self.__graphicsView.setFocus()  # Set focus to the graphics view for key events

    @QtCore.Slot(int, int)
    def _onPixelHovered(self, row: int, col: int):
        """
        Slot to receive pixel coordinates from CCDCaptureGraphicsView and update the value label.
        """
        data_rows, data_cols = self.__viewModel.getRawData().shape
        if 0 <= row < data_rows and 0 <= col < data_cols:
            value = self.__viewModel.valueAt(row, col)
            self._valueLabel.setText(f"Value: ({row},{col}): {value:.2e} keV")
            self.__graphicsViewModel.updateMagnifierPosition(row, col)
        else:
            self._valueLabel.setText("Value: NaN")
            self.__graphicsViewModel.updateMagnifierPosition(-1, -1)
