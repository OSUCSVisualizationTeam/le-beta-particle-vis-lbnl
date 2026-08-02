"""Storage-agnostic interface for writing a filtered cluster set to disk.

Ships HDF5 as the first (and only) implementation via
``H5ExportStorageService``. The ABC exists so future formats (Parquet,
Zarr, a future streaming format, etc.) can slot in without touching
``HistoricalExportService`` or the UI layer.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable, Dict, List, Optional

from ..common.Cluster import Cluster


def format_mac(node: int) -> str:
    """Formats a 48-bit integer (as returned by uuid.getnode()) as a MAC string."""
    return ":".join(f"{(node >> shift) & 0xFF:02x}" for shift in range(40, -1, -8))


def machine_id() -> str:
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
    return format_mac(uuid.getnode())


class CancelToken:
    """Cooperative cancellation flag shared with worker threads.

    Writers poll ``is_cancelled`` between clusters; the UI flips it via
    ``cancel()``. A plain ``threading.Event`` wrapped here for clarity
    and so future implementations (e.g. subprocess-backed exporters) can
    swap in a richer signal without changing callers.
    """

    def __init__(self) -> None:
        """Initialise the internal threading.Event that backs the flag."""
        self._event = Event()

    def cancel(self) -> None:
        """Signal cancellation; subsequent ``is_cancelled`` checks return True."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """True once ``cancel()`` has been called."""
        return self._event.is_set()


@dataclass(frozen=True)
class ExportProvenance:
    """Self-describing metadata attached to an export.

    Captured at export start so the resulting file remains interpretable
    in isolation months later. See issue #56 `/export_info` spec.
    """

    app_version: str
    export_timestamp_utc: str
    filter_json: str
    calibration_kev_conversion_factor: float
    calibration_pedestal_width: int
    hostname: str
    user: str
    # Stable machine identifier (MAC address as "aa:bb:cc:dd:ee:ff") so
    # an archived export can be traced back to the physical workstation
    # that produced it even after hostname/user changes.
    machine_id: str = ""
    # FITS-header-derived attrs keyed by source filename. Optional because
    # single-cluster exports (Raw Data view) may not resolve headers.
    fits_headers: Dict[str, Dict[str, str]] = field(default_factory=dict)


ProgressCallback = Callable[[int, int], None]
"""``(completed, total)`` — called after each cluster is written."""


class ExportStorageService(ABC):
    """Writes a list of clusters + provenance to a single on-disk artifact."""

    @abstractmethod
    def write(
        self,
        out_path: Path,
        clusters: List[Cluster],
        provenance: ExportProvenance,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Persist ``clusters`` to ``out_path``.

        Implementations must:
          * Poll ``cancel_token.is_cancelled`` between clusters and return
            promptly without leaving a partially-written artifact.
          * Invoke ``on_progress(completed, total)`` after each cluster.
          * Not touch Qt — this runs off the main thread.
        """
        raise NotImplementedError
