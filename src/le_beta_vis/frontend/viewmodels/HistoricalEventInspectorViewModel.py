"""ViewModel for the Historical Event Inspector panel.

Pure Python — no Qt dependencies — so it can run in headless CI.
"""
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


# TODO: The embedded English labels ("Energy:", "Geometry:", etc.)
# are not translatable because this VM is pure Python and cannot
# use tr().  When full i18n support is needed, the label strings
# should be passed as parameters from the View (which has access
# to tr()).
HTML_TEMPLATE = """\
<div>
  <span style="font-size: 16px; font-weight: bold;">\
{particle_symbol} &mdash; {particle_name}</span>
  <br/>
  <table style="margin-top: 6px;">
    <tr>
      <td>CNN:</td>
      <td style="{cnn_css}">{cnn_pct}</td>
    </tr>
    <tr>
      <td>NRG:</td>
      <td style="{nrg_css}">{nrg_pct}</td>
    </tr>
    <tr>
      <td>BDT:</td>
      <td style="{bdt_css}">{bdt_pct}</td>
    </tr>
  </table>
  <hr/>
  <table style="margin-top: 4px;">
    <tr><td><b>Cluster ID:</b></td><td>{cluster_id}</td></tr>
    <tr><td><b>FITS File:</b></td><td>{fits_filename}</td></tr>
    <tr><td><b>Energy:</b></td><td>{energy}</td></tr>
    <tr>\
<td><b>&sigma; spread:</b></td>\
<td>&sigma;\u2093 = {sigma_x:.2f}, \
&sigma;\u1d67 = {sigma_y:.2f}</td>\
</tr>
    <tr><td><b>Geometry:</b></td><td>{geometry}</td></tr>
    <tr><td><b>Center:</b></td><td>{center}</td></tr>
    <tr><td><b>Pixels:</b></td><td>{pixels}</td></tr>
    <tr><td><b>Date:</b></td><td>{date}</td></tr>
  </table>
</div>"""


class HistoricalEventInspectorViewModel:
    """Pure Python ViewModel for the event detail inspector.

    Formats cluster data into rich HTML for the view and manages
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
        self._on_event_changed: List[
            Callable[[Optional[Cluster]], None]
        ] = []

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

    def formatDetailHtml(self, cluster: Cluster) -> str:
        """Formats cluster data as a rich-text HTML block.

        Args:
            cluster: The cluster whose details to format.

        Returns:
            An HTML string suitable for ``QLabel.setText()``.
        """
        particle_type, _ = classify_particle(
            cluster, self._threshold
        )

        # Energy formatting
        if self._physics and self._displayKeV:
            energy_kev = self._physics.adu_to_kev(cluster.energy)
            energy = (
                f"{energy_kev:.4f} keV ({cluster.energy:.0f} ADU)"
            )
        else:
            energy = f"{cluster.energy:.2f} ADU"

        # Geometry
        bb = cluster.boundingBox
        w = bb.right - bb.left
        h = bb.bottom - bb.top
        geometry = f"{w}\u00d7{h}"

        # Relative center
        rel_cx = cluster.centerX - bb.left
        rel_cy = cluster.centerY - bb.top
        center = f"({rel_cx}, {rel_cy})"

        # Cluster ID
        cluster_id = (
            str(cluster.clusterId)
            if cluster.clusterId is not None
            else "N/A"
        )

        return HTML_TEMPLATE.format(
            particle_symbol=particle_type.symbol,
            particle_name=particle_type.display_name,
            cnn_css=_score_css(
                cluster.cnnClassification, self._threshold
            ),
            cnn_pct=f"{cluster.cnnClassification * 100:.1f}%",
            nrg_css=_score_css(
                cluster.nrgClassification, self._threshold
            ),
            nrg_pct=f"{cluster.nrgClassification * 100:.1f}%",
            bdt_css=_score_css(
                cluster.bdtClassification, self._threshold
            ),
            bdt_pct=f"{cluster.bdtClassification * 100:.1f}%",
            cluster_id=cluster_id,
            fits_filename="N/A",
            energy=energy,
            sigma_x=cluster.sigmaX,
            sigma_y=cluster.sigmaY,
            geometry=geometry,
            center=center,
            pixels=cluster.pixelCount,
            date="N/A",
        )

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
