from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QShowEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget
from shiboken6 import isValid

from le_beta_vis.common import AnnotationOverlay
from .CaptureGraphicsView import CaptureGraphicsView
from ._HUDAnnotationOverlaysItem import _HUDAnnotationOverlaysItem
from ._HUDBoxSelectionItem import _HUDBoxSelectionItem
from ._HUDMagnifierBorderItem import _HUDMagnifierBorderItem
from .MagnifierGraphicsItem import MagnifierGraphicsItem


class HDUVisualizationHUDWidget(QGraphicsView):
    """Transparent HUD overlay drawn on top of CaptureGraphicsView.

    Its scene uses widget (screen) coordinates, so pens, fonts, and
    bounding boxes rendered here are invariant to the zoom applied to
    the underlying CaptureGraphicsView. HUD items subscribe to
    ``viewportChanged`` to reproject their source-scene geometry into
    widget space via ``mapSceneToWidget``.

    Mouse input falls through to the widget below
    (``WA_TransparentForMouseEvents``) so the HUD never steals clicks.
    """

    viewportChanged = Signal()

    def __init__(
        self,
        sourceView: CaptureGraphicsView,
        parent: Optional[QWidget] = None,
        fontScale: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._sourceView = sourceView
        self._hudScene = QGraphicsScene(self)
        self.setScene(self._hudScene)

        self._boxSelectionItem = _HUDBoxSelectionItem()
        self._boxSelectionItem.setVisible(False)
        self._hudScene.addItem(self._boxSelectionItem)
        self._boxSelectionSceneRect: Optional[QRectF] = None

        self._magnifierBorderItem = _HUDMagnifierBorderItem(fontScale=fontScale)
        self._magnifierBorderItem.setVisible(False)
        self._hudScene.addItem(self._magnifierBorderItem)
        self._magnifierItem: Optional[MagnifierGraphicsItem] = None
        self._magnifierVisible: bool = False

        self._annotationOverlaysItem = _HUDAnnotationOverlaysItem()
        self._hudScene.addItem(self._annotationOverlaysItem)
        self._annotationOverlays: List[AnnotationOverlay] = []

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: 0px;")
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(Qt.NoBrush)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setInteractive(False)
        self.setFocusPolicy(Qt.NoFocus)

        self._sourceView.viewportChanged.connect(self._onViewportChanged)

    @property
    def hudScene(self) -> QGraphicsScene:
        """HUD scene expressed in widget/screen pixels."""
        return self._hudScene

    def mapSceneToWidget(self, scenePoint: QPointF) -> QPointF:
        """Project a source-scene point into HUD widget coordinates."""
        return QPointF(self._sourceView.mapFromScene(scenePoint))

    def mapSceneRectToWidget(self, sceneRect: QRectF) -> QRectF:
        """Project a source-scene rect into HUD widget coordinates."""
        topLeft = self.mapSceneToWidget(sceneRect.topLeft())
        bottomRight = self.mapSceneToWidget(sceneRect.bottomRight())
        return QRectF(topLeft, bottomRight).normalized()

    def setBoxSelectionSceneRect(self, rect: Optional[QRectF]) -> None:
        """Store the ROI rect in source-scene coords and reproject.

        Pass ``None`` to hide the ROI.
        """
        self._boxSelectionSceneRect = QRectF(rect) if rect is not None else None
        self._reprojectBoxSelection()

    def setAnnotationOverlays(self, overlays: List[AnnotationOverlay]) -> None:
        """Replace the set of annotation overlays drawn on the HUD.

        Each overlay's bounding_box is in source-scene (FITS pixel) coordinates.
        Pass an empty list to hide all overlays.
        """
        self._annotationOverlays = list(overlays)
        self._reprojectAnnotationOverlays()

    def setBoxSelectionColor(self, color: str) -> None:
        self._boxSelectionItem.setColor(color)

    def setBoxSelectionBorderWidth(self, width: int) -> None:
        self._boxSelectionItem.setBorderWidth(width)

    def bindMagnifier(
        self, magnifier: Optional[MagnifierGraphicsItem]
    ) -> None:
        """Associate the scene magnifier item for HUD chrome rendering."""
        self._magnifierItem = magnifier
        self._reprojectMagnifier()

    def setMagnifierVisible(self, visible: bool) -> None:
        """Show or hide the HUD magnifier border + labels."""
        self._magnifierVisible = visible
        self._reprojectMagnifier()

    def refreshMagnifier(self) -> None:
        """Re-read magnifier state and repaint HUD chrome.

        Call this when the magnifier position, magnification factor,
        source data, hints, or unit label change.
        """
        self._reprojectMagnifier()

    def _reprojectMagnifier(self) -> None:
        if (
            not self._magnifierVisible
            or self._magnifierItem is None
            or not isValid(self._magnifierItem)
            or not self._magnifierItem.hasSource
        ):
            self._magnifierBorderItem.setState(
                None, "", 1.0, (0.0, 0.0, 0.0), []
            )
            return
        item = self._magnifierItem
        displaySize = item.displaySize
        pos = item.pos()
        sceneRect = QRectF(
            pos.x(), pos.y(), displaySize, displaySize
        )
        widgetRect = self.mapSceneRectToWidget(sceneRect)
        figures = item.computeCurrentFigures()
        self._magnifierBorderItem.setState(
            widgetRect,
            item.unitLabel,
            item.magnificationFactor,
            figures,
            item.hintLines,
        )

    def _reprojectAnnotationOverlays(self) -> None:
        widgetRects = [
            self.mapSceneRectToWidget(
                QRectF(
                    o.bounding_box.left,
                    o.bounding_box.top,
                    o.bounding_box.right - o.bounding_box.left,
                    o.bounding_box.bottom - o.bounding_box.top,
                )
            )
            for o in self._annotationOverlays
        ]
        self._annotationOverlaysItem.setWidgetRects(widgetRects)

    def _reprojectBoxSelection(self) -> None:
        if self._boxSelectionSceneRect is None:
            self._boxSelectionItem.setWidgetRect(None)
            return
        widgetRect = self.mapSceneRectToWidget(self._boxSelectionSceneRect)
        w = int(round(self._boxSelectionSceneRect.width()))
        h = int(round(self._boxSelectionSceneRect.height()))
        self._boxSelectionItem.setWidgetRect(widgetRect, f"{w} x {h}")

    def _onViewportChanged(self) -> None:
        self._syncSceneRect()
        self._reprojectBoxSelection()
        self._reprojectMagnifier()
        self._reprojectAnnotationOverlays()
        self.viewportChanged.emit()

    def _syncSceneRect(self) -> None:
        viewportSize = self._sourceView.viewport().size()
        rect = QRectF(
            0.0,
            0.0,
            float(viewportSize.width()),
            float(viewportSize.height()),
        )
        self._hudScene.setSceneRect(rect)
        self.setSceneRect(rect)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._syncSceneRect()
