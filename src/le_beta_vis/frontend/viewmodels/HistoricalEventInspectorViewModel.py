"""ViewModel for the Historical Event Inspector panel.

Pure Python — no Qt dependencies — so it can run in headless CI.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.HistogramRenderer import (
    HistogramRenderer,
    MatplotlibHistogramRenderer,
)
from le_beta_vis.common.ParticleType import (
    CLASSIFICATION_THRESHOLD,
    classify_particle,
)
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)


@dataclass(frozen=True)
class ClusterDisplayData:
    """Structured cluster data for display — no HTML, no labels.

    The ViewModel computes all values; the View is responsible for
    rendering them into a presentable format (HTML, plain text, etc.)
    with translatable labels via ``tr()``.
    """

    particle_symbol: str
    particle_name: str
    cnn_pct: str
    cnn_css: str
    nrg_pct: str
    nrg_css: str
    bdt_pct: str
    bdt_css: str
    cluster_id: str
    fits_filename: Optional[str]
    energy: str
    sigma_x: float
    sigma_y: float
    geometry: str
    center: str
    pixels: int
    date: Optional[str]


def _score_css(score: float, threshold: float) -> str:
    """Returns an inline CSS color string for a confidence score.

    Args:
        score: Model confidence (0.0–1.0).
        threshold: Minimum confidence for a "positive" result.

    Returns:
        CSS color string: green (>= threshold), yellow (>= 0.5),
        or gray (below 0.5).
    """
    if score >= threshold:
        return "color: #27ae60; font-weight: bold;"
    if score >= 0.5:
        return "color: #f39c12; font-weight: bold;"
    return "color: #7f8c8d; font-weight: bold;"



class HistoricalEventInspectorViewModel:
    """Pure Python ViewModel for the event detail inspector.

    Computes display-ready values from cluster data and manages
    display settings (threshold, keV toggle).  Follows the same
    observer pattern as ``HistoricalViewModel``.
    """

    def __init__(
        self,
        physics: Optional[PhysicsConversionManager] = None,
        threshold: float = CLASSIFICATION_THRESHOLD,
        displayKeV: bool = True,
        histogramRenderer: Optional[HistogramRenderer] = None,
    ):
        self._cluster: Optional[Cluster] = None
        self._physics = physics
        self._threshold = threshold
        self._displayKeV = displayKeV
        self._renderer: HistogramRenderer = (
            histogramRenderer or MatplotlibHistogramRenderer()
        )
        self._on_event_changed: List[Callable[[Optional[Cluster]], None]] = []

    # --- Properties ---

    @property
    def cluster(self) -> Optional[Cluster]:
        """The currently inspected cluster, or None."""
        return self._cluster

    @property
    def threshold(self) -> float:
        """Classification confidence threshold."""
        return self._threshold

    @property
    def displayKeV(self) -> bool:
        """Whether energy values display in keV."""
        return self._displayKeV

    @property
    def renderer(self) -> HistogramRenderer:
        """The histogram rendering service."""
        return self._renderer

    @property
    def physics(self) -> Optional[PhysicsConversionManager]:
        """The physics conversion manager, or None."""
        return self._physics

    # --- Commands ---

    def setEvent(self, cluster: Optional[Cluster]) -> None:
        """Sets the cluster to inspect and notifies observers.

        Args:
            cluster: The cluster to display, or None to clear.
        """
        self._cluster = cluster
        self._notify_event_changed()

    def setThreshold(self, threshold: float) -> None:
        """Updates the classification confidence threshold.

        Args:
            threshold: New threshold value (0.0–1.0).
        """
        self._threshold = threshold

    def setDisplayKeV(self, enabled: bool) -> None:
        """Toggles keV vs ADU energy display.

        Args:
            enabled: True for keV, False for raw ADU.
        """
        self._displayKeV = enabled

    # --- Formatting ---

    def formatClusterData(self, cluster: Cluster) -> ClusterDisplayData:
        """Extracts display-ready values from a cluster.

        All computation (classification, energy conversion, geometry)
        happens here.  The returned dataclass carries no HTML and no
        user-facing labels, so the View can render it with
        translatable ``tr()`` strings.

        Args:
            cluster: The cluster whose details to format.

        Returns:
            A frozen ``ClusterDisplayData`` instance.
        """
        particle_type, _ = classify_particle(cluster, self._threshold)
        energy = self._formatEnergy(cluster)
        geometry = self._formatGeometry(cluster)
        center = self._formatCenter(cluster)
        cluster_id = (
            str(cluster.clusterId) if cluster.clusterId is not None else "N/A"
        )

        return ClusterDisplayData(
            particle_symbol=particle_type.symbol,
            particle_name=particle_type.display_name,
            cnn_pct=f"{cluster.cnnClassification * 100:.1f}%",
            cnn_css=_score_css(cluster.cnnClassification, self._threshold),
            nrg_pct=f"{cluster.nrgClassification * 100:.1f}%",
            nrg_css=_score_css(cluster.nrgClassification, self._threshold),
            bdt_pct=f"{cluster.bdtClassification * 100:.1f}%",
            bdt_css=_score_css(cluster.bdtClassification, self._threshold),
            cluster_id=cluster_id,
            fits_filename=cluster.fitsFilename,
            energy=energy,
            sigma_x=cluster.sigmaX,
            sigma_y=cluster.sigmaY,
            geometry=geometry,
            center=center,
            pixels=cluster.pixelCount,
            date=cluster.date,
        )

    def _formatEnergy(self, cluster: Cluster) -> str:
        """Formats the energy value as keV + ADU or ADU-only."""
        if self._physics and self._displayKeV:
            energy_kev = self._physics.adu_to_kev(cluster.energy)
            return f"{energy_kev:.4f} keV ({cluster.energy:.0f} ADU)"
        return f"{cluster.energy:.2f} ADU"

    def _formatGeometry(self, cluster: Cluster) -> str:
        """Formats the bounding box as W×H."""
        bb = cluster.boundingBox
        w = abs(bb.right - bb.left)
        h = abs(bb.bottom - bb.top)
        return f"{w}\u00d7{h}"

    def _formatCenter(self, cluster: Cluster) -> str:
        """Formats the relative center within the bounding box."""
        if cluster.centerX is not None and cluster.centerY is not None:
            rel_cx = cluster.centerX - cluster.boundingBox.left
            rel_cy = cluster.centerY - cluster.boundingBox.top
            return f"({rel_cx}, {rel_cy})"
        return "N/A"

    def formatHistogramXLabel(self, cluster: Cluster) -> str:
        """Returns the x-axis label for the energy histogram.

        Args:
            cluster: The cluster (unused now, reserved for future).

        Returns:
            ``"Energy (keV)"`` or ``"Energy (ADU)"``.
        """
        if self._physics and self._displayKeV:
            return "Energy (keV)"
        return "Energy (ADU)"

    # --- Observer pattern ---

    def add_event_changed_callback(
        self, callback: Callable[[Optional[Cluster]], None]
    ) -> None:
        """Registers a callback fired when the inspected event changes.

        Args:
            callback: Called with the new Cluster or None.
        """
        self._on_event_changed.append(callback)

    # --- Private ---

    def _notify_event_changed(self) -> None:
        for cb in self._on_event_changed:
            cb(self._cluster)
