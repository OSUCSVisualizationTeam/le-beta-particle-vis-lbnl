"""ViewModel for the Historical "Save" action (issue #56).

Pure Python — no Qt imports — so it runs in headless CI. Owns:

  * Gating logic (time preset must not be 'all'; window must not
    exceed ``gui:export:max_time_window_days``).
  * The export lifecycle (begin / progress / complete / cancel / error)
    surfaced as plain callbacks the View binds to.
  * Coordination with the filter-bar ViewModel's export lock so filter
    inputs can't mutate during an in-flight save.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from le_beta_vis.common.AppInfo import APP_VERSION
from le_beta_vis.common.ClusterExportService import ClusterMetadataLabels
from le_beta_vis.common.Colormap import Colormap
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.ExportStorageService import CancelToken, ExportProvenance
from le_beta_vis.common.HistoricalExportService import (
    ExportRequest,
    HistoricalExportService,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager

logger = logging.getLogger(__name__)


class HistoricalExportViewModel:
    def __init__(
        self,
        config: ConfigurationService,
        physics: PhysicsConversionManager,
        export_service: HistoricalExportService,
        filter_bar_vm,
    ) -> None:
        self._config = config
        self._physics = physics
        self._service = export_service
        self._filter_bar = filter_bar_vm
        self._is_exporting: bool = False
        self._cancel_token: Optional[CancelToken] = None
        self._on_state_changed: List[Callable[[bool], None]] = []
        self._on_progress: List[Callable[[int, int, str], None]] = []
        self._on_complete: List[Callable[[Path], None]] = []
        self._on_error: List[Callable[[str], None]] = []
        self._on_cancelled: List[Callable[[], None]] = []
        self._on_gating_changed: List[Callable[[bool, str], None]] = []

    # --- Properties ---

    @property
    def is_exporting(self) -> bool:
        return self._is_exporting

    @property
    def max_window_days(self) -> int:
        return self._config.get_int(
            "gui:export:max_time_window_days", 30, minimum=1
        )

    @property
    def colormap(self) -> Colormap:
        raw = str(self._config.get("gui:export:cluster_png_colormap", "viridis"))
        try:
            return Colormap(raw)
        except ValueError:
            logger.warning(
                "Invalid gui:export:cluster_png_colormap=%r; falling back to viridis",
                raw,
            )
            return Colormap.VIRIDIS

    @property
    def default_export_path(self) -> str:
        """Return ``<dir>/mlccd-export-YYYYMMDD-HHMMSS`` for the current local time.

        The directory is read from ``gui:export:default_path`` (default ``~``).
        """
        base_dir = str(self._config.get("gui:export:default_path", "~"))
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return str(Path(base_dir).expanduser() / f"mlccd-export-{timestamp}")

    # --- Gating ---

    def can_export(self) -> bool:
        ok, _ = self.gating_reason()
        return ok

    def gating_reason(self) -> tuple[bool, str]:
        """Returns ``(enabled, reason_if_disabled)``.

        Reason string is user-facing (no tr() here — the View wraps it
        with ``tr()`` when building the tooltip).
        """
        preset = self._filter_bar.time_preset
        if preset == "all":
            return False, (
                "Export is disabled while the time preset is set to 'all'. "
                "Pick a time window first."
            )
        start = self._filter_bar.start_datetime
        end = self._filter_bar.end_datetime
        if start is not None and end is not None:
            window_days = (end - start).total_seconds() / 86400.0
            if window_days > self.max_window_days:
                return False, (
                    f"Export is disabled because the selected window "
                    f"({window_days:.1f} days) exceeds the configured "
                    f"maximum ({self.max_window_days} days)."
                )
        return True, ""

    def notify_gating_changed(self) -> None:
        ok, reason = self.gating_reason()
        for cb in self._on_gating_changed:
            cb(ok, reason)

    # --- Commands ---

    def export(
        self,
        out_path: Path,
        query_filter: ClusterQueryFilter,
        selection_summary: Optional[str] = None,
        labels: Optional[ClusterMetadataLabels] = None,
        include_pngs: bool = False,
    ) -> None:
        """Begin an async export.

        Parameters
        ----------
        out_path:
            Destination HDF5 file path.
        query_filter:
            Active cluster filter criteria.
        selection_summary:
            Optional pre-formatted summary string for the cluster card metadata.
        labels:
            Pre-translated metadata labels from the View. Falls back to
            ``ClusterMetadataLabels.default_english()`` when omitted.
        include_pngs:
            When ``True``, cluster card PNGs are embedded in the HDF5 under
            ``/clusterCards``. Increases file size.
        """
        if self._is_exporting:
            return
        self._cancel_token = CancelToken()
        self._is_exporting = True
        self._filter_bar.set_export_running(True)
        self._notify_state(True)
        request = ExportRequest(
            out_path=out_path,
            query_filter=query_filter,
            provenance=self._build_provenance(query_filter),
            colormap=self.colormap,
            labels=labels or ClusterMetadataLabels.default_english(),
            selection_summary=selection_summary,
            include_pngs=include_pngs,
        )
        self._service.run_async(
            request,
            self._cancel_token,
            on_progress=self._forward_progress,
            on_complete=self._finish_success,
            on_error=self._finish_error,
            on_cancelled=self._finish_cancelled,
        )

    def cancel(self) -> None:
        if self._cancel_token is not None:
            self._cancel_token.cancel()

    # --- Observer pattern ---

    def add_state_changed_callback(self, cb: Callable[[bool], None]) -> None:
        self._on_state_changed.append(cb)

    def add_progress_callback(self, cb: Callable[[int, int, str], None]) -> None:
        self._on_progress.append(cb)

    def add_complete_callback(self, cb: Callable[[Path], None]) -> None:
        self._on_complete.append(cb)

    def add_error_callback(self, cb: Callable[[str], None]) -> None:
        self._on_error.append(cb)

    def add_cancelled_callback(self, cb: Callable[[], None]) -> None:
        self._on_cancelled.append(cb)

    def add_gating_changed_callback(
        self, cb: Callable[[bool, str], None]
    ) -> None:
        self._on_gating_changed.append(cb)

    # --- Internals ---

    def _finish_success(self, out: Path) -> None:
        self._reset_state()
        for cb in self._on_complete:
            cb(out)

    def _finish_error(self, message: str) -> None:
        logger.error("Export failed: %s", message)
        self._reset_state()
        for cb in self._on_error:
            cb(message)

    def _finish_cancelled(self) -> None:
        self._reset_state()
        for cb in self._on_cancelled:
            cb()

    def _reset_state(self) -> None:
        self._is_exporting = False
        self._cancel_token = None
        self._filter_bar.set_export_running(False)
        self._notify_state(False)

    def _notify_state(self, flag: bool) -> None:
        for cb in self._on_state_changed:
            cb(flag)

    def _forward_progress(self, done: int, total: int, stage: str) -> None:
        for cb in self._on_progress:
            cb(done, total, stage)

    def _build_provenance(
        self, query_filter: Optional[ClusterQueryFilter]
    ) -> ExportProvenance:
        filter_dict = asdict(query_filter) if query_filter is not None else {}
        return ExportProvenance(
            app_version=APP_VERSION,
            export_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            filter_json=json.dumps(filter_dict, default=str),
            calibration_kev_conversion_factor=self._physics.kev_conversion_factor,
            calibration_pedestal_width=int(self._physics.pedestal_width),
            hostname=socket.gethostname(),
            user=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
            machine_id=_machine_id(),
        )


def _format_mac(node: int) -> str:
    return ":".join(f"{(node >> shift) & 0xFF:02x}" for shift in range(40, -1, -8))


def _machine_id() -> str:
    """Return a stable machine identifier without blocking the main thread.

    Reads the first non-zero MAC address from /sys/class/net (Linux) —
    an instantaneous file read. Falls back to uuid.getnode() only on
    non-Linux systems; that call can spawn subprocesses on some
    configurations and block for up to 120 s.
    """
    sys_net = Path("/sys/class/net")
    if sys_net.is_dir():
        for addr_file in sorted(sys_net.glob("*/address")):
            try:
                addr = addr_file.read_text().strip()
                if addr and addr != "00:00:00:00:00:00":
                    return addr
            except OSError:
                continue
    return _format_mac(uuid.getnode())
