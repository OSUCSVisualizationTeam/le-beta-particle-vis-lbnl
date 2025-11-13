from PySide6.QtWidgets import QGraphicsItem, QWidget, QStyleOptionGraphicsItem
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont
from PySide6.QtCore import QRectF, QPoint, Qt
import numpy as np
from typing import Optional, Callable, Tuple


class MagnifierGraphicsItem(QGraphicsItem):
    """
    A custom QGraphicsItem that displays a magnified view of a portion of a source QPixmap
    and shows min/max/central pixel values.
    """

    def __init__(
        self,
        fixedDisplaySize: int = 127,
        initialMagnificationFactor: float = 3.0,
        conversionFunc: Optional[Callable[[float], float]] = None,
        parent: QGraphicsItem = None,
    ):
        """
        Initializes the MagnifierGraphicsItem.

        Args:
            fixedDisplaySize (int, optional): The fixed side length in pixels for the
                                              square display area of the magnifier. Defaults to 127.
            initialMagnificationFactor (float, optional): The initial zoom level for
                                                          the content inside the magnifier. Defaults to 3.0.
            conversionFunc (Optional[Callable[[float], float]], optional): A function
                                                                           to apply to raw pixel values
                                                                           before displaying them in labels.
                                                                           Defaults to None.
            parent (QGraphicsItem, optional): The parent QGraphicsItem. Defaults to None.
        """
        super().__init__(parent)
        self._sourcePixmap: Optional[QPixmap] = None
        self._sourceRawData: Optional[np.matrix] = None
        self._currentPixelPos: QPoint = QPoint(-1, -1)
        self._displayRectSizePx = fixedDisplaySize
        self._magnificationFactor: float = initialMagnificationFactor
        self._minMagnifierEffectiveSidePx: int = 9
        self._conversionFunc = conversionFunc

        self._labelWidth: int = 120
        self._labelHeight: int = 60
        self._labelPadding: int = 10

        self.setZValue(100)

    def setSourceData(
        self,
        pixmap: QPixmap,
        rawData: np.matrix,
        conversionFunc: Optional[Callable[[float], float]],
    ):
        """
        Sets the source QPixmap, raw data, and conversion function for the magnifier.

        Args:
            pixmap (QPixmap): The QPixmap of the full image.
            rawData (np.matrix): The raw NumPy matrix data corresponding to the pixmap.
            conversionFunc (Optional[Callable[[float], float]]): A function to convert
                                                                  raw pixel values for display.
        """
        self._sourcePixmap = pixmap
        self._sourceRawData = rawData
        self._conversionFunc = conversionFunc
        self.prepareGeometryChange()
        self.update()

    def setPixelPos(self, row: int, col: int):
        """Sets the target pixel position (row, col) for the magnifier's center."""
        if self._sourcePixmap is None or self._sourceRawData is None:
            return

        maxRow, maxCol = self._sourceRawData.shape
        self._currentPixelPos = QPoint(
            max(0, min(col, maxCol - 1)), max(0, min(row, maxRow - 1))
        )
        self.prepareGeometryChange()
        self.update()

    def setMagnificationFactor(self, factor: float):
        """Sets the magnification factor for the content inside the magnifier."""
        self._magnificationFactor = factor
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        """
        Returns the bounding rectangle of the magnifier, including space for labels.
        """
        if self._sourcePixmap is None:
            return QRectF()

        totalWidth = self._displayRectSizePx + self._labelPadding + self._labelWidth
        totalHeight = max(self._displayRectSizePx, self._labelHeight)

        return QRectF(0, 0, totalWidth, totalHeight)

    def _calculateSourceRect(self) -> QRectF:
        """
        Calculates the source rectangle from the original image to be magnified.
        This rectangle defines the portion of the source image that will be
        displayed in the magnifier. It includes logic for:
        - Ensuring a minimum effective side (e.g., 9x9 pixels).
        - Clamping the source rectangle to stay within the bounds of the original image.

        Returns:
            QRectF: The rectangle in source image coordinates to be magnified.
        """

        effectiveSourceSide = self._displayRectSizePx / self._magnificationFactor

        effectiveSourceSide = max(
            effectiveSourceSide, self._minMagnifierEffectiveSidePx
        )

        halfEffectiveSide = effectiveSourceSide / 2.0

        sourceX = self._currentPixelPos.x() - halfEffectiveSide
        sourceY = self._currentPixelPos.y() - halfEffectiveSide

        imgWidth = self._sourcePixmap.width()
        imgHeight = self._sourcePixmap.height()

        if sourceX < 0:
            sourceX = 0
        if sourceY < 0:
            sourceY = 0

        if sourceX + effectiveSourceSide > imgWidth:
            sourceX = imgWidth - effectiveSourceSide
            if sourceX < 0:
                sourceX = 0
        if sourceY + effectiveSourceSide > imgHeight:
            sourceY = imgHeight - effectiveSourceSide
            if sourceY < 0:
                sourceY = 0

        return QRectF(sourceX, sourceY, effectiveSourceSide, effectiveSourceSide)

    def _drawMagnifiedImage(self, painter: QPainter, sourceRect: QRectF):
        """Draws the magnified image and its border."""
        targetRect = QRectF(0, 0, self._displayRectSizePx, self._displayRectSizePx)
        painter.drawPixmap(targetRect, self._sourcePixmap, sourceRect)

        painter.setPen(QPen(QColor("blue"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(targetRect)

    def _computeFigures(
        self, magnifiedDataView: np.matrix
    ) -> Tuple[float, float, float]:
        """
        Computes the min, max, and central pixel values for the magnified view,
        applying the conversion function if available.

        Args:
            magnifiedDataView (np.matrix): The numpy subarray representing the
                                           magnified region of the raw data.

        Returns:
            Tuple[float, float, float]: A tuple containing (minVal, maxVal, centralVal).
        """
        minVal = np.nan
        maxVal = np.nan
        centralVal = np.nan

        if magnifiedDataView.size > 0:
            if self._conversionFunc is not None:
                convertedView = np.vectorize(self._conversionFunc)(magnifiedDataView)
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

    def _drawLabels(self, painter: QPainter, sourceRect: QRectF):
        """
        Draws the translucent background and the text labels (min, max, central value)
        for the magnified region, including "keV" units.
        """
        labelX = self._displayRectSizePx + self._labelPadding
        labelY = 0

        metrics = painter.fontMetrics()
        lineHeight = metrics.height() + 2

        labelBgHeight = 3 * lineHeight + 4
        labelBgRect = QRectF(labelX - 4, labelY, self._labelWidth + 4, labelBgHeight)

        painter.fillRect(labelBgRect, QColor(0, 0, 0, int(255 * 0.8)))

        srcXInt = int(sourceRect.x())
        srcYInt = int(sourceRect.y())
        srcWidthInt = int(sourceRect.width())
        srcHeightInt = int(sourceRect.height())

        imgWidth = self._sourcePixmap.width()
        imgHeight = self._sourcePixmap.height()
        srcXInt = max(0, srcXInt)
        srcYInt = max(0, srcYInt)
        srcWidthInt = min(srcWidthInt, imgWidth - srcXInt)
        srcHeightInt = min(srcHeightInt, imgHeight - srcYInt)

        minVal = np.nan
        maxVal = np.nan
        centralVal = np.nan

        if srcWidthInt > 0 and srcHeightInt > 0:
            magnifiedDataView = self._sourceRawData[
                srcYInt : srcYInt + srcHeightInt,
                srcXInt : srcXInt + srcWidthInt,
            ]
            minVal, maxVal, centralVal = self._computeFigures(magnifiedDataView)

        painter.setPen(QPen(QColor("white")))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(labelX, labelY + lineHeight, f"Min: {minVal:.2e} keV")
        painter.drawText(labelX, labelY + 2 * lineHeight, f"Max: {maxVal:.2e} keV")
        painter.drawText(labelX, labelY + 3 * lineHeight, f"Val: {centralVal:.2e} keV")

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ):
        """
        Paints the magnified view and associated labels.
        """
        if (
            self._sourcePixmap is None
            or self._sourceRawData is None
            or self._currentPixelPos.x() == -1
        ):
            return

        sourceRect = self._calculateSourceRect()
        self._drawMagnifiedImage(painter, sourceRect)
        self._drawLabels(painter, sourceRect)
