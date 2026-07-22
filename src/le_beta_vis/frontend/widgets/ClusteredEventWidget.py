from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.ClassifierService import ClusterScores
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.ParticleType import CLASSIFICATION_THRESHOLD, ParticleType
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)

THUMBNAIL_SIZE = 64


class ClusteredEventWidget(QWidget):
    """Displays clustered event results as a selectable list.

    Standalone widget with no dependency on RawDataView internals.
    Receives data via setResults() and emits signals for user actions.

    Signals:
        clustersSelected(list): Emitted when the selection changes;
            carries a sorted list of selected row indices.
        classifyRequested(): Emitted when the Classify button is clicked.
        exportRequested(): Emitted when the Export button is clicked.
    """

    clustersSelected = Signal(list)
    classifyRequested = Signal()
    exportRequested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._results: List[ClusteredEventInfo] = []
        self._colormap: Optional[Colormap] = None
        self._displayKeV: bool = True
        self._kevConversion: float = 1.02857e-5
        self._classification_scores: Dict[int, ClusterScores] = {}
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
        self._listWidget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._listWidget.itemSelectionChanged.connect(self._onSelectionChanged)
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

        Replaces any existing content. Clears any prior classification scores
        so stale badges do not appear on the new result set.

        Args:
            results: List of ClusteredEventInfo from extraction.
        """
        self._results = list(results)
        self._classification_scores = {}
        self._rebuildRows()

    def updateClassificationResults(
        self, scores: Dict[int, ClusterScores]
    ) -> None:
        """Overlays ML classification scores on the existing cluster rows.

        Rebuilds the list so each row gains CNN/NRG/BDT score labels and a
        particle-type badge. Call after a classification dialog closes with
        results; no-op when *scores* is empty.

        Args:
            scores: Per-cluster scores keyed by cluster list index.
        """
        if not scores:
            return
        self._classification_scores = dict(scores)
        self._rebuildRows()

    def clear(self) -> None:
        """Clears the list and resets to empty state."""
        self.setResults([])

    def _rebuildRows(self) -> None:
        """Rebuilds QListWidget rows from the current results and scores."""
        self._listWidget.clear()
        self._updateCountLabel()
        self._btnClassify.setEnabled(False)
        self._btnExport.setEnabled(False)

        for i, event in enumerate(self._results):
            item = QListWidgetItem()
            widget = self._createEntryWidget(i, event)
            item.setSizeHint(widget.sizeHint())
            self._listWidget.addItem(item)
            self._listWidget.setItemWidget(item, widget)

    def setSelectedIndices(self, indices: List[int]) -> None:
        """Programmatically sets the multi-selection from a list of indices.

        Uses blockSignals to suppress itemSelectionChanged during the update,
        preventing a re-notification loop back to the ViewModel.

        Args:
            indices: Zero-based row indices to select.
                Pass an empty list to deselect all.
        """
        self._listWidget.blockSignals(True)
        try:
            self._listWidget.clearSelection()
            for index in indices:
                if 0 <= index < self._listWidget.count():
                    item = self._listWidget.item(index)
                    if item is not None:
                        item.setSelected(True)
        finally:
            self._listWidget.blockSignals(False)
        count = len(indices)
        self._btnClassify.setEnabled(count > 0)
        self._btnExport.setEnabled(count > 0)

    def setSelectedIndex(self, index: int) -> None:
        """Backward-compat shim — delegates to setSelectedIndices.

        Args:
            index: Index to select, or any negative value to deselect all.
        """
        self.setSelectedIndices([] if index < 0 else [index])

    def _createEntryWidget(self, index: int, event: ClusteredEventInfo) -> QWidget:
        """Creates a single list entry with thumbnail and metadata."""
        entry = QWidget()
        entry.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        entry.setProperty("class", "entry")
        layout = QHBoxLayout(entry)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        thumbnail = self._createThumbnailLabel(event)
        layout.addWidget(thumbnail)

        metaLayout = QVBoxLayout()
        metaLayout.setSpacing(1)

        bb = event.boundingBox
        width = bb.right - bb.left
        height = bb.bottom - bb.top
        metaLayout.addWidget(
            QLabel(self.tr("Geometry: {w}x{h}").format(w=width, h=height))
        )

        rel_cx = event.centerX - bb.left
        rel_cy = event.centerY - bb.top
        metaLayout.addWidget(
            QLabel(
                self.tr("Center: ({cx}, {cy})").format(
                    cx=rel_cx,
                    cy=rel_cy,
                )
            )
        )

        metaLayout.addWidget(self._createEnergyLabel(event))

        sigma_label = QLabel(
            self.tr(
                "\u03c3<sub>x</sub> = {sx:.2f}," " \u03c3<sub>y</sub> = {sy:.2f}"
            ).format(sx=event.sigmaX, sy=event.sigmaY)
        )
        metaLayout.addWidget(sigma_label)
        metaLayout.addWidget(
            QLabel(self.tr("Pixels: {count}").format(count=event.pixelCount))
        )

        if index in self._classification_scores:
            self._appendScoreLabels(metaLayout, self._classification_scores[index])

        layout.addLayout(metaLayout)
        layout.setStretch(1, 1)
        return entry

    def _appendScoreLabels(
        self, layout: QVBoxLayout, scores: ClusterScores
    ) -> None:
        """Appends CNN/NRG/BDT score rows and a particle badge to *layout*."""

        def _fmt(v: Optional[float]) -> str:
            return f"{v * 100:.0f}%" if v is not None else "?"

        def _level(v: Optional[float]) -> str:
            if v is None:
                return "low"
            if v >= CLASSIFICATION_THRESHOLD:
                return "good"
            if v >= 0.5:
                return "medium"
            return "low"

        for model, val in (
            ("CNN", scores.cnn),
            ("NRG", scores.nrg),
            ("BDT", scores.bdt),
        ):
            lbl = QLabel(
                self.tr("{model}: <b>{score}</b>").format(
                    model=model, score=_fmt(val)
                )
            )
            lbl.setProperty("scoreLevel", _level(val))
            layout.addWidget(lbl)

        valid = [v for v in (scores.cnn, scores.nrg, scores.bdt) if v is not None]
        particle = (
            ParticleType.TRITIUM
            if valid and max(valid) >= CLASSIFICATION_THRESHOLD
            else ParticleType.UNCLASSIFIED
        )
        badge = QLabel(
            self.tr("Type: {symbol}").format(symbol=particle.symbol)
        )
        layout.addWidget(badge)

    def _createEnergyLabel(self, event: ClusteredEventInfo) -> QLabel:
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

    def _createThumbnailLabel(self, event: ClusteredEventInfo) -> EnergyClusterWidget:
        """Generates a thumbnail widget from cluster data."""
        widget = EnergyClusterWidget(size=THUMBNAIL_SIZE, parent=self)
        widget.setCluster(event.data, self._colormap)
        return widget

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

    @Slot()
    def _onSelectionChanged(self) -> None:
        """Slot for QListWidget.itemSelectionChanged signal."""
        selected_rows = sorted(
            self._listWidget.row(item) for item in self._listWidget.selectedItems()
        )
        count = len(selected_rows)
        self._btnClassify.setEnabled(count > 0)
        self._btnExport.setEnabled(count > 0)
        if count > 0:
            self.clustersSelected.emit(selected_rows)
