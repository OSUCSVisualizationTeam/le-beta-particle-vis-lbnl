from typing import Optional

from PySide6.QtCore import QMetaObject, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap, QResizeEvent, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QVBoxLayout,
    QWidget,
)

from .CaptureGraphicsView import CaptureGraphicsView
from .HDUVisualizationHUDWidget import HDUVisualizationHUDWidget
from .MagnifierGraphicsItem import MagnifierGraphicsItem
from ..viewmodels.RawDataViewModel import RawDataViewModel


_GRAPHICS_VIEW_STYLE = """
    QGraphicsView {
        background-color: #000;
        border: none;
    }
    QScrollBar:vertical {
        width: 12px;
        background: transparent;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: rgba(100, 100, 100, 165);
        min-height: 30px;
        border-radius: 6px;
        margin: 2px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(150, 150, 150, 200);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QScrollBar:horizontal {
        height: 12px;
        background: transparent;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: rgba(100, 100, 100, 165);
        min-width: 30px;
        border-radius: 6px;
        margin: 2px;
    }
    QScrollBar::handle:horizontal:hover {
        background: rgba(150, 150, 150, 200);
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
    }
"""


class HDUVisualizationView(QWidget):
    """Visualization surface for the active HDU.

    Owns the graphics scene, pixmap, magnifier item, zoom transform,
    and the HUD overlay stacked on top of the graphics view. Binds to
    the ViewModel for image, zoom, magnifier, and active-tool state.

    Control-surface concerns (toolbar, status bar, clustering progress,
    ROI / cluster annotation routing) live in the parent
    ``_CenterImageAreaView``. ROI-related graphics-view signals are
    re-emitted here so the parent can route them without reaching into
    private members.
    """

    boxSelectionCompleted = Signal(int, int, int, int)
    boxSelectClicked = Signal(int, int)
    pixelHovered = Signal(int, int)

    def __init__(self, viewModel: RawDataViewModel) -> None:
        super().__init__()
        self._vm = viewModel
        self._stackHost: Optional[_StackHost] = None
        self._hudWidget: Optional[HDUVisualizationHUDWidget] = None
        self._initUI()
        self._bindViewModel()
        self._applyInitialToolState()

    @property
    def hudWidget(self) -> Optional[HDUVisualizationHUDWidget]:
        """The HUD overlay; bound after construction."""
        return self._hudWidget

    def centerOn(self, x: float, y: float) -> None:
        """Delegates pan to the underlying CaptureGraphicsView."""
        self.graphicsView.centerOn(x, y)

    # --- Setup ---

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scene = QGraphicsScene()
        self.graphicsView = CaptureGraphicsView()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setStyleSheet(_GRAPHICS_VIEW_STYLE)
        self.graphicsView.setAlignment(Qt.AlignCenter)

        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)

        self._installStackHost(layout)
        self._setupMagnifierItem()

    def _installStackHost(self, layout: QVBoxLayout) -> None:
        self._stackHost = _StackHost()
        self.graphicsView.setParent(self._stackHost)
        self.graphicsView.setGeometry(self._stackHost.rect())

        self._hudWidget = HDUVisualizationHUDWidget(
            self.graphicsView, self._stackHost
        )
        self._hudWidget.setGeometry(self._stackHost.rect())
        self._hudWidget.raise_()

        self._stackHost.bindOverlays(self.graphicsView, self._hudWidget)
        layout.addWidget(self._stackHost, 1)

    def _setupMagnifierItem(self) -> None:
        self._magnifierItem = MagnifierGraphicsItem(
            fixedDisplaySize=127,
            initialMagnificationFactor=3.0,
        )
        self._magnifierItem.setUnitLabel(self.tr("keV"))
        self._magnifierItem.setVisible(False)
        if self._vm.showToolHints:
            self._magnifierItem.setHintLines(
                [
                    self.tr("Arrow keys: fine movement"),
                    self.tr("Scroll wheel: zoom in/out"),
                ]
            )
        self.scene.addItem(self._magnifierItem)

        if self._hudWidget is not None:
            self._hudWidget.bindMagnifier(self._magnifierItem)

    def _applyInitialToolState(self) -> None:
        self._updateActiveTool()

    # --- ViewModel binding ---

    def _bindViewModel(self) -> None:
        self._bindImageCallbacks()
        self._bindMagnifierCallbacks()
        self._bindToolCallbacks()
        self._bindGraphicsViewSignals()

    def _bindImageCallbacks(self) -> None:
        def on_image_changed():
            QMetaObject.invokeMethod(self, "updateImage", Qt.QueuedConnection)

        def on_scale_changed():
            QMetaObject.invokeMethod(self, "updateZoom", Qt.QueuedConnection)

        self._vm.add_image_changed_callback(on_image_changed)
        self._vm.add_scale_changed_callback(on_scale_changed)

    def _bindMagnifierCallbacks(self) -> None:
        def on_magnifier_state_changed():
            QMetaObject.invokeMethod(
                self, "_updateMagnifierState", Qt.QueuedConnection
            )

        def on_magnifier_position_changed():
            QMetaObject.invokeMethod(
                self, "_updateMagnifierPosition", Qt.QueuedConnection
            )

        self._vm.add_magnifier_state_changed_callback(on_magnifier_state_changed)
        self._vm.add_magnifier_position_changed_callback(
            on_magnifier_position_changed
        )

    def _bindToolCallbacks(self) -> None:
        def on_active_tool_changed():
            QMetaObject.invokeMethod(self, "_updateActiveTool", Qt.QueuedConnection)

        self._vm.add_active_tool_changed_callback(on_active_tool_changed)

    def _bindGraphicsViewSignals(self) -> None:
        self.graphicsView.pixelHovered.connect(self._onPixelHovered)
        self.graphicsView.pixelHovered.connect(self.pixelHovered)
        self.graphicsView.pixelNudgeRequested.connect(self._onPixelNudged)
        self.graphicsView.magnificationDeltaRequested.connect(
            self._vm.adjustMagnification
        )
        self.graphicsView.mouseLeft.connect(self._vm.clearPointerHover)
        self.graphicsView.boxSelectionCompleted.connect(self.boxSelectionCompleted)
        self.graphicsView.boxSelectClicked.connect(self.boxSelectClicked)

    # --- Image / zoom ---

    @Slot()
    def updateImage(self) -> None:
        """Thread-safe update of the displayed pixmap."""
        buffer = self._vm.currentBuffer

        if buffer is not None:
            height, width, channels = buffer.shape
            bytes_per_line = channels * width
            q_img = QImage(
                buffer.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(q_img.copy())
            self.pixmapItem.setPixmap(pixmap)
            self.scene.setSceneRect(0, 0, width, height)
            self.updateZoom()
            self._updateMagnifierSourceData(pixmap)
        else:
            self.pixmapItem.setPixmap(QPixmap())

    def _updateMagnifierSourceData(self, pixmap: QPixmap) -> None:
        rawData = self._vm.activeRawData
        if rawData is not None:
            kevFactor = self._vm.kevConversionFactor
            self._magnifierItem.setSourceData(
                pixmap, rawData, lambda val: val * kevFactor
            )
            if self._hudWidget is not None:
                self._hudWidget.refreshMagnifier()

    @Slot()
    def updateZoom(self) -> None:
        """Updates the graphics view transform based on scale."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            scale = self._vm.scale
            transform = QTransform()
            transform.scale(scale, scale)
            self.graphicsView.setTransform(transform)
        finally:
            QApplication.restoreOverrideCursor()

    # --- Tool / magnifier state ---

    @Slot()
    def _updateActiveTool(self) -> None:
        magnifierActive = self._vm.isMagnifierActive
        boxSelectActive = self._vm.isBoxSelectActive

        self.graphicsView.setMagnifierActive(magnifierActive)
        self.graphicsView.setBoxSelectActive(boxSelectActive)
        self._magnifierItem.setVisible(magnifierActive)
        if self._hudWidget is not None:
            self._hudWidget.setMagnifierVisible(magnifierActive)

        if magnifierActive:
            self.graphicsView.setFocus()

    @Slot()
    def _updateMagnifierState(self) -> None:
        self._magnifierItem.setMagnificationFactor(self._vm.magnificationFactor)
        if self._hudWidget is not None:
            self._hudWidget.refreshMagnifier()

    @Slot()
    def _updateMagnifierPosition(self) -> None:
        row, col = self._vm.magnifierPosition
        self._magnifierItem.setPixelPos(row, col)
        self._positionMagnifierItem(row, col)
        if self._hudWidget is not None:
            self._hudWidget.refreshMagnifier()

    def _positionMagnifierItem(self, row: int, col: int) -> None:
        imageRect = self.pixmapItem.boundingRect()
        magRect = self._magnifierItem.boundingRect()
        magWidth = magRect.width()
        magHeight = magRect.height()

        desiredX = col - (self._magnifierItem.displaySize / 2)
        desiredY = row - (magHeight / 2)

        clampedX = max(imageRect.left(), min(desiredX, imageRect.right() - magWidth))
        clampedY = max(imageRect.top(), min(desiredY, imageRect.bottom() - magHeight))

        if magWidth > imageRect.width():
            clampedX = imageRect.left()
        if magHeight > imageRect.height():
            clampedY = imageRect.top()

        self._magnifierItem.setPos(clampedX, clampedY)

    @Slot(int, int)
    def _onPixelHovered(self, row: int, col: int) -> None:
        if self._vm.isMagnifierActive:
            self._vm.setMagnifierPosition(row, col)
        else:
            self._vm.setPointerHoverPosition(row, col)

    @Slot(int, int)
    def _onPixelNudged(self, drow: int, dcol: int) -> None:
        self._vm.moveMagnifier(drow, dcol)


class _StackHost(QWidget):
    """Parent widget that keeps two stacked children at the same geometry."""

    def __init__(self) -> None:
        super().__init__()
        self._primary: Optional[QWidget] = None
        self._overlay: Optional[QWidget] = None

    def bindOverlays(self, primary: QWidget, overlay: QWidget) -> None:
        self._primary = primary
        self._overlay = overlay
        self._resync()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._resync()

    def _resync(self) -> None:
        if self._primary is not None:
            self._primary.setGeometry(self.rect())
        if self._overlay is not None:
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
