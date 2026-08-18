"""Real-database integration tests for BulkClusterInsert (issue #140).

Validates two assumptions the mocked unit tests in
tests/test_BulkClusterInsert.py cannot: that MySQL's contiguous-id
guarantee for a simple multi-row INSERT actually holds, and that the
live `clusters` schema still matches CLUSTER_INSERT_COLUMNS.

Self-gates on a live connection probe (rather than an opt-in env var)
so it runs automatically wherever a real MySQL with the `lbnlfits`
schema is already available -- the CI job provisions exactly that via
`.github/workflows/python-package-uv.yml` -- and skips cleanly for
local devs without one running, with zero workflow changes required.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import mysql.connector  # noqa: E402
import pytest  # noqa: E402

from le_beta_vis.backend.BulkClusterInsert import (  # noqa: E402
    CLUSTER_INSERT_COLUMNS,
    bulk_insert_clusters,
)
from le_beta_vis.common.EPSDataClasses import ClusterStoreRequest  # noqa: E402

# Matches global:db:* defaults in defaults.yaml, which also match the
# CI job's DB_USER=root/DB_PASS=root/DB_NAME=lbnlfits env vars.
_DB_HOST = "localhost"
_DB_USER = "root"
_DB_PASSWORD = "root"
_DB_NAME = "lbnlfits"


def _probe_db_available() -> bool:
    try:
        conn = mysql.connector.connect(
            host=_DB_HOST,
            user=_DB_USER,
            password=_DB_PASSWORD,
            database=_DB_NAME,
            connection_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _probe_db_available(),
    reason="No local/CI MySQL with lbnlfits schema available; skipping bulk-insert integration test.",
)


def _make_cluster(fits_id: int, classification: str) -> ClusterStoreRequest:
    return ClusterStoreRequest(
        data=None,
        hdu_id=0,
        bounding_box={"top": 1, "left": 2, "bottom": 3, "right": 4},
        sigma_x=1.0,
        sigma_y=1.0,
        total_energy=100.0,
        total_pixels=10,
        fits_id=fits_id,
        classification=classification,
    )


class BulkClusterInsertIntegrationTest(unittest.TestCase):
    """Base fixture: real connection + a throwaway fits_files row."""

    _CLASSIFICATION_MARKER = "bulk_insert_integration_test"

    def setUp(self):
        self.conn = mysql.connector.connect(
            host=_DB_HOST, user=_DB_USER, password=_DB_PASSWORD, database=_DB_NAME
        )
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO fits_files (fileName, date, min, max, exposureTime) "
            "VALUES (%s, NOW(), %s, %s, %s)",
            (f"{self._CLASSIFICATION_MARKER}.fits", 0.0, 1.0, 1.0),
        )
        self.fits_id = cursor.lastrowid
        self.conn.commit()
        cursor.close()

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM clusters WHERE classification = %s",
            (self._CLASSIFICATION_MARKER,),
        )
        cursor.execute("DELETE FROM fits_files WHERE fitsID = %s", (self.fits_id,))
        self.conn.commit()
        cursor.close()
        self.conn.close()


class TestBulkInsertContiguousIds(BulkClusterInsertIntegrationTest):

    def test_bulk_insert_returns_contiguous_ids_matching_lastrowid(self):
        clusters = [
            _make_cluster(self.fits_id, self._CLASSIFICATION_MARKER) for _ in range(3)
        ]

        result = bulk_insert_clusters(self.conn, clusters)

        self.assertEqual(result.result, "success")
        self.assertEqual(len(result.cluster_ids), 3)

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT clusterID FROM clusters WHERE classification = %s ORDER BY clusterID",
            (self._CLASSIFICATION_MARKER,),
        )
        actual_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

        self.assertEqual(actual_ids, result.cluster_ids)
        first_id = result.cluster_ids[0]
        self.assertEqual(result.cluster_ids, [first_id, first_id + 1, first_id + 2])


class TestClusterColumnsMatchSchema(BulkClusterInsertIntegrationTest):

    def test_clusters_table_columns_match_CLUSTER_INSERT_COLUMNS(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'clusters'",
            (_DB_NAME,),
        )
        actual_columns = {row[0] for row in cursor.fetchall()}
        cursor.close()

        missing = set(CLUSTER_INSERT_COLUMNS) - actual_columns
        self.assertFalse(
            missing,
            f"clusters table is missing columns referenced by CLUSTER_INSERT_COLUMNS: {missing}",
        )


class TestBulkInsertFallbackRecovery(BulkClusterInsertIntegrationTest):

    def test_bulk_insert_falls_back_and_recovers_on_a_bad_row(self):
        nonexistent_fits_id = -1
        clusters = [
            _make_cluster(self.fits_id, self._CLASSIFICATION_MARKER),
            _make_cluster(nonexistent_fits_id, self._CLASSIFICATION_MARKER),
            _make_cluster(self.fits_id, self._CLASSIFICATION_MARKER),
        ]

        result = bulk_insert_clusters(self.conn, clusters)

        self.assertEqual(result.result, "partial")
        self.assertEqual(len(result.cluster_ids), 3)
        self.assertIsNotNone(result.cluster_ids[0])
        self.assertIsNone(result.cluster_ids[1])
        self.assertIsNotNone(result.cluster_ids[2])

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM clusters WHERE classification = %s",
            (self._CLASSIFICATION_MARKER,),
        )
        count = cursor.fetchone()[0]
        cursor.close()
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
