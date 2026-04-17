"""Reusable rich-text stats display for a single Cluster.

Owns the HTML template and uses ``tr()`` for all user-facing labels,
enabling full i18n.  Receives structured data from
``HistoricalEventInspectorViewModel.formatClusterData()``.

Used by both ``HistoricalEventInspector`` and ``LiveModeView``.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    ClusterDisplayData,
    HistoricalEventInspectorViewModel,
)


class ClusterDetailWidget(QLabel):
    """Rich-text cluster statistics label.

    The ``show_filename`` flag controls whether the FITS filename
    row is rendered — live-mode hides it because the path can be
    long and is not relevant in a presentation context.

    Args:
        viewModel: Shared inspector ViewModel for data computation.
        show_filename: Whether to include the FITS filename row.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        viewModel: HistoricalEventInspectorViewModel,
        show_filename: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._show_filename = show_filename
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setAlignment(Qt.AlignTop)

    def setCluster(self, cluster: Optional[Cluster]) -> None:
        """Renders cluster stats into the label, or clears it.

        Args:
            cluster: The cluster to display, or None to clear.
        """
        if cluster is None:
            self.clear()
            return
        data = self._vm.formatClusterData(cluster)
        self.setText(self._buildHtml(data))

    def _buildHtml(self, data: ClusterDisplayData) -> str:
        """Constructs HTML from structured data with translatable labels."""
        rows = self._buildScoreRows(data)
        rows += self._buildDetailRows(data)
        return (
            f"<div>"
            f'<span style="font-size: 16px; font-weight: bold;">'
            f"{data.particle_symbol} &mdash; {data.particle_name}"
            f"</span><br/>"
            f'<table style="margin-top: 6px;">{rows}</table>'
            f"</div>"
        )

    def _buildScoreRows(self, data: ClusterDisplayData) -> str:
        """Builds the CNN / NRG / BDT classification score rows."""
        return (
            f'<tr><td>CNN:</td><td style="{data.cnn_css}">'
            f"{data.cnn_pct}</td></tr>"
            f'<tr><td>NRG:</td><td style="{data.nrg_css}">'
            f"{data.nrg_pct}</td></tr>"
            f'<tr><td>BDT:</td><td style="{data.bdt_css}">'
            f"{data.bdt_pct}</td></tr>"
            f"</table><hr/>"
            f'<table style="margin-top: 4px;">'
        )

    def _buildDetailRows(self, data: ClusterDisplayData) -> str:
        """Builds the detail rows with translatable labels."""
        cluster_id_label = self.tr("Cluster ID:")
        fits_label = self.tr("FITS File:")
        energy_label = self.tr("Energy:")
        sigma_label = self.tr("\u03c3 spread:")
        geometry_label = self.tr("Geometry:")
        center_label = self.tr("Center:")
        pixels_label = self.tr("Pixels:")
        date_label = self.tr("Date:")

        sigma_val = (
            f"\u03c3\u2093 = {data.sigma_x:.2f}, "
            f"\u03c3\u1d67 = {data.sigma_y:.2f}"
        )

        rows = f"<tr><td><b>{cluster_id_label}</b></td><td>{data.cluster_id}</td></tr>"
        if self._show_filename:
            rows += (
                f"<tr><td><b>{fits_label}</b></td>"
                f"<td>{data.fits_filename}</td></tr>"
            )
        rows += (
            f"<tr><td><b>{energy_label}</b></td><td>{data.energy}</td></tr>"
            f"<tr><td><b>{sigma_label}</b></td><td>{sigma_val}</td></tr>"
            f"<tr><td><b>{geometry_label}</b></td><td>{data.geometry}</td></tr>"
            f"<tr><td><b>{center_label}</b></td><td>{data.center}</td></tr>"
            f"<tr><td><b>{pixels_label}</b></td><td>{data.pixels}</td></tr>"
            f"<tr><td><b>{date_label}</b></td><td>{data.date}</td></tr>"
        )
        return rows
