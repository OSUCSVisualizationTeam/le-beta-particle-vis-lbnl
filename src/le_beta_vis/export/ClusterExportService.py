"""Per-cluster export interface

The PNG sidecar next to the `.h5` is meant for slide decks — the raw
ADU array in `/images/<cluster_id>` remains the source of truth. The
ABC exists so we can swap renderers (currently a Pillow + numpy LUT
implementation) without changing callers.

Metadata rendering is part of the contract: every renderer must paint
the structured ``ClusterExportMetadata`` built by ``build_metadata``.
Labels are supplied by the caller through ``ClusterMetadataLabels``
so the View layer owns ``tr()`` and the service stays headless.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

from ..common.Cluster import Cluster
from ..common.Colormap import Colormap
from ..common.PhysicsConversionManager import PhysicsConversionManager


@dataclass(frozen=True)
class ClusterMetadataLabels:
    """Pre-translated labels for the metadata panel.

    The View (which has access to Qt's ``tr()``) constructs this and
    hands it down through ``ClusterExportContext``. The service never
    invokes ``tr()`` — this mirrors the ``ActionableEvent`` contract
    where the frontend owns all user-facing translation.
    """

    energy: str
    pixels: str
    sigma_x: str
    sigma_y: str
    full_width_x: str
    full_width_y: str
    energy_per_pixel: str
    peak_xy: str
    selection: str
    kev_unit: str
    colorbar: str
    x_axis: str
    y_axis: str

    @classmethod
    def default_english(cls) -> "ClusterMetadataLabels":
        """Fallback labels for callers without access to ``tr()``.

        Used by tests and the Raw Data single-cluster export when no
        View has plumbed localized labels in yet.
        """
        return cls(
            energy="Energy",
            pixels="Num. pixels",
            sigma_x="σx",
            sigma_y="σy",
            full_width_x="Full width x",
            full_width_y="Full width y",
            energy_per_pixel="Energy per pixel",
            peak_xy="Peak xy",
            selection="Selection",
            kev_unit="keV",
            colorbar="Pixel energy [keV]",
            x_axis="Pixel x",
            y_axis="Pixel y",
        )


@dataclass(frozen=True)
class ClusterExportMetadata:
    """Structured metadata derived from a Cluster at export time.

    Deliberately excludes ``cluster_id`` — the figure title already
    identifies the cluster; duplicating the id in the metadata panel
    is the bug this field set fixes.
    """

    total_energy_kev: float
    pixel_count: int
    sigma_x: float
    sigma_y: float
    full_width_x: int
    full_width_y: int
    energy_per_pixel_kev: float
    peak_xy_absolute: Tuple[int, int]
    selection_summary: Optional[str]


@dataclass(frozen=True)
class ClusterExportContext:
    """Extra data the renderer needs beyond the Cluster object.

    Carries the PhysicsConversionManager (single source of truth for
    ADU→keV) and the pre-translated label set. Kept separate from
    ``Cluster`` so per-export metadata never leaks into the in-memory
    data model.
    """

    physics: PhysicsConversionManager
    labels: ClusterMetadataLabels
    selection_summary: Optional[str] = None


class ClusterExportService(ABC):
    """Renders a single cluster to an output artifact (PNG today).

    Concrete subclasses override ``export`` and ``render_metadata``;
    ``build_metadata`` is concrete on the ABC so every renderer shares
    the same physics-backed derivation of metadata values.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        # Caller (usually HistoricalExportService) injects a child logger
        # so log lines carry the orchestrator → service chain. Fallback
        # keeps standalone use (tests, Raw Data single-cluster) sane.
        self._logger = logger or logging.getLogger(self.__class__.__module__)

    @abstractmethod
    def export(
        self,
        cluster: Cluster,
        out_path: Path,
        *,
        context: ClusterExportContext,
        colormap: Colormap,
    ) -> None:
        """Render ``cluster`` to ``out_path`` using ``colormap``.

        Implementations must be headless-safe (no Qt, no GUI backend)
        because this runs on a worker thread during export.
        """
        raise NotImplementedError

    @abstractmethod
    def render_metadata(
        self,
        canvas: Any,
        metadata: ClusterExportMetadata,
        labels: ClusterMetadataLabels,
    ) -> None:
        """Paint ``metadata`` onto the renderer's native ``canvas``.

        The current implementation (`DirectPNGClusterExportService`)
        receives a ``PIL.Image.Image``. Future renderers may pass a
        ``QPainter``, a ``pyqtgraph`` item, etc. — the ABC keeps the
        contract: metadata must always be rendered alongside the cluster.
        """
        raise NotImplementedError

    def render_to_bytes(
        self,
        cluster: Cluster,
        *,
        context: ClusterExportContext,
        colormap: Colormap,
    ) -> bytes:
        """Render ``cluster`` to PNG bytes without writing a permanent file.

        Calls ``export()`` against a NamedTemporaryFile so all existing
        renderer implementations produce the bytes without any changes.
        Callers receive raw PNG bytes suitable for embedding in HDF5.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            self.export(cluster, tmp_path, context=context, colormap=colormap)
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def build_metadata(
        self, cluster: Cluster, context: ClusterExportContext
    ) -> ClusterExportMetadata:
        """Derive structured metadata from a cluster.

        Uses ``context.physics.adu_to_kev`` for every energy conversion
        — never multiply by a raw factor. Shared across renderers so a
        future pyqtgraph-based implementation produces identical values.
        """
        data = np.asarray(cluster.data)
        rows, cols = data.shape
        peak_local = np.unravel_index(int(np.argmax(data)), data.shape)
        peak_x = int(cluster.boundingBox.left + peak_local[1])
        peak_y = int(cluster.boundingBox.top + peak_local[0])
        pixel_count = max(int(cluster.pixelCount), 1)
        total_kev = float(context.physics.adu_to_kev(float(cluster.energy)))
        return ClusterExportMetadata(
            total_energy_kev=total_kev,
            pixel_count=int(cluster.pixelCount),
            sigma_x=float(cluster.sigmaX),
            sigma_y=float(cluster.sigmaY),
            full_width_x=int(cols),
            full_width_y=int(rows),
            energy_per_pixel_kev=total_kev / pixel_count,
            peak_xy_absolute=(peak_x, peak_y),
            selection_summary=context.selection_summary,
        )
