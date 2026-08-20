"""Bulk cluster insertion for the Event Persistence Service.

Kept separate from ``EventPersistenceService`` (already large) so the "BulkStorage" action's SQL
logic does not grow that file further.

Bypasses the ``insert_cluster`` stored procedure entirely: the fast path is a single multi-row
``INSERT`` executed as one transaction, and the failure-recovery path falls back to inserting the
same clusters one row at a time, reusing the exact same column-driven SQL builder
(``CLUSTER_INSERT_COLUMNS`` / ``_row_values``) so the two paths cannot drift apart from each other.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector

from le_beta_vis.common.EPSDataClasses import (
    BulkInsertClustersResponse,
    ClusterStoreRequest,
)

logger = logging.getLogger(__name__)


CLUSTER_INSERT_COLUMNS: Tuple[str, ...] = (
    "fitsFile",
    "hdu_id",
    "box_top",
    "box_left",
    "box_bottom",
    "box_right",
    "data",
    "totalEnergy",
    "sigmaX",
    "sigmaY",
    "classification",
    "cnn_classification",
    "bdt_classification",
    "nrg_classification",
    "pixelCount",
)
"""Single source of truth for the clusters table INSERT column list.

Both the bulk path and the per-row fallback path build their SQL from this constant, so a schema
change is a one-place edit. A column added here without a matching key in ``_row_values`` raises
``KeyError`` immediately instead of silently shifting positional parameters.
"""


def _row_values(cluster: ClusterStoreRequest) -> Dict[str, Any]:
    """Maps one ClusterStoreRequest to a dict keyed by INSERT column name."""
    bounding_box = cluster.bounding_box or {}
    return {
        "fitsFile": cluster.fits_id,
        "hdu_id": cluster.hdu_id,
        "box_top": bounding_box.get("top"),
        "box_left": bounding_box.get("left"),
        "box_bottom": bounding_box.get("bottom"),
        "box_right": bounding_box.get("right"),
        "data": cluster.data,
        "totalEnergy": cluster.total_energy,
        "sigmaX": cluster.sigma_x,
        "sigmaY": cluster.sigma_y,
        "classification": cluster.classification,
        "cnn_classification": cluster.cnn_classification,
        "bdt_classification": cluster.bdt_classification,
        "nrg_classification": cluster.nrg_classification,
        "pixelCount": cluster.total_pixels,
    }


def _build_insert_sql(num_rows: int) -> str:
    """Builds a parameterized multi-row INSERT statement for num_rows clusters."""
    row_placeholder = "(" + ", ".join(["%s"] * len(CLUSTER_INSERT_COLUMNS)) + ")"
    columns = ", ".join(CLUSTER_INSERT_COLUMNS)
    values = ", ".join([row_placeholder] * num_rows)
    return f"INSERT INTO clusters ({columns}) VALUES {values}"


def _flatten_values(clusters: List[ClusterStoreRequest]) -> List[Any]:
    """Flattens clusters into one parameter list matching CLUSTER_INSERT_COLUMNS order."""
    values: List[Any] = []
    for cluster in clusters:
        row = _row_values(cluster)
        values.extend(row[col] for col in CLUSTER_INSERT_COLUMNS)
    return values


def _execute_insert(conn, clusters: List[ClusterStoreRequest]) -> List[int]:
    """Executes one multi-row INSERT for clusters, returning generated ids in input order.

    Does not commit or rollback — the caller owns the transaction boundary, since the bulk path and
    the per-row fallback path need different commit granularity.
    """
    cursor = conn.cursor()
    cursor.execute(_build_insert_sql(len(clusters)), tuple(_flatten_values(clusters)))
    first_id = cursor.lastrowid
    cursor.close()
    if not first_id:
        raise ValueError("Insert returned no lastrowid")
    return [first_id + i for i in range(len(clusters))]


def bulk_insert_clusters(conn, clusters: List[ClusterStoreRequest]) -> BulkInsertClustersResponse:
    """Persists clusters via one multi-row INSERT, falling back to per-row inserts on failure.

    The fast path is all-or-nothing (one transaction). If it fails for any reason, each cluster is
    retried individually via ``_insert_single_cluster`` so one bad row does not take the whole batch
    down.
    """
    if not clusters:
        return BulkInsertClustersResponse(
            result="failure", cluster_ids=None, error="clusters must be non-empty"
        )
    try:
        ids = _execute_insert(conn, clusters)
        conn.commit()
        return BulkInsertClustersResponse(result="success", cluster_ids=ids)
    except (mysql.connector.Error, ValueError) as err:
        logger.warning("Bulk cluster insert failed, falling back to per-row inserts: %s", err)
        conn.rollback()
        return _fallback_insert_individually(conn, clusters, str(err))


def _insert_single_cluster(conn, cluster: ClusterStoreRequest) -> Optional[int]:
    """Inserts one cluster via the same column-driven SQL builder as the bulk path.

    Bypasses ``insert_cluster`` entirely, same as the bulk path. Commits/rolls back in isolation so
    one bad cluster doesn't block its siblings during the fallback.
    """
    try:
        cluster_id = _execute_insert(conn, [cluster])[0]
        conn.commit()
        return cluster_id
    except (mysql.connector.Error, ValueError) as err:
        conn.rollback()
        logger.warning(
            "Per-row fallback insert failed for cluster (fits_id=%s, hdu_id=%s): %s",
            cluster.fits_id,
            cluster.hdu_id,
            err,
        )
        return None


def _fallback_insert_individually(
    conn, clusters: List[ClusterStoreRequest], bulk_error: str
) -> BulkInsertClustersResponse:
    """Retries clusters one at a time after a failed bulk insert.

    Returns "success" if every row eventually persisted, "partial" if some did, and "failure" if
    none did. cluster_ids stays positionally aligned with clusters regardless of outcome.
    """
    cluster_ids: List[Optional[int]] = [_insert_single_cluster(conn, c) for c in clusters]
    failures = cluster_ids.count(None)
    if failures == 0:
        result = "success"
    elif failures == len(clusters):
        result = "failure"
    else:
        result = "partial"
    return BulkInsertClustersResponse(
        result=result,
        cluster_ids=cluster_ids,
        error=(
            f"Bulk insert failed ({bulk_error}); "
            f"per-row fallback: {len(clusters) - failures}/{len(clusters)} succeeded"
        ),
    )
