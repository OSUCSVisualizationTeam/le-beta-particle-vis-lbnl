"""Single-cluster export support for the Raw Data Analysis annotation dialog.

Reuses the same HDF5 writer and ``CLUSTER_COLUMNS`` layout as the
Historical export pipeline, without depending on
``HistoricalExportViewModel``'s Historical-filter-bar coupling.
"""
import json
import logging
import os
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from le_beta_vis.common.AppInfo import APP_VERSION
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.export.ExportStorageService import (
    CancelToken,
    ExportProvenance,
    machine_id,
)
from le_beta_vis.export.H5ExportStorageService import H5ExportStorageService

logger = logging.getLogger(__name__)


class RawClusterExportService:
    """Exports a single already-hydrated cluster to an HDF5 file.

    Runs off the main thread; results are delivered via the
    ``on_complete``/``on_error`` callbacks passed to ``export_cluster``,
    which may be invoked from the background thread — callers must marshal
    them back to the UI thread themselves (e.g. via a Qt ``Signal.emit``).
    """

    def export_cluster(
        self,
        cluster: Cluster,
        out_path: Path,
        physics: PhysicsConversionManager,
        on_complete: Callable[[Path], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Asynchronously writes *cluster* to *out_path* as HDF5.

        Args:
            cluster: The cluster to export; its pixel data must already be
                populated.
            out_path: Destination HDF5 file path.
            physics: Supplies ADU->keV conversion for the writer.
            on_complete: Called with ``out_path`` on success.
            on_error: Called with an error message on failure.
        """
        threading.Thread(
            target=self._run_export,
            args=(cluster, out_path, physics, on_complete, on_error),
            daemon=True,
        ).start()

    def _run_export(
        self,
        cluster: Cluster,
        out_path: Path,
        physics: PhysicsConversionManager,
        on_complete: Callable[[Path], None],
        on_error: Callable[[str], None],
    ) -> None:
        try:
            provenance = self._build_provenance(cluster, physics)
            service = H5ExportStorageService(physics)
            service.write(out_path, [cluster], provenance, CancelToken())
        except Exception as exc:
            logger.exception("Failed to export cluster %s", cluster.clusterId)
            on_error(str(exc))
            return
        on_complete(out_path)

    def _build_provenance(
        self, cluster: Cluster, physics: PhysicsConversionManager
    ) -> ExportProvenance:
        return ExportProvenance(
            app_version=APP_VERSION,
            export_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            filter_json=json.dumps({"cluster_id": cluster.clusterId}),
            calibration_kev_conversion_factor=physics.kev_conversion_factor,
            calibration_pedestal_width=int(physics.pedestal_width),
            hostname=socket.gethostname(),
            user=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
            machine_id=machine_id(),
            fits_headers={},
        )
