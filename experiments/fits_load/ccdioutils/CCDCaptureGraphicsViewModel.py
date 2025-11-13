from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
from PySide6.QtCore import QObject, Slot, QRectF
from PySide6.QtGui import QPixmap, QColor, QPen
from typing import List, Optional, Callable
import numpy as np

from .ClusterExtractor import ClusteredEventInfo
from .MagnifierGraphicsItem import MagnifierGraphicsItem


class CCDCaptureGraphicsViewModel(QObject):
    """
    ViewModel for managing a QGraphicsScene and its interactable items for CCD capture
    visualization.
    """

    def __init__(self, parent: QObject = None):
        """
        Initializes the CCDCaptureGraphicsViewModel.

        Sets up the QGraphicsScene and initializes attributes for managing the
        base image, clustered event bounding boxes, and the magnifier overlay.
        Defines the minimum and maximum magnification factors for the magnifier.

        Args:
            parent (QObject, optional): The parent QObject. Defaults to None.
        """
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._pixmapItem: Optional[QGraphicsPixmapItem] = None
        self._boundingBoxItems: List[QGraphicsRectItem] = list()

        # Magnifier related attributes
        self._magnifierItem: Optional[MagnifierGraphicsItem] = None
        self._magnifierVisible: bool = False
        self._currentImagePixmap: Optional[QPixmap] = None
        self._currentRawData: Optional[np.matrix] = None
        self._currentConversionFunc: Optional[Callable[[float], float]] = None
        self._imageHeightPx: int = 0
        self._minMagnificationFactor: float = 1.0
        self._maxMagnificationFactor: float = 100.0

    def scene(self) -> QGraphicsScene:
        """Returns the QGraphicsScene managed by this ViewModel."""
        return self._scene

    @Slot(QPixmap, np.matrix, object)
    def updateImage(
        self,
        pixmap: QPixmap,
        rawData: np.matrix,
        conversionFunc: Optional[Callable[[float], float]],
    ):
        """
        Updates the base image displayed in the QGraphicsScene and stores raw data and conversion
        function. If a magnifier is active, its source data is also updated.

        Args:
            pixmap (QPixmap): The QPixmap representing the image to display.
            rawData (np.matrix): The raw NumPy matrix data corresponding to the pixmap.
            conversionFunc (Optional[Callable[[float], float]]): A function to convert
                                                                  raw pixel values for display.
        """
        self._currentImagePixmap = pixmap
        self._currentRawData = rawData
        self._currentConversionFunc = conversionFunc
        self._imageHeightPx = pixmap.height()

        if self._pixmapItem:
            self._pixmapItem.setPixmap(pixmap)
        else:
            self._pixmapItem = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pixmapItem)
        self._scene.setSceneRect(self._pixmapItem.boundingRect())

        if self._magnifierItem:
            self._magnifierItem.setSourceData(pixmap, rawData, conversionFunc)

    @Slot()
    def toggleMagnifier(self):
        """
        Toggles the visibility of the magnifier.

        If the magnifier is made visible for the first time, it is initialized
        and added to the scene. Its initial position is set to (0,0).
        """
        self._magnifierVisible = not self._magnifierVisible
        if self._magnifierVisible:
            if not self._magnifierItem:
                # Initialize magnifier item if it doesn't exist
                self._magnifierItem = MagnifierGraphicsItem(
                    initialMagnificationFactor=self._minMagnificationFactor
                )
                self._scene.addItem(self._magnifierItem)
            if (
                self._currentImagePixmap is not None
                and self._currentRawData is not None
            ):
                self._magnifierItem.setSourceData(
                    self._currentImagePixmap,
                    self._currentRawData,
                    self._currentConversionFunc,
                )
            self._magnifierItem.setVisible(True)
            self._magnifierItem.setPos(0, 0)
        else:
            if self._magnifierItem:
                self._magnifierItem.setVisible(False)

    @Slot(int, int)
    def updateMagnifierPosition(self, row: int, col: int):
        """
        Updates the position of the magnifier to center on the given pixel coordinates
        and ensures the magnifier item stays within scene bounds.
        """
        if self._magnifierVisible and self._magnifierItem and self._pixmapItem:
            self._magnifierItem.setPixelPos(row, col)

            cursorSceneX = col
            cursorSceneY = row

            magnifierWidth = self._magnifierItem.boundingRect().width()
            magnifierHeight = self._magnifierItem.boundingRect().height()

            desiredX = cursorSceneX - (self._magnifierItem._displayRectSizePx / 2)
            desiredY = cursorSceneY - (magnifierHeight / 2)

            imageRect = self._pixmapItem.boundingRect()

            clampedX = min(desiredX, imageRect.right() - magnifierWidth)
            clampedX = max(clampedX, imageRect.left())

            clampedY = min(desiredY, imageRect.bottom() - magnifierHeight)
            clampedY = max(clampedY, imageRect.top())

            if magnifierWidth > imageRect.width():
                clampedX = imageRect.left()
            if magnifierHeight > imageRect.height():
                clampedY = imageRect.top()

            self._magnifierItem.setPos(clampedX, clampedY)

    @Slot(int)
    def changeMagnificationFactor(self, delta: int):
        """
        Changes the magnification factor of the magnifier's content.
        The new factor is clamped between `_minMagnificationFactor` and `_maxMagnificationFactor`.

        Args:
            delta (int): The change increment. Positive values increase zoom,
                         negative values decrease zoom.
        """
        if self._magnifierVisible and self._magnifierItem:
            currentFactor = self._magnifierItem._magnificationFactor
            newFactor = currentFactor + delta * 0.5

            newFactor = max(
                self._minMagnificationFactor,
                min(newFactor, self._maxMagnificationFactor),
            )

            self._magnifierItem.setMagnificationFactor(newFactor)

    @Slot(list)
    def updateClusteredEvents(self, clusteredEvents: List[ClusteredEventInfo]):
        """
        Updates the bounding box overlays for clustered events.
        Removes existing bounding boxes and draws new ones.
        """
        for item in self._boundingBoxItems:
            self._scene.removeItem(item)
        self._boundingBoxItems.clear()

        for event in clusteredEvents:
            boundingBox = event.boundingBox
            rectF = QRectF(
                boundingBox.left,
                boundingBox.top,
                boundingBox.right - boundingBox.left,
                boundingBox.bottom - boundingBox.top,
            )
            rectItem = QGraphicsRectItem(rectF)
            rectItem.setPen(QPen(QColor("red"), 2))
            rectItem.setBrush(QColor(0, 0, 0, 0))
            self._scene.addItem(rectItem)
            self._boundingBoxItems.append(rectItem)

    def clearOverlays(self):
        """Clears all bounding box overlays from the scene."""
        for item in self._boundingBoxItems:
            self._scene.removeItem(item)
        self._boundingBoxItems.clear()
