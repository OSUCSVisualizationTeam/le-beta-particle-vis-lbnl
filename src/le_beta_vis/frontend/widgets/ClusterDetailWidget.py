"""Reusable rich-text stats display for a single Cluster.

Owns the HTML template and uses ``tr()`` for all user-facing labels,
enabling full i18n.  Receives structured data from
``HistoricalEventInspectorViewModel.formatClusterData()``.

Used by both ``HistoricalEventInspector`` and ``LiveModeView``.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.viewmodels.HistoricalEventInspectorViewModel import (
    ClusterDisplayData,
    HistoricalEventInspectorViewModel,
)


_OPEN_LINK_HREF = "open-in-raw-data"


class ClusterDetailWidget(QWidget):
    """Rich-text cluster statistics with an optional Open action.

    The ``show_filename`` flag controls whether the FITS filename
    row is rendered — live-mode hides it because the path can be
    long and is not relevant in a presentation context.

    The ``show_open_action`` flag controls the "Open in Raw Data"
    button + clickable filename hyperlink.  Both emit
    :pyattr:`openClicked` so the host can navigate to the Raw Data
    Analysis tab.

    Args:
        viewModel: Shared inspector ViewModel for data computation.
        show_filename: Whether to include the FITS filename row.
        show_open_action: Whether to expose the Open action.
        parent: Optional parent widget.
    """

    openClicked = Signal()

    def __init__(
        self,
        viewModel: HistoricalEventInspectorViewModel,
        show_filename: bool = True,
        show_open_action: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._show_filename = show_filename
        self._show_open_action = show_open_action
        self._has_filename = False
        self._classifiers_visible: bool = True
        self._current_cluster: Optional[Cluster] = None
        # Honor caller-supplied background-color stylesheets (live mode
        # paints a dark panel behind the stats); QWidget ignores its own
        # stylesheet background unless WA_StyledBackground is enabled.
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setAlignment(Qt.AlignTop)
        self._label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._label.setOpenExternalLinks(False)
        self._label.linkActivated.connect(self._onLinkActivated)
        layout.addWidget(self._label)

        self._openButton = QPushButton(self.tr("Open"), self)
        self._openButton.setToolTip(
            self.tr("Open this cluster in the Raw Data Analysis tab")
        )
        self._openButton.clicked.connect(self.openClicked)
        self._openButton.setVisible(False)
        layout.addWidget(self._openButton, 0, Qt.AlignLeft)

    def setCluster(self, cluster: Optional[Cluster]) -> None:
        """Renders cluster stats into the widget, or clears it.

        Args:
            cluster: The cluster to display, or None to clear.
        """
        if cluster is None:
            self.clear()
            return
        self._current_cluster = cluster
        data = self._vm.formatClusterData(cluster)
        self._has_filename = bool(data.fits_filename)
        self._label.setText(self._buildHtml(data))
        self._refreshOpenAction()

    def clear(self) -> None:
        """Clear the widget to its empty state."""
        self._current_cluster = None
        self._label.clear()
        self._has_filename = False
        self._refreshOpenAction()

    def set_classifiers_visible(self, visible: bool) -> None:
        """Show or hide the particle type header and classifier score rows.

        Intended for live mode where classifiers may be disabled or the
        incoming cluster may not yet have classification scores.  Historical
        views should not call this — the section is always visible by default.

        Args:
            visible: True to show classifier rows; False to hide them.
        """
        if self._classifiers_visible == visible:
            return
        self._classifiers_visible = visible
        if self._current_cluster is not None:
            data = self._vm.formatClusterData(self._current_cluster)
            self._label.setText(self._buildHtml(data))

    def _refreshOpenAction(self) -> None:
        """Shows/enables the Open button based on flags + data."""
        visible = self._show_open_action and self._show_filename
        self._openButton.setVisible(visible)
        self._openButton.setEnabled(visible and self._has_filename)

    def _onLinkActivated(self, href: str) -> None:
        if href == _OPEN_LINK_HREF and self._openButton.isEnabled():
            self.openClicked.emit()

    def _buildHtml(self, data: ClusterDisplayData) -> str:
        """Constructs HTML from structured data with translatable labels."""
        parts = ["<div>"]
        if self._classifiers_visible:
            parts.append(
                f'<span style="font-size: 16px; font-weight: bold;">'
                f"{data.particle_symbol} &mdash; {data.particle_name}"
                f"</span><br/>"
                f'<table style="margin-top: 6px;">'
                f"{self._buildScoreRows(data)}"
                f"</table><hr/>"
            )
        parts.append(
            f'<table style="margin-top: 4px;">'
            f"{self._buildDetailRows(data)}"
            f"</table>"
        )
        parts.append("</div>")
        return "".join(parts)

    def _buildScoreRows(self, data: ClusterDisplayData) -> str:
        """Builds the CNN / NRG / BDT classification score table rows."""
        return (
            f'<tr><td>CNN:</td><td style="{data.cnn_css}">'
            f"{data.cnn_pct}</td></tr>"
            f'<tr><td>NRG:</td><td style="{data.nrg_css}">'
            f"{data.nrg_pct}</td></tr>"
            f'<tr><td>BDT:</td><td style="{data.bdt_css}">'
            f"{data.bdt_pct}</td></tr>"
        )

    def _buildDetailRows(self, data: ClusterDisplayData) -> str:
        """Builds the detail rows with translatable labels."""
        cluster_id_label = self.tr("Cluster ID:")
        fits_label = self.tr("FITS File:")
        energy_label = self.tr("Energy:")
        sigma_label = self.tr("σ spread:")
        geometry_label = self.tr("Geometry:")
        center_label = self.tr("Center:")
        pixels_label = self.tr("Pixels:")
        date_label = self.tr("Date:")

        sigma_val = (
            f"σₓ = {data.sigma_x:.2f}, "
            f"σᵧ = {data.sigma_y:.2f}"
        )

        rows = f"<tr><td><b>{cluster_id_label}</b></td><td>{data.cluster_id}</td></tr>"
        if self._show_filename:
            rows += (
                f"<tr><td><b>{fits_label}</b></td>"
                f"<td>{self._formatFilenameCell(data.fits_filename)}</td></tr>"
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

    def _formatFilenameCell(self, filename: Optional[str]) -> str:
        """Renders the filename as a hyperlink when the Open action is live."""
        if not filename:
            return ""
        if self._show_open_action:
            return f'<a href="{_OPEN_LINK_HREF}">{filename}</a>'
        return filename
