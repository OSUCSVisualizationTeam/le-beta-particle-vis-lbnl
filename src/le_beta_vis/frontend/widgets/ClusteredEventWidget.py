from typing import List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.frontend.fitsconverters import generate_cluster_thumbnail
from le_beta_vis.frontend.fitsconverters.interface import Colormap

THUMBNAIL_SIZE = 48


class ClusteredEventWidget(QWidget):
    """Displays clustered event results as a selectable list.

    Standalone widget with no dependency on RawDataView internals.
    Receives data via setResults() and emits signals for user actions.

    Signals:
        clusterSelected(int): Emitted when user clicks a cluster entry.
        classifyRequested(): Emitted when the Classify button is clicked.
        exportRequested(): Emitted when the Export button is clicked.
    """

    clusterSelected = Signal(int)
    classifyRequested = Signal()
    exportRequested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._results: List[ClusteredEventInfo] = []
        self._colormap: Optional[Colormap] = None
        self._displayKeV: bool = True
        self._kevConversion: float = 1.02857e-5
        self._initUI()

    def _initUI(self) -> None:
        """Builds the internal layout."""
        outerLayout = QVBoxLayout(self)
        outerLayout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox(self.tr("Clustered Events"))
        layout = QVBoxLayout(group)

        self._countLabel = QLabel(self.tr("No clusters found"))
        layout.addWidget(self._countLabel)

        self._listWidget = QListWidget()
        self._listWidget.setAlternatingRowColors(True)
        self._listWidget.currentRowChanged.connect(
            self._onSelectionChanged
        )
        layout.addWidget(self._listWidget)

        btnLayout = QHBoxLayout()
        self._btnClassify = QPushButton(self.tr("Classify"))
        self._btnClassify.setEnabled(False)
        self._btnClassify.clicked.connect(self.classifyRequested)
        btnLayout.addWidget(self._btnClassify)

        self._btnExport = QPushButton(self.tr("Export for Training"))
        self._btnExport.setEnabled(False)
        self._btnExport.clicked.connect(self.exportRequested)
        btnLayout.addWidget(self._btnExport)

        layout.addLayout(btnLayout)
        outerLayout.addWidget(group)

    def setColormap(self, colormap: Optional[Colormap]) -> None:
        """Sets the colormap used for thumbnail rendering.

        Args:
            colormap: Colormap enum for false-color thumbnails,
                or None for grayscale.
        """
        self._colormap = colormap

    def setDisplayEnergyInKev(self, enabled: bool) -> None:
        """Toggles energy display between keV and ADU.

        Args:
            enabled: When True, energy is shown in keV.
        """
        self._displayKeV = enabled

    def setKevConversion(self, factor: float) -> None:
        """Sets the ADU-to-keV conversion factor.

        Args:
            factor: Multiplicative factor (keV per ADU).
        """
        self._kevConversion = factor

    def setResults(self, results: List[ClusteredEventInfo]) -> None:
        """Populates the list with clustered events.

        Replaces any existing content. Generates thumbnails and
        builds list entries with summary metadata.

        Args:
            results: List of ClusteredEventInfo from extraction.
        """
        self._results = list(results)
        self._listWidget.clear()
        self._updateCountLabel()
        self._btnClassify.setEnabled(False)
        self._btnExport.setEnabled(False)

        for i, event in enumerate(results):
            item = QListWidgetItem()
            widget = self._createEntryWidget(i, event)
            item.setSizeHint(widget.sizeHint())
            self._listWidget.addItem(item)
            self._listWidget.setItemWidget(item, widget)

    def clear(self) -> None:
        """Clears the list and resets to empty state."""
        self.setResults([])

    def setSelectedIndex(self, index: int) -> None:
        """Programmatically selects a cluster entry by index.

        Args:
            index: Index to select, or -1 to deselect all.
        """
        if index < 0:
            self._listWidget.clearSelection()
            self._listWidget.setCurrentRow(-1)
        elif index < self._listWidget.count():
            self._listWidget.setCurrentRow(index)

    def _createEntryWidget(
        self, index: int, event: ClusteredEventInfo
    ) -> QWidget:
        """Creates a single list entry with thumbnail and metadata."""
        entry = QWidget()
        layout = QHBoxLayout(entry)
        layout.setContentsMargins(4, 4, 4, 4)

        thumbnail = self._createThumbnailLabel(event)
        layout.addWidget(thumbnail)

        metaLayout = QVBoxLayout()
        metaLayout.setSpacing(1)

        bb = event.boundingBox
        width = bb.right - bb.left
        height = bb.bottom - bb.top
        metaLayout.addWidget(QLabel(
            self.tr("Geometry: {w}x{h}").format(w=width, h=height)
        ))

        rel_cx = event.centerX - bb.left
        rel_cy = event.centerY - bb.top
        metaLayout.addWidget(QLabel(
            self.tr("Center: ({cx}, {cy})").format(
                cx=rel_cx, cy=rel_cy,
            )
        ))

        metaLayout.addWidget(self._createEnergyLabel(event))

        metaLayout.addWidget(QLabel(
            self.tr("Sigma: ({sx:.2f}, {sy:.2f})").format(
                sx=event.sigmaX, sy=event.sigmaY,
            )
        ))
        metaLayout.addWidget(QLabel(
            self.tr("Pixels: {count}").format(count=event.pixelCount)
        ))

        layout.addLayout(metaLayout)
        layout.setStretch(1, 1)
        return entry

    def _createEnergyLabel(
        self, event: ClusteredEventInfo
    ) -> QLabel:
        """Creates the energy label, converting to keV if enabled."""
        if self._displayKeV:
            energy_kev = event.energy * self._kevConversion
            return QLabel(
                self.tr("Energy: {energy:.4f} keV").format(
                    energy=energy_kev,
                )
            )
        return QLabel(
            self.tr("Energy: {energy:.2f} ADU").format(
                energy=event.energy,
            )
        )

    def _createThumbnailLabel(
        self, event: ClusteredEventInfo
    ) -> QLabel:
        """Generates a thumbnail QLabel from cluster data."""
        label = QLabel()
        label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)

        buffer = generate_cluster_thumbnail(
            event.data, colormap=self._colormap
        )
        height, width = buffer.shape[:2]

        if buffer.ndim == 3:
            bytes_per_line = 3 * width
            q_img = QImage(
                buffer.data, width, height, bytes_per_line,
                QImage.Format_RGB888,
            )
        else:
            q_img = QImage(
                buffer.data, width, height, width,
                QImage.Format_Grayscale8,
            )

        pixmap = QPixmap.fromImage(q_img.copy())
        pixmap = pixmap.scaled(
            THUMBNAIL_SIZE, THUMBNAIL_SIZE,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignCenter)
        return label

    def _updateCountLabel(self) -> None:
        """Updates the header showing the count of clusters."""
        count = len(self._results)
        if count == 0:
            self._countLabel.setText(self.tr("No clusters found"))
        elif count == 1:
            self._countLabel.setText(self.tr("1 cluster found"))
        else:
            self._countLabel.setText(
                self.tr("{count} clusters found").format(count=count)
            )

    @Slot(int)
    def _onSelectionChanged(self, row: int) -> None:
        """Slot for QListWidget.currentRowChanged signal."""
        has_selection = row >= 0
        self._btnClassify.setEnabled(has_selection)
        self._btnExport.setEnabled(has_selection)
        if has_selection:
            self.clusterSelected.emit(row)
