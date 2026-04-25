"""HDF5 implementation of :class:`ExportStorageService` (issue #56).

File layout (locked — downstream analysis scripts pin to this):
  /clusters              compound-dtype tabular rows, one per cluster
  /images/<cluster_id>   2D float array of raw ADU pixel values
  /export_info           group; attrs carry provenance

Naming: h5py is the library, `.h5` is the file extension, so the impl
is called H5ExportStorageService (not HDFS — HDFS is Hadoop).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

import h5py
import numpy as np

from ..common.Cluster import Cluster
from ..common.ParticleType import ParticleType, classify_particle
from ..common.PhysicsConversionManager import PhysicsConversionManager
from .ExportStorageService import (
    CancelToken,
    ExportProvenance,
    ExportStorageService,
    ProgressCallback,
)

logger = logging.getLogger(__name__)

# Locked column order. Downstream analysis scripts pin to this tuple,
# so additions MUST append to the end — never re-order or insert.
#
# The three *_particle_type columns (cnn_particle_type, bdt_particle_type,
# nrg_particle_type) are reserved for the per-model class label each
# classifier will emit once Troy's Cluster-schema work (issue #36) ships
# the label alongside the existing scalar score. We populate them with
# ParticleType.UNCLASSIFIED today so analysts consuming current .h5 files
# do not need to branch their readers when the labels go live.
CLUSTER_COLUMNS: Tuple[str, ...] = (
    "cluster_id",
    "fits_id",
    "fits_filename",
    "date",
    "hdu_id",
    "center_x",
    "center_y",
    "bbox_top",
    "bbox_left",
    "bbox_bottom",
    "bbox_right",
    "sigma_x",
    "sigma_y",
    "pixel_count",
    "energy_adu",
    "energy_kev",
    "score_cnn",
    "score_nrg",
    "score_bdt",
    "cnn_particle_type",
    "bdt_particle_type",
    "nrg_particle_type",
    "particle_type",
)


def _cluster_dtype() -> np.dtype:
    """Build the compound numpy dtype for the locked ``/clusters`` dataset."""
    str_dt = h5py.string_dtype(encoding="utf-8")
    return np.dtype(
        [
            ("cluster_id", np.int64),
            ("fits_id", np.int64),
            ("fits_filename", str_dt),
            ("date", str_dt),
            ("hdu_id", np.int64),
            ("center_x", np.int64),
            ("center_y", np.int64),
            ("bbox_top", np.int64),
            ("bbox_left", np.int64),
            ("bbox_bottom", np.int64),
            ("bbox_right", np.int64),
            ("sigma_x", np.float64),
            ("sigma_y", np.float64),
            ("pixel_count", np.int64),
            ("energy_adu", np.float64),
            ("energy_kev", np.float64),
            ("score_cnn", np.float64),
            ("score_nrg", np.float64),
            ("score_bdt", np.float64),
            ("cnn_particle_type", str_dt),
            ("bdt_particle_type", str_dt),
            ("nrg_particle_type", str_dt),
            ("particle_type", str_dt),
        ]
    )


def _resolve_per_model_label(score: float) -> str:
    """Reserved hook for future per-model particle-type resolution.

    Returns UNCLASSIFIED today because ``Cluster`` carries scalar scores
    only — no per-model class label. Fills in once issue #36 lands the
    multi-class label on the Cluster schema. Signature kept minimal so
    callers don't need to change when the real classifier arrives.
    """
    # TODO(#36): return the per-model ParticleType label when available.
    _ = score
    return ParticleType.UNCLASSIFIED.name


class H5ExportStorageService(ExportStorageService):
    """HDF5 implementation of ExportStorageService; writes the locked layout
    described in the module docstring."""

    def __init__(
        self,
        physics: PhysicsConversionManager,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        """``physics`` provides ADU→keV conversions; ``logger_`` defaults to the module logger."""
        self._physics = physics
        self._logger = logger_ or logger
        self._coerced_fields = 0

    def write(
        self,
        out_path: Path,
        clusters: List[Cluster],
        provenance: ExportProvenance,
        cancel_token: CancelToken,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Write ``clusters`` and ``provenance`` to a new HDF5 file at ``out_path``.

        Writes to a ``.partial`` sibling first and atomically renames on success.
        Polls ``cancel_token.is_cancelled`` between clusters; partial files are
        deleted on cancel or failure.
        """
        total = len(clusters)
        tmp_path = out_path.with_suffix(out_path.suffix + ".partial")
        self._coerced_fields = 0
        self._logger.info("h5 export start: rows=%d out=%s", total, out_path)
        try:
            with h5py.File(tmp_path, "w") as f:
                images = f.create_group("images")
                rows = np.empty(total, dtype=_cluster_dtype())
                for idx, cluster in enumerate(clusters):
                    if cancel_token.is_cancelled:
                        raise _Cancelled()
                    rows[idx] = self._row(cluster)
                    cid = cluster.clusterId if cluster.clusterId is not None else idx
                    arr = (
                        np.asarray(cluster.data, dtype=np.float64)
                        if cluster.data is not None
                        else None
                    )
                    if arr is not None and arr.ndim >= 1:
                        images.create_dataset(
                            str(cid),
                            data=arr,
                            compression="gzip",
                            compression_opts=4,
                        )
                    else:
                        self._logger.warning(
                            "cluster %s has no pixel data; image omitted from h5", cid
                        )
                    if on_progress is not None:
                        on_progress(idx + 1, total)
                f.create_dataset("clusters", data=rows)
                self._write_provenance(f, provenance)
            tmp_path.replace(out_path)
            if self._coerced_fields:
                self._logger.debug(
                    "h5 export coerced %d None cluster fields to defaults",
                    self._coerced_fields,
                )
            self._logger.info("h5 export complete: %s", out_path)
        except _Cancelled:
            tmp_path.unlink(missing_ok=True)
            self._logger.info("h5 export cancelled, partial removed: %s", tmp_path)
            raise
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            self._logger.exception("h5 export failed, partial removed: %s", tmp_path)
            raise

    def _row(self, c: Cluster) -> tuple:
        """Serialise one cluster to the compound-dtype tuple expected by ``_cluster_dtype()``.

        None fields are coerced to sentinel values via ``_i``/``_f``; each coercion
        increments ``_coerced_fields`` so the caller can log a summary.
        """
        bbox = c.boundingBox
        particle, _ = classify_particle(c)
        energy_adu = self._f(c.energy)
        return (
            self._i(c.clusterId),
            self._i(c.fitsId),
            c.fitsFilename or "",
            c.date or "",
            self._i(c.hdu_id),
            self._i(c.centerX),
            self._i(c.centerY),
            self._i(bbox.top),
            self._i(bbox.left),
            self._i(bbox.bottom),
            self._i(bbox.right),
            self._f(c.sigmaX),
            self._f(c.sigmaY),
            self._i(c.pixelCount),
            energy_adu,
            float(self._physics.adu_to_kev(energy_adu)),
            self._f(c.cnnClassification),
            self._f(c.nrgClassification),
            self._f(c.bdtClassification),
            _resolve_per_model_label(c.cnnClassification),
            _resolve_per_model_label(c.bdtClassification),
            _resolve_per_model_label(c.nrgClassification),
            particle.name,
        )

    def _i(self, value: Any, default: int = -1) -> int:
        """Coerce ``value`` to ``int``, returning ``default`` for ``None``. Increments ``_coerced_fields`` on coercion."""
        if value is None:
            self._coerced_fields += 1
            return default
        return int(value)

    def _f(self, value: Any, default: float = 0.0) -> float:
        """Coerce ``value`` to ``float``, returning ``default`` for ``None``. Increments ``_coerced_fields`` on coercion."""
        if value is None:
            self._coerced_fields += 1
            return default
        return float(value)

    @staticmethod
    def _write_provenance(f: h5py.File, p: ExportProvenance) -> None:
        """Write all ``ExportProvenance`` fields as HDF5 attributes on the ``/export_info`` group."""
        g = f.create_group("export_info")
        g.attrs["app_version"] = p.app_version
        g.attrs["export_timestamp_utc"] = p.export_timestamp_utc
        g.attrs["filter_json"] = p.filter_json
        g.attrs["calibration_kev_conversion_factor"] = p.calibration_kev_conversion_factor
        g.attrs["calibration_pedestal_width"] = p.calibration_pedestal_width
        g.attrs["hostname"] = p.hostname
        g.attrs["user"] = p.user
        g.attrs["machine_id"] = p.machine_id
        g.attrs["fits_headers_json"] = json.dumps(p.fits_headers)
        g.attrs["column_order"] = list(CLUSTER_COLUMNS)


class _Cancelled(Exception):
    """Internal — raised to unwind the write loop on cancel."""
