"""Paged cluster retrieval for the Event Persistence Service.

Kept separate from ``EventPersistenceService`` (already large) so the
"PagedRetrieval" action's SQL/formatting logic does not grow that file
further. The filter-clause and row-formatting helpers here intentionally
mirror (rather than reuse) the logic in
``EventPersistenceService.retrieve_clusters`` / ``process_retrieval_clusters``
so that method remains unchanged.
"""

import logging
from typing import Any, List, Tuple

import mysql.connector

from le_beta_vis.common.EPSDataClasses import (
    ClusterPagedQueryFilter,
    ClusterQueryFilter,
    EPSClusterRecord,
    PagedRetrieveClustersResponse,
)

logger = logging.getLogger(__name__)


# Simple equality/threshold filters: (value, SQL clause).
_SIMPLE_FILTER_CLAUSES: List[Tuple[str, str]] = [
    ("hdu_id", "hdu_id = %s"),
    ("fits_id", "fitsFile = %s"),
    ("cluster_id", "clusterId = %s"),
    ("min_sigma_x", "sigmaX >= %s"),
    ("min_sigma_y", "sigmaY >= %s"),
    ("min_total_energy", "totalEnergy >= %s"),
    ("min_total_pixels", "pixelCount >= %s"),
    ("classification", "classification = %s"),
]


def _bounding_box_clause(bounding_box: dict) -> Tuple[List[str], List[Any]]:
    """Returns the WHERE clauses and values for a bounding-box filter."""
    return (
        ["box_top = %s", "box_left = %s", "box_bottom = %s", "box_right = %s"],
        [
            bounding_box["top"],
            bounding_box["left"],
            bounding_box["bottom"],
            bounding_box["right"],
        ],
    )


def _date_range_clause(filters: ClusterQueryFilter) -> Tuple[List[str], List[Any]]:
    """Returns the WHERE clause and values for a date-range filter."""
    # Imported lazily to avoid a circular top-level import between this
    # module and EventPersistenceService.
    from le_beta_vis.backend.EventPersistenceService import _parse_date_filter

    date_start = str(filters.date_start) if filters.date_start else None
    date_end = str(filters.date_end) if filters.date_end else None
    date_range = _parse_date_filter({"start": date_start, "end": date_end})
    if date_range is None:
        return [], []
    return ["fits_files.date BETWEEN %s AND %s"], list(date_range)


def _fits_list_clause(fits_list: List[int]) -> Tuple[List[str], List[Any]]:
    """Returns the WHERE clause and values for an ``IN`` filter on fits IDs."""
    placeholder = ", ".join(["%s"] * len(fits_list))
    return [f"fitsFile in ({placeholder})"], list(fits_list)


def _build_cluster_select(filters: ClusterQueryFilter) -> Tuple[str, List[Any]]:
    """Builds the base ``SELECT ... WHERE ...`` clause for a cluster query.

    Returns the query string (without ``LIMIT``/``OFFSET``) and the list of
    bind parameters for the ``WHERE`` clause.
    """
    select_query = (
        "SELECT clusters.*, fits_files.filename, fits_files.date "
        "FROM clusters INNER JOIN fits_files "
        "ON clusters.fitsFile = fits_files.fitsID"
    )
    select_args: List[str] = []
    select_argv: List[Any] = []

    for attr, clause in _SIMPLE_FILTER_CLAUSES:
        value = getattr(filters, attr)
        if value:
            select_args.append(clause)
            select_argv.append(value)

    if filters.bounding_box:
        clauses, values = _bounding_box_clause(filters.bounding_box)
        select_args.extend(clauses)
        select_argv.extend(values)

    if filters.fits_list:
        clauses, values = _fits_list_clause(filters.fits_list)
        select_args.extend(clauses)
        select_argv.extend(values)

    date_clauses, date_values = _date_range_clause(filters)
    select_args.extend(date_clauses)
    select_argv.extend(date_values)

    if select_args:
        select_query += " WHERE " + " AND ".join(select_args)

    select_query += " ORDER BY clusters.clusterID"

    return select_query, select_argv


def _format_cluster_rows(results) -> List[dict]:
    """Maps cluster/fits_files row dicts to the EPS cluster response shape."""
    return [EPSClusterRecord.from_db_row(result).to_response_dict() for result in results]


def paged_retrieve_clusters(
    conn,
    paged_filter: ClusterPagedQueryFilter,
    default_limit: int,
    max_limit: int,
) -> PagedRetrieveClustersResponse:
    """Runs a bounded, paginated cluster retrieval against the database.

    Applies ``default_limit`` when the request does not specify ``limit``,
    and rejects (raises ``ValueError``) any effective limit that is
    non-positive or exceeds ``max_limit``.
    """
    effective_limit = (
        paged_filter.limit if paged_filter.limit is not None else default_limit
    )
    if effective_limit <= 0 or effective_limit > max_limit:
        raise ValueError(
            f"limit must be between 1 and {max_limit}, got {effective_limit}"
        )

    try:
        cursor = conn.cursor(dictionary=True)

        select_query, select_argv = _build_cluster_select(paged_filter.filters)
        select_query += " LIMIT %s OFFSET %s"
        select_argv = select_argv + [effective_limit, paged_filter.offset]

        cursor.execute(select_query, tuple(select_argv))
        results = cursor.fetchall()
        cursor.close()

        return PagedRetrieveClustersResponse(
            result="success",
            clusters=_format_cluster_rows(results),
            limit=effective_limit,
            offset=paged_filter.offset,
        )
    except mysql.connector.Error as err:
        logger.warning("Could not retrieve paged clusters: %s", err)
        return PagedRetrieveClustersResponse(
            result="failure",
            clusters=None,
            limit=0,
            offset=0,
            error=str(err),
        )
