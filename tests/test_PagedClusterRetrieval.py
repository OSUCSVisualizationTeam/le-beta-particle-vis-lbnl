"""Tests for PagedClusterRetrieval.paged_retrieve_clusters (issue #147)."""
from le_beta_vis.common.EPSDataClasses import ClusterPagedQueryFilter, ClusterQueryFilter
from le_beta_vis.backend.PagedClusterRetrieval import paged_retrieve_clusters
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# Add the src directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Keep tests importable even when mysql-connector isn't installed locally.
try:
    import mysql.connector  # type: ignore # noqa: F401
except ModuleNotFoundError:
    mysql_module = types.ModuleType("mysql")
    connector_module = types.ModuleType("mysql.connector")

    class _DummyMySQLError(Exception):
        pass

    connector_module.Error = _DummyMySQLError
    connector_module.connect = MagicMock()
    mysql_module.connector = connector_module
    sys.modules["mysql"] = mysql_module
    sys.modules["mysql.connector"] = connector_module


def _make_row(cluster_id: int) -> dict:
    return {
        "fitsFile": 1,
        "clusterID": cluster_id,
        "hdu_id": 0,
        "box_top": 1,
        "box_left": 2,
        "box_bottom": 3,
        "box_right": 4,
        "data": b"data",
        "totalEnergy": 1000.0,
        "sigmaX": 1.0,
        "sigmaY": 1.0,
        "classification": "tritium",
        "pixelCount": 10,
        "filename": "test.fits",
        "date": "2026-01-01",
    }


def _make_conn(rows):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestPagedRetrieveClusters(unittest.TestCase):
    """Unit tests for paged_retrieve_clusters."""

    def test_first_page_uses_requested_limit_and_offset(self):
        mock_conn, mock_cursor = _make_conn([_make_row(1), _make_row(2)])

        paged_filter = ClusterPagedQueryFilter(limit=10, offset=0)
        result = paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

        self.assertEqual(result["result"], "success")
        self.assertEqual(len(result["clusters"]), 2)
        self.assertEqual(result["limit"], 10)
        self.assertEqual(result["offset"], 0)

        sql, params = mock_cursor.execute.call_args[0]
        self.assertIn("LIMIT %s OFFSET %s", sql)
        self.assertEqual(params[-2:], (10, 0))

    def test_second_page_uses_offset(self):
        mock_conn, mock_cursor = _make_conn([_make_row(3)])

        paged_filter = ClusterPagedQueryFilter(limit=10, offset=50)
        result = paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

        self.assertEqual(result["offset"], 50)
        _, params = mock_cursor.execute.call_args[0]
        self.assertEqual(params[-2:], (10, 50))

    def test_empty_page_returns_empty_clusters(self):
        mock_conn, _ = _make_conn([])

        paged_filter = ClusterPagedQueryFilter(limit=10, offset=0)
        result = paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["clusters"], [])

    def test_default_limit_applied_when_limit_is_none(self):
        mock_conn, mock_cursor = _make_conn([_make_row(1)])

        paged_filter = ClusterPagedQueryFilter()
        result = paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

        self.assertEqual(result["limit"], 500)
        _, params = mock_cursor.execute.call_args[0]
        self.assertEqual(params[-2:], (500, 0))

    def test_filters_are_applied_to_where_clause(self):
        mock_conn, mock_cursor = _make_conn([_make_row(1)])

        paged_filter = ClusterPagedQueryFilter(
            filters=ClusterQueryFilter(fits_id=7, classification="tritium"),
            limit=10,
        )
        paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

        sql, params = mock_cursor.execute.call_args[0]
        self.assertIn("fitsFile = %s", sql)
        self.assertIn("classification = %s", sql)
        self.assertIn(7, params)
        self.assertIn("tritium", params)

    def test_limit_above_max_raises_value_error(self):
        mock_conn, _ = _make_conn([])
        paged_filter = ClusterPagedQueryFilter(limit=2500)

        with self.assertRaises(ValueError):
            paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

    def test_non_positive_default_limit_raises_value_error(self):
        mock_conn, _ = _make_conn([])
        paged_filter = ClusterPagedQueryFilter()

        with self.assertRaises(ValueError):
            paged_retrieve_clusters(mock_conn, paged_filter, default_limit=0, max_limit=2000)

    def test_mysql_error_returns_failure(self):
        mock_conn, mock_cursor = _make_conn([])
        mock_cursor.execute.side_effect = mysql.connector.Error("boom")

        paged_filter = ClusterPagedQueryFilter(limit=10)
        result = paged_retrieve_clusters(mock_conn, paged_filter, default_limit=500, max_limit=2000)

        self.assertEqual(result["result"], "failure")
        self.assertIsNone(result["clusters"])


if __name__ == "__main__":
    unittest.main()
