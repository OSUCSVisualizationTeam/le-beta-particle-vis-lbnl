"""Tests for BulkClusterInsert.bulk_insert_clusters (issue #140)."""

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

from le_beta_vis.backend.BulkClusterInsert import (  # noqa: E402
    CLUSTER_INSERT_COLUMNS,
    bulk_insert_clusters,
)
from le_beta_vis.common.EPSDataClasses import ClusterStoreRequest  # noqa: E402


def _make_cluster(fits_id: int = 1) -> ClusterStoreRequest:
    return ClusterStoreRequest(
        data=None,
        hdu_id=0,
        bounding_box={"top": 1, "left": 2, "bottom": 3, "right": 4},
        sigma_x=1.0,
        sigma_y=1.0,
        total_energy=100.0,
        total_pixels=10,
        fits_id=fits_id,
        classification="tritium",
    )


def _make_conn(lastrowid):
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = lastrowid
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestBulkInsertClustersFastPath(unittest.TestCase):

    def test_empty_clusters_fails_without_touching_conn(self):
        mock_conn = MagicMock()
        result = bulk_insert_clusters(mock_conn, [])
        self.assertEqual(result.result, "failure")
        self.assertIsNone(result.cluster_ids)
        mock_conn.cursor.assert_not_called()

    def test_success_executes_one_multi_row_insert_and_commits(self):
        mock_conn, mock_cursor = _make_conn(lastrowid=101)
        clusters = [_make_cluster(1), _make_cluster(2), _make_cluster(3)]

        result = bulk_insert_clusters(mock_conn, clusters)

        self.assertEqual(result.result, "success")
        self.assertEqual(result.cluster_ids, [101, 102, 103])
        mock_conn.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    def test_success_query_uses_expected_column_list(self):
        mock_conn, mock_cursor = _make_conn(lastrowid=1)
        bulk_insert_clusters(mock_conn, [_make_cluster()])

        query = mock_cursor.execute.call_args.args[0]
        for column in CLUSTER_INSERT_COLUMNS:
            self.assertIn(column, query)

    def test_success_flattened_values_match_row_count(self):
        mock_conn, mock_cursor = _make_conn(lastrowid=1)
        clusters = [_make_cluster(1), _make_cluster(2)]
        bulk_insert_clusters(mock_conn, clusters)

        values = mock_cursor.execute.call_args.args[1]
        self.assertEqual(len(values), len(CLUSTER_INSERT_COLUMNS) * len(clusters))


class TestBulkInsertClustersFallback(unittest.TestCase):

    def test_mysql_error_triggers_rollback_and_fallback(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = mysql.connector.Error("bulk boom")
        mock_conn.cursor.return_value = mock_cursor

        result = bulk_insert_clusters(mock_conn, [_make_cluster()])

        mock_conn.rollback.assert_called()
        self.assertIn(result.result, ("success", "partial", "failure"))

    def test_fallback_all_rows_succeed_reports_success(self):
        mock_conn = MagicMock()
        bulk_cursor = MagicMock()
        bulk_cursor.execute.side_effect = mysql.connector.Error("bulk boom")

        fallback_cursors = [MagicMock(lastrowid=101), MagicMock(lastrowid=102)]
        mock_conn.cursor.side_effect = [bulk_cursor] + fallback_cursors

        result = bulk_insert_clusters(mock_conn, [_make_cluster(1), _make_cluster(2)])

        self.assertEqual(result.result, "success")
        self.assertEqual(result.cluster_ids, [101, 102])

    def test_fallback_partial_failure_reports_partial_with_aligned_ids(self):
        mock_conn = MagicMock()
        bulk_cursor = MagicMock()
        bulk_cursor.execute.side_effect = mysql.connector.Error("bulk boom")

        good_cursor = MagicMock(lastrowid=101)
        bad_cursor = MagicMock()
        bad_cursor.execute.side_effect = mysql.connector.Error("row boom")
        mock_conn.cursor.side_effect = [bulk_cursor, good_cursor, bad_cursor]

        result = bulk_insert_clusters(mock_conn, [_make_cluster(1), _make_cluster(2)])

        self.assertEqual(result.result, "partial")
        self.assertEqual(result.cluster_ids, [101, None])
        self.assertIsNotNone(result.error)

    def test_fallback_all_rows_fail_reports_failure(self):
        mock_conn = MagicMock()
        bulk_cursor = MagicMock()
        bulk_cursor.execute.side_effect = mysql.connector.Error("bulk boom")

        row_cursor = MagicMock()
        row_cursor.execute.side_effect = mysql.connector.Error("row boom")
        mock_conn.cursor.side_effect = [bulk_cursor, row_cursor, row_cursor]

        result = bulk_insert_clusters(mock_conn, [_make_cluster(1), _make_cluster(2)])

        self.assertEqual(result.result, "failure")
        self.assertEqual(result.cluster_ids, [None, None])

    def test_no_lastrowid_on_bulk_path_triggers_fallback(self):
        mock_conn = MagicMock()
        bulk_cursor = MagicMock()
        bulk_cursor.lastrowid = 0
        fallback_cursor = MagicMock(lastrowid=55)
        mock_conn.cursor.side_effect = [bulk_cursor, fallback_cursor]

        result = bulk_insert_clusters(mock_conn, [_make_cluster()])

        self.assertEqual(result.result, "success")
        self.assertEqual(result.cluster_ids, [55])

    def test_fallback_reuses_same_column_driven_sql_builder(self):
        """The per-row fallback query must reference the same column list as the bulk path (DRY)."""
        mock_conn = MagicMock()
        bulk_cursor = MagicMock()
        bulk_cursor.execute.side_effect = mysql.connector.Error("bulk boom")
        fallback_cursor = MagicMock(lastrowid=101)
        mock_conn.cursor.side_effect = [bulk_cursor, fallback_cursor]

        bulk_insert_clusters(mock_conn, [_make_cluster()])

        fallback_query = fallback_cursor.execute.call_args.args[0]
        for column in CLUSTER_INSERT_COLUMNS:
            self.assertIn(column, fallback_query)
        self.assertNotIn("insert_cluster", fallback_query)


if __name__ == "__main__":
    unittest.main()
