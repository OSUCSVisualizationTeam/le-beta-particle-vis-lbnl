from PySide6.QtCore import QMetaObject, QSize, Qt, Slot
from PySide6.QtGui import QImage, QPixmap, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..fitsconverters import Colormap
from ..viewmodels.RawDataViewModel import RawDataViewModel
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
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self._setupMosaicView()
        self._setupMainBody()

    def _setupMosaicView(self):
        self.mosaicView = MosaicView(self.viewModel.mosaicViewModel)
        self.mainLayout.addWidget(self.mosaicView)
        self.mosaicView.setVisible(False)

    def _setupMainBody(self):
        self.bodyWidget = QWidget()
        self.bodyLayout = QHBoxLayout(self.bodyWidget)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(0)
        self.mainLayout.addWidget(self.bodyWidget)

        self._setupLeftToolbar()
        self._setupCenterImageArea()
        self._setupRightSidebar()

    def _setupLeftToolbar(self):
        self.leftToolbar = QFrame()
        self.leftToolbar.setFixedWidth(100)
        self.leftToolbar.setStyleSheet(
            "background-color: #2d2d2d; border-right: 1px solid #3d3d3d;"
        )
        layout = QVBoxLayout(self.leftToolbar)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Common size for squared buttons
        btn_size = QSize(40, 40)

        tools = [self.tr("Ptr"), self.tr("Mag"), self.tr("Box")]
        for tool in tools:
            btn = QToolButton()
            btn.setText(tool)
            btn.setFixedSize(btn_size)
            layout.addWidget(btn, 0, Qt.AlignHCenter)

        layout.addWidget(self._createDivider(), 0, Qt.AlignHCenter)

        # Zoom In
        self.btnZoomIn = QToolButton()
        self.btnZoomIn.setText("+")
        self.btnZoomIn.setToolTip(self.tr("Zoom In"))
        self.btnZoomIn.setFixedSize(btn_size)
        self.btnZoomIn.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #ffffff;"
        )
        self.btnZoomIn.clicked.connect(self.viewModel.zoomIn)
        layout.addWidget(self.btnZoomIn, 0, Qt.AlignHCenter)

        # Reset Zoom
        self.btnZoomReset = QToolButton()
        self.btnZoomReset.setText("1x")
        self.btnZoomReset.setToolTip(self.tr("Reset Zoom (1:1)"))
        self.btnZoomReset.setFixedSize(btn_size)
        self.btnZoomReset.setStyleSheet("font-weight: bold; color: #ffffff;")
        self.btnZoomReset.clicked.connect(self.viewModel.resetZoom)
        layout.addWidget(self.btnZoomReset, 0, Qt.AlignHCenter)

        # Zoom Out
        self.btnZoomOut = QToolButton()
        self.btnZoomOut.setText("-")
        self.btnZoomOut.setToolTip(self.tr("Zoom Out"))
        self.btnZoomOut.setFixedSize(btn_size)
        self.btnZoomOut.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #ffffff;"
        )
        self.btnZoomOut.clicked.connect(self.viewModel.zoomOut)
        layout.addWidget(self.btnZoomOut, 0, Qt.AlignHCenter)

        layout.addWidget(self._createDivider(), 0, Qt.AlignHCenter)
        layout.addSpacing(10)

        self.rangeControl = VerticalRangeControl(abs_min=0.0, abs_max=1.0)
        self.rangeControl.setVisible(False)
        self.rangeControl.rangeChanged.connect(self.onRangeChanged)
        layout.addWidget(self.rangeControl, 0, Qt.AlignHCenter)

        self.bodyLayout.addWidget(self.leftToolbar)

    def _createDivider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #555555;")
        line.setFixedWidth(80)
        return line

    def _setupCenterImageArea(self):
        self.scene = QGraphicsScene()
        self.graphicsView = QGraphicsView(self.scene)
        self.graphicsView.setStyleSheet("background-color: #000; border: none;")
        self.graphicsView.setAlignment(Qt.AlignCenter)

        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)

        self.bodyLayout.addWidget(self.graphicsView)

    def _setupRightSidebar(self):
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
        group = QGroupBox(self.tr("Visualization"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("Colormap")))
        self.cmapSelector = QComboBox()
        self.cmapSelector.addItems([c.value for c in Colormap])
        self.cmapSelector.currentTextChanged.connect(self.onColormapChanged)
        layout.addWidget(self.cmapSelector)
        self.rightLayout.addWidget(group)

    def _addFilteringSection(self):
        group = QGroupBox(self.tr("Filtering Pipeline"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("(Not implemented yet)")))
        self.rightLayout.addWidget(group)

    def _addExtractionSection(self):
        group = QGroupBox(self.tr("Cluster Extraction"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("(Not implemented yet)")))
        group.setFixedHeight(100)
        self.rightLayout.addWidget(group)

    def _addInspectorSection(self):
        group = QGroupBox(self.tr("Inspector: Selection"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self.tr("No selection")))
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.rightLayout.addWidget(group)

    def bindViewModel(self):
        # Image changed callback from background thread
        def on_image_changed():
            QMetaObject.invokeMethod(self, "updateImage", Qt.QueuedConnection)

        def on_scale_changed():
            QMetaObject.invokeMethod(self, "updateZoom", Qt.QueuedConnection)

        self.viewModel.add_image_changed_callback(on_image_changed)
        self.viewModel.mosaicViewModel.add_thumbnails_changed_callback(
            self.updateMosaicVisibility
        )
        self.viewModel.add_scale_changed_callback(on_scale_changed)
        self.updateMosaicVisibility()

        vmin, vmax = self.viewModel.visualizationRange
        self.rangeControl.setValues(vmin, vmax)
        self.rangeControl.setColormap(self.viewModel.colormap)

    def updateMosaicVisibility(self):
        count = len(self.viewModel.mosaicViewModel.thumbnails)
        self.mosaicView.setVisible(count > 1)

    @Slot()
    def updateImage(self):
        """Thread-safe update of the displayed pixmap."""
        buffer = self.viewModel.currentBuffer
        self.rangeControl.setVisible(buffer is not None)

        if buffer is not None:
            # Convert NumPy Buffer (RGB) -> QImage -> QPixmap
            height, width, channels = buffer.shape
            bytes_per_line = channels * width
            q_img = QImage(
                buffer.data, width, height, bytes_per_line, QImage.Format_RGB888
            )
            pixmap = QPixmap.fromImage(q_img)

            self.pixmapItem.setPixmap(pixmap)
            self.scene.setSceneRect(0, 0, width, height)

            # Ensure zoom is correct for new image
            self.updateZoom()

            # Update Range Control Limits (Sync with ViewModel data range)
            dmin, dmax = self.viewModel.dataRange
            self.rangeControl.setAbsoluteRange(dmin, dmax)

            vmin, vmax = self.viewModel.visualizationRange
            self.rangeControl.setValues(vmin, vmax)
            self.rangeControl.setColormap(self.viewModel.colormap)
        else:
            self.pixmapItem.setPixmap(QPixmap())

    @Slot()
    def updateZoom(self):
        """Updates the graphics view transform based on scale."""
        # UX Feedback: Busy Cursor & Disable Buttons
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.btnZoomIn.setEnabled(False)
        self.btnZoomOut.setEnabled(False)
        self.btnZoomReset.setEnabled(False)

        try:
            scale = self.viewModel.scale
            transform = QTransform()
            transform.scale(scale, scale)
            self.graphicsView.setTransform(transform)
        finally:
            # Restore UX
            self.btnZoomIn.setEnabled(True)
            self.btnZoomOut.setEnabled(True)
            self.btnZoomReset.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def onColormapChanged(self, text):
        self.viewModel.setColormap(text)

    def onRangeChanged(self, vmin, vmax):
        self.viewModel.setVisualizationRange(vmin, vmax)
