from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QScrollArea,
    QGroupBox,
    QFrame,
    QSizePolicy,
    QToolButton,
)
from PySide6.QtCore import Qt
from ..viewmodels.RawDataViewModel import RawDataViewModel
from ..fitsconverters import Colormap
from ..widgets.VerticalRangeControl import VerticalRangeControl
from .MosaicView import MosaicView


class RawDataView(QWidget):
    def __init__(self, viewModel: RawDataViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        """Initializes the UI components and layout."""
        # Main Layout (Top Strip + Body)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self._setupMosaicView()
        self._setupMainBody()

    def _setupMosaicView(self):
        """Creates the top HDU Mosaic View."""
        # Use the specialized MosaicView widget
        self.mosaicView = MosaicView(self.viewModel.mosaicViewModel)
        self.mainLayout.addWidget(self.mosaicView)
        # Initially hidden until loaded
        self.mosaicView.setVisible(False)

    def _setupMainBody(self):
        """Creates the main content area with toolbar, image, and sidebar."""
        self.bodyWidget = QWidget()
        self.bodyLayout = QHBoxLayout(self.bodyWidget)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(0)
        self.mainLayout.addWidget(self.bodyWidget)

        self._setupLeftToolbar()
        self._setupCenterImageArea()
        self._setupRightSidebar()

    def _setupLeftToolbar(self):
        """Creates the tool selection bar and range control on the left."""
        self.leftToolbar = QFrame()
        self.leftToolbar.setFixedWidth(100)  # ADR-001: Increased to 100px
        self.leftToolbar.setStyleSheet(
            "background-color: #2d2d2d; border-right: 1px solid #3d3d3d;"
        )
        layout = QVBoxLayout(self.leftToolbar)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        # Tools Section
        tools = [self.tr("Ptr"), self.tr("Mag"), self.tr("Box"), self.tr("Zoom")]
        for tool in tools:
            btn = QToolButton()
            btn.setText(tool)
            btn.setFixedSize(90, 40)
            layout.addWidget(btn)

        layout.addSpacing(20)

        # Unified Vertical Range Control
        # Initialize with temporary default; updateImage will set real data range
        self.rangeControl = VerticalRangeControl(abs_min=0.0, abs_max=1.0)
        self.rangeControl.setVisible(False) # Hidden until file loaded
        self.rangeControl.rangeChanged.connect(self.onRangeChanged)

        layout.addWidget(self.rangeControl)

        self.bodyLayout.addWidget(self.leftToolbar)

    def _setupCenterImageArea(self):
        """Creates the scrollable central area for data visualization."""
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setAlignment(Qt.AlignCenter)
        self.scrollArea.setStyleSheet("background-color: #000; border: none;")

        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.scrollArea.setWidget(self.imageLabel)
        self.bodyLayout.addWidget(self.scrollArea)

    def _setupRightSidebar(self):
        """Creates and populates the control sidebar on the right."""
        self.rightSidebar = QFrame()
        self.rightSidebar.setFixedWidth(300)
        self.rightSidebar.setStyleSheet(
            "background-color: #f0f0f0; border-left: 1px solid #ccc;"
        )
        self.rightLayout = QVBoxLayout(self.rightSidebar)
        self.rightLayout.setContentsMargins(10, 10, 10, 10)
        self.rightLayout.setSpacing(15)
        self.rightLayout.setAlignment(Qt.AlignTop)

        self._addVisualizationSection()
        self._addFilteringSection()
        self._addExtractionSection()
        self._addInspectorSection()

        self.bodyLayout.addWidget(self.rightSidebar)

    def _addVisualizationSection(self):
        """Adds visualization controls to the sidebar."""
        group = QGroupBox(self.tr("Visualization"))
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel(self.tr("Colormap")))
        self.cmapSelector = QComboBox()
        # Use Enum values to ensure consistency
        self.cmapSelector.addItems([c.value for c in Colormap])
        self.cmapSelector.currentTextChanged.connect(self.onColormapChanged)
        layout.addWidget(self.cmapSelector)

        self.rightLayout.addWidget(group)

    def _addFilteringSection(self):
        """Adds the filtering pipeline section to the sidebar."""
        group = QGroupBox(self.tr("Filtering Pipeline"))
        layout = QVBoxLayout(group)

        placeholder = QLabel(self.tr("(Not implemented yet)"))
        placeholder.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(placeholder)

        layout.addWidget(QLabel(self.tr("1. Pedestal Subtraction")))
        layout.addWidget(QLabel(self.tr("2. Gaussian Blur")))
        self.rightLayout.addWidget(group)

    def _addExtractionSection(self):
        """Adds the cluster extraction section to the sidebar."""
        group = QGroupBox(self.tr("Cluster Extraction"))
        layout = QVBoxLayout(group)
        placeholder = QLabel(self.tr("(Not implemented yet)"))
        placeholder.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(placeholder)
        group.setFixedHeight(100)
        self.rightLayout.addWidget(group)

    def _addInspectorSection(self):
        """Adds the selection inspector section to the sidebar."""
        group = QGroupBox(self.tr("Inspector: Selection"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("No selection")))
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.rightLayout.addWidget(group)

    def bindViewModel(self):
        """Register callbacks with the ViewModel."""
        self.viewModel.add_image_changed_callback(self.updateImage)
        self.viewModel.mosaicViewModel.add_thumbnails_changed_callback(
            self.updateMosaicVisibility
        )
        self.updateMosaicVisibility()

        # Initialize Range Control state
        vmin, vmax = self.viewModel.visualizationRange
        self.rangeControl.setValues(vmin, vmax)
        self.rangeControl.setColormap(self.viewModel.colormap)

    def updateMosaicVisibility(self):
        """Hides the mosaic view if there are 0 or 1 HDUs."""
        count = len(self.viewModel.mosaicViewModel.thumbnails)
        self.mosaicView.setVisible(count > 1)

    def updateImage(self):
        """Update the displayed pixmap from the ViewModel."""
        
        # 1. Update Pixmap and toggle visibility
        pixmap = self.viewModel.currentPixmap
        self.rangeControl.setVisible(pixmap is not None)
        
        if pixmap is not None:
            self.imageLabel.setPixmap(pixmap)
        else:
            self.imageLabel.clear()
            
        # 2. Update Range Control with Data Limits
        dmin, dmax = self.viewModel.dataRange
        self.rangeControl.setAbsoluteRange(dmin, dmax)

        # 3. Ensure handles reflect the current thresholds
        vmin, vmax = self.viewModel.visualizationRange
        self.rangeControl.setValues(vmin, vmax)
        
        # 4. Force gradient refresh
        self.rangeControl.setColormap(self.viewModel.colormap)

    def onColormapChanged(self, text):
        self.viewModel.setColormap(text)
        self.rangeControl.setColormap(text)

    def onRangeChanged(self, vmin, vmax):
        self.viewModel.setVisualizationRange(vmin, vmax)