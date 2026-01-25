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
from .MosaicView import MosaicView


class RawDataView(QWidget):
    def __init__(self, viewModel: RawDataViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        """Initializes the UI components and layout."""
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self._setupMosaicView()
        self._setupMainBody()

    def _setupMosaicView(self):
        """Creates the top HDU Mosaic View."""
        self.mosaicView = MosaicView(self.viewModel.mosaicViewModel)
        self.mainLayout.addWidget(self.mosaicView)

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
        """Creates the tool selection bar on the left."""
        self.leftToolbar = QFrame()
        self.leftToolbar.setFixedWidth(50)
        self.leftToolbar.setStyleSheet(
            "background-color: #2d2d2d; border-right: 1px solid #3d3d3d;"
        )
        layout = QVBoxLayout(self.leftToolbar)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        tools = [self.tr("Ptr"), self.tr("Mag"), self.tr("Box"), self.tr("Roi")]
        for tool in tools:
            btn = QToolButton()
            btn.setText(tool)
            btn.setFixedSize(40, 40)
            layout.addWidget(btn)

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
        self.cmapSelector.addItems(
            ["viridis", "plasma", "inferno", "magma", "jet", "bone", "hot", "cool"]
        )
        self.cmapSelector.currentTextChanged.connect(self.onColormapChanged)
        layout.addWidget(self.cmapSelector)

        layout.addWidget(QLabel(self.tr("Range (keV)")))
        rangePlaceholder = QFrame()
        rangePlaceholder.setFixedHeight(30)
        rangePlaceholder.setStyleSheet("background-color: #ddd; border-radius: 4px;")
        layout.addWidget(rangePlaceholder)

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

    def updateImage(self):
        """Update the displayed pixmap from the ViewModel."""
        pixmap = self.viewModel.currentPixmap
        if pixmap is not None:
            self.imageLabel.setPixmap(pixmap)
        else:
            self.imageLabel.clear()

    def onColormapChanged(self, text):
        self.viewModel.setColormap(text)
