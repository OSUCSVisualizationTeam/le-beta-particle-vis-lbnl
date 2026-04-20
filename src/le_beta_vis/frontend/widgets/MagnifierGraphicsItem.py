from typing import Callable, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget


class MagnifierGraphicsItem(QGraphicsItem):
    """
    A QGraphicsItem that displays a magnified view of a source QPixmap
    region. Border, value labels, and hint lines render in the HUD
    layer so they remain zoom-invariant; this item only draws the
    magnified pixmap content in scene space.
    """

    def __init__(
        self,
        fixedDisplaySize: int = 127,
        initialMagnificationFactor: float = 3.0,
        conversionFunc: Optional[Callable[[float], float]] = None,
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        Initializes the MagnifierGraphicsItem.

        Args:
            fixedDisplaySize: Side length in pixels for the display area.
            initialMagnificationFactor: Initial zoom level.
            conversionFunc: Optional function to convert raw pixel values
                before displaying them in labels.
            parent: The parent QGraphicsItem.
        """
        super().__init__(parent)
        self._sourcePixmap: Optional[QPixmap] = None
        self._sourceRawData: Optional[np.ndarray] = None
        self._currentPixelPos: QPoint = QPoint(-1, -1)
        self._displayRectSizePx = fixedDisplaySize
        self._magnificationFactor: float = initialMagnificationFactor
        self._minMagnifierEffectiveSidePx: int = 9
        self._conversionFunc = conversionFunc
        self._unitLabel: str = "keV"
        self._hintLines: List[str] = []

        self.setZValue(100)

    @property
    def displaySize(self) -> int:
        """Returns the fixed side length of the magnifier display area."""
        return self._displayRectSizePx

    @property
    def unitLabel(self) -> str:
        """Unit string displayed next to pixel values (e.g., 'keV')."""
        return self._unitLabel

    @property
    def hintLines(self) -> List[str]:
        """Hint strings displayed by the HUD below the value labels."""
        return list(self._hintLines)

    @property
    def magnificationFactor(self) -> float:
        """Current magnification factor."""
        return self._magnificationFactor

    @property
    def hasSource(self) -> bool:
        """True when both source pixmap and raw data are set."""
        return (
            self._sourcePixmap is not None
            and self._sourceRawData is not None
            and self._currentPixelPos.x() >= 0
        )

    def computeCurrentFigures(self) -> Tuple[float, float, float]:
        """Returns (min, max, central) for the current magnified region."""
        if not self.hasSource:
            return np.nan, np.nan, np.nan
        sourceRect = self._calculateSourceRect()
        data = self._extractMagnifiedData(sourceRect)
        if data is None:
            return np.nan, np.nan, np.nan
        return self._computeFigures(data)

    def setUnitLabel(self, label: str) -> None:
        """
        Sets the unit label displayed alongside pixel values.

        Args:
            label: The unit string (e.g., 'keV').
        """
        self._unitLabel = label

    def setHintLines(self, lines: List[str]) -> None:
        """
        Sets the hint lines displayed below the value labels.

        Args:
            lines: List of hint strings to display.
        """
        self._hintLines = lines
        self.prepareGeometryChange()
        self.update()

    def setSourceData(
        self,
        pixmap: QPixmap,
        rawData: np.ndarray,
        conversionFunc: Optional[Callable[[float], float]],
    ) -> None:
        """
        Sets the source QPixmap, raw data, and conversion function.

        Args:
            pixmap: The QPixmap of the full image.
            rawData: The raw NumPy array data corresponding to the pixmap.
            conversionFunc: A function to convert raw pixel values for display.
        """
        self._sourcePixmap = pixmap
        self._sourceRawData = rawData
        self._conversionFunc = conversionFunc
        self.prepareGeometryChange()
        self.update()

    def setPixelPos(self, row: int, col: int) -> None:
        """
        Sets the target pixel position for the magnifier's center.

        Args:
            row: The row (y) coordinate in the source image.
            col: The column (x) coordinate in the source image.
        """
        if self._sourcePixmap is None or self._sourceRawData is None:
            return

        maxRow, maxCol = self._sourceRawData.shape
        self._currentPixelPos = QPoint(
            max(0, min(col, maxCol - 1)), max(0, min(row, maxRow - 1))
        )
        self.prepareGeometryChange()
        self.update()

    def setMagnificationFactor(self, factor: float) -> None:
        """
        Sets the magnification factor for the magnified content.

        Args:
            factor: The magnification level.
        """
        self._magnificationFactor = factor
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle of the magnified display area.

        Border, labels and hints render in the HUD layer, so the item
        itself only covers the magnified pixmap region.
        """
        if self._sourcePixmap is None:
            return QRectF()
        return QRectF(
            0, 0, self._displayRectSizePx, self._displayRectSizePx
        )

    def _calculateSourceRect(self) -> QRectF:
        """
        Calculates the source rectangle to be magnified, clamped
        to stay within the bounds of the source image.
        """
        effectiveSourceSide = (
            self._displayRectSizePx / self._magnificationFactor
        )
        effectiveSourceSide = max(
            effectiveSourceSide, self._minMagnifierEffectiveSidePx
        )

        halfSide = effectiveSourceSide / 2.0
        sourceX = self._currentPixelPos.x() - halfSide
        sourceY = self._currentPixelPos.y() - halfSide

        imgWidth = self._sourcePixmap.width()
        imgHeight = self._sourcePixmap.height()

        sourceX = max(0, sourceX)
        sourceY = max(0, sourceY)

        if sourceX + effectiveSourceSide > imgWidth:
            sourceX = max(0, imgWidth - effectiveSourceSide)
        if sourceY + effectiveSourceSide > imgHeight:
            sourceY = max(0, imgHeight - effectiveSourceSide)

        return QRectF(
            sourceX, sourceY,
            effectiveSourceSide, effectiveSourceSide,
        )

    def _drawMagnifiedImage(
        self, painter: QPainter, sourceRect: QRectF
    ) -> None:
        """Draws the magnified image region. Border is rendered in HUD."""
        targetRect = QRectF(
            0, 0, self._displayRectSizePx, self._displayRectSizePx
        )
        painter.drawPixmap(targetRect, self._sourcePixmap, sourceRect)

    def _computeFigures(
        self, magnifiedDataView: np.ndarray
    ) -> Tuple[float, float, float]:
        """
        Computes min, max, and central pixel values for the magnified view,
        applying the conversion function if available.

        Args:
            magnifiedDataView: Numpy subarray of the magnified region.

        Returns:
            Tuple of (minVal, maxVal, centralVal).
        """
        minVal = np.nan
        maxVal = np.nan
        centralVal = np.nan

        if magnifiedDataView.size > 0:
            if self._conversionFunc is not None:
                convertedView = np.vectorize(self._conversionFunc)(
                    magnifiedDataView
                )
                minVal = np.min(convertedView)
                maxVal = np.max(convertedView)
                centralVal = self._conversionFunc(
                    self._sourceRawData[
                        self._currentPixelPos.y(), self._currentPixelPos.x()
                    ]
                )
            else:
                minVal = np.min(magnifiedDataView)
                maxVal = np.max(magnifiedDataView)
                centralVal = self._sourceRawData[
                    self._currentPixelPos.y(), self._currentPixelPos.x()
                ]
        return minVal, maxVal, centralVal

    def _extractMagnifiedData(
        self, sourceRect: QRectF
    ) -> Optional[np.ndarray]:
        """
        Extracts the raw data subarray corresponding to the source rect.

        Args:
            sourceRect: The rectangle in source image coordinates.

        Returns:
            The numpy subarray, or None if dimensions are invalid.
        """
        srcX = max(0, int(sourceRect.x()))
        srcY = max(0, int(sourceRect.y()))
        srcW = int(sourceRect.width())
        srcH = int(sourceRect.height())

        imgW = self._sourcePixmap.width()
        imgH = self._sourcePixmap.height()
        srcW = min(srcW, imgW - srcX)
        srcH = min(srcH, imgH - srcY)

        if srcW <= 0 or srcH <= 0:
            return None
        return self._sourceRawData[srcY: srcY + srcH, srcX: srcX + srcW]

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paints the magnified pixmap region in scene space."""
        if not self.hasSource:
            return
        sourceRect = self._calculateSourceRect()
        self._drawMagnifiedImage(painter, sourceRect)
