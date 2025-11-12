from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
from PySide6.QtCore import QObject, Slot, QRectF
from PySide6.QtGui import QPixmap, QColor, QPen
from typing import List, Optional

from .ClusterExtractor import ClusteredEventInfo


class CCDCaptureGraphicsViewModel(QObject):
    """
    ViewModel for managing a QGraphicsScene and its interactable items for CCD capture
    visualization.
    """

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._pixmapItem: Optional[QGraphicsPixmapItem] = None
        self._boundingBoxItems: List[QGraphicsRectItem] = list()

    def scene(self) -> QGraphicsScene:
        """Returns the QGraphicsScene managed by this ViewModel."""
        return self._scene

    @Slot(QPixmap)
    def updateImage(self, pixmap: QPixmap):
        """
        Updates the base image displayed in the QGraphicsScene.
        """
        if self._pixmapItem:
            self._pixmapItem.setPixmap(pixmap)
        else:
            self._pixmapItem = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pixmapItem)
        self._scene.setSceneRect(self._pixmapItem.boundingRect())

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
            bbox = event.boundingBox
            rect = QRectF(
                bbox.left, bbox.top, bbox.right - bbox.left, bbox.bottom - bbox.top
            )
            rectItem = QGraphicsRectItem(rect)
            rectItem.setPen(QPen(QColor("red"), 2))
            rectItem.setBrush(QColor(0, 0, 0, 0))
            self._scene.addItem(rectItem)
            self._boundingBoxItems.append(rectItem)

    def clearOverlays(self):
        """Clears all bounding box overlays from the scene."""
        for item in self._boundingBoxItems:
            self._scene.removeItem(item)
        self._boundingBoxItems.clear()
