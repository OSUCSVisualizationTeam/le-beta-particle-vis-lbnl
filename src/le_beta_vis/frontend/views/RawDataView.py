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


class RawDataView(QWidget):
    def __init__(self, viewModel: RawDataViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        # Main Layout (Top Strip + Body)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # 1. Top Strip: HDU Mosaic View
        # ---------------------------------------------------------
        self.mosaicFrame = QFrame()
        self.mosaicFrame.setFixedHeight(120)  # Fixed height for thumbnail strip
        self.mosaicFrame.setStyleSheet(
            "background-color: #1e1e1e;"
        )  # Dark background per wireframe
        self.mosaicLayout = QHBoxLayout(self.mosaicFrame)
        self.mosaicLabel = QLabel(self.tr("HDU EXTENSIONS (MOSAIC VIEW) - Placeholder"))
        self.mosaicLabel.setStyleSheet("color: #888;")
        self.mosaicLayout.addWidget(self.mosaicLabel)

        self.mainLayout.addWidget(self.mosaicFrame)

        # 2. Main Body (Left Toolbar + Center Image + Right Sidebar)
        # ---------------------------------------------------------
        self.bodyWidget = QWidget()
        self.bodyLayout = QHBoxLayout(self.bodyWidget)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(0)
        self.mainLayout.addWidget(self.bodyWidget)

        # 2a. Left Toolbar (Tools)
        # ------------------------
        self.leftToolbar = QFrame()
        self.leftToolbar.setFixedWidth(50)
        self.leftToolbar.setStyleSheet(
            "background-color: #2d2d2d; border-right: 1px solid #3d3d3d;"
        )
        self.leftToolbarLayout = QVBoxLayout(self.leftToolbar)
        self.leftToolbarLayout.setContentsMargins(5, 10, 5, 10)
        self.leftToolbarLayout.setSpacing(10)
        self.leftToolbarLayout.setAlignment(Qt.AlignTop)

        # Placeholder Tools (Pointer, Magnifier, etc.)
        tools = [self.tr("Ptr"), self.tr("Mag"), self.tr("Box"), self.tr("Roi")]
        for tool in tools:
            btn = QToolButton()
            btn.setText(tool)  # Icon would go here
            btn.setFixedSize(40, 40)
            self.leftToolbarLayout.addWidget(btn)

        self.bodyLayout.addWidget(self.leftToolbar)

        # 2b. Center Image Area
        # ---------------------
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setAlignment(Qt.AlignCenter)
        self.scrollArea.setStyleSheet("background-color: #000; border: none;")

        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.scrollArea.setWidget(self.imageLabel)

        self.bodyLayout.addWidget(self.scrollArea)

        # 2c. Right Sidebar (Controls)
        # ----------------------------
        self.rightSidebar = QFrame()
        self.rightSidebar.setFixedWidth(300)
        self.rightSidebar.setStyleSheet(
            "background-color: #f0f0f0; border-left: 1px solid #ccc;"
        )
        self.rightLayout = QVBoxLayout(self.rightSidebar)
        self.rightLayout.setContentsMargins(10, 10, 10, 10)
        self.rightLayout.setSpacing(15)
        self.rightLayout.setAlignment(Qt.AlignTop)

        # Section: Visualization
        vizGroup = QGroupBox(self.tr("Visualization"))
        vizLayout = QVBoxLayout()

        vizLayout.addWidget(QLabel(self.tr("Colormap")))
        self.cmapSelector = QComboBox()
        self.cmapSelector.addItems(
            ["viridis", "plasma", "inferno", "magma", "jet", "bone", "hot", "cool"]
        )
        self.cmapSelector.currentTextChanged.connect(self.onColormapChanged)
        vizLayout.addWidget(self.cmapSelector)

        # Range Slider Placeholder
        vizLayout.addWidget(QLabel(self.tr("Range (keV)")))
        rangePlaceholder = QFrame()
        rangePlaceholder.setFixedHeight(30)
        rangePlaceholder.setStyleSheet("background-color: #ddd; border-radius: 4px;")
        vizLayout.addWidget(rangePlaceholder)

        vizGroup.setLayout(vizLayout)
        self.rightLayout.addWidget(vizGroup)

        # Section: Filtering Pipeline (Placeholder)
        filterGroup = QGroupBox(self.tr("Filtering Pipeline"))
        filterLayout = QVBoxLayout()

        filterPlaceholder = QLabel(self.tr("(Not implemented yet)"))
        filterPlaceholder.setStyleSheet("color: #666; font-style: italic;")
        filterLayout.addWidget(filterPlaceholder)

        filterLayout.addWidget(QLabel(self.tr("1. Pedestal Subtraction")))
        filterLayout.addWidget(QLabel(self.tr("2. Gaussian Blur")))
        filterGroup.setLayout(filterLayout)
        self.rightLayout.addWidget(filterGroup)

        # Section: Cluster Extraction (Placeholder)
        clusterGroup = QGroupBox(self.tr("Cluster Extraction"))
        clusterLayout = QVBoxLayout()
        clusterPlaceholder = QLabel(self.tr("(Not implemented yet)"))
        clusterPlaceholder.setStyleSheet("color: #666; font-style: italic;")
        clusterLayout.addWidget(clusterPlaceholder)
        clusterGroup.setLayout(clusterLayout)
        clusterGroup.setFixedHeight(100)
        self.rightLayout.addWidget(clusterGroup)

        # Section: Inspector (Placeholder)
        inspectorGroup = QGroupBox(self.tr("Inspector: Selection"))
        inspectorLayout = QVBoxLayout()
        inspectorLayout.addWidget(QLabel(self.tr("No selection")))
        inspectorGroup.setLayout(inspectorLayout)

        # Push inspector to bottom or let it expand?
        # For now, let it take available space
        inspectorGroup.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.rightLayout.addWidget(inspectorGroup)

        self.bodyLayout.addWidget(self.rightSidebar)

    def bindViewModel(self):
        """Register callbacks with the ViewModel."""
        self.viewModel.add_image_changed_callback(self.updateImage)
        self.viewModel.add_file_loaded_callback(self.updateHDUList)

    def updateImage(self):
        """Update the displayed pixmap from the ViewModel."""
        pixmap = self.viewModel.currentPixmap
        if pixmap is not None:
            self.imageLabel.setPixmap(pixmap)
        else:
            self.imageLabel.clear()

    def updateHDUList(self):
        """
        Update the HDU list.
        TODO: In the future, this will populate the Mosaic View thumbnails.
        For now, we just log it or update a label to show a file was loaded.
        """
        if self.viewModel.hduSummaries:
            self.mosaicLabel.setText(f"Loaded {len(self.viewModel.hduSummaries)} HDUs")

    def onHDUChanged(self, index):
        self.viewModel.setActiveHDU(index)

    def onColormapChanged(self, text):
        self.viewModel.setColormap(text)
