# Citation for Unit Tests: MockHistogramRenderer returning dummy PNG bytes
# Date: 02/27/2026
# Adapted from GitHub Copilot:
# I need to create unit tests for this file under the tests directory, name it test_EventPersistenceService.
# Ensure that all functions, edge cases, and paths are tested for storage and retrieval.
import zmq
from le_beta_vis.common.EPSDataClasses import (
    BulkClusterStoreRequest,
    BulkInsertClustersResponse,
    ClassificationUpdateRequest,
    ClusterPagedQueryFilter,
    ClusterQueryFilter,
    ClusterRecentQueryFilter,
    ClusterStoreRequest,
    FitsQueryFilter,
    FitsStoreRequest,
)
from le_beta_vis.backend.EventPersistenceService import (
    EventPersistence,
    FailedProcException,
    _parse_date_filter,
)
import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np
import sys
import os
import types

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


class TestParseDateFilter(unittest.TestCase):
    """Tests for _parse_date_filter, the EPS date-range entry validator."""

    def test_none_returns_none(self):
        self.assertIsNone(_parse_date_filter(None))

    def test_empty_dict_returns_none(self):
        self.assertIsNone(_parse_date_filter({}))

    def test_both_keys_none_returns_none(self):
        self.assertIsNone(_parse_date_filter({"start": None, "end": None}))

    def test_valid_pair_returns_datetimes(self):
        result = _parse_date_filter(
            {"start": "2025-01-01 00:00:00", "end": "2025-12-31 23:59:59"}
        )
        self.assertEqual(
            result,
            (
                datetime(2025, 1, 1, 0, 0, 0),
                datetime(2025, 12, 31, 23, 59, 59),
            ),
        )

    def test_only_start_raises(self):
        with self.assertRaises(ValueError):
            _parse_date_filter({"start": "2025-01-01 00:00:00"})

    def test_only_end_raises(self):
        with self.assertRaises(ValueError):
            _parse_date_filter({"end": "2025-01-01 00:00:00"})

    def test_non_string_start_raises(self):
        with self.assertRaises(TypeError):
            _parse_date_filter({"start": 12345, "end": "2025-12-31 23:59:59"})

    def test_non_string_end_raises(self):
        with self.assertRaises(TypeError):
            _parse_date_filter({"start": "2025-01-01 00:00:00", "end": 67890})

    def test_bad_format_slashes_raises(self):
        with self.assertRaises(ValueError):
            _parse_date_filter({"start": "2025/01/01", "end": "2025/12/31"})

    def test_bad_format_iso_t_separator_raises(self):
        """ISO 8601 with 'T' separator is *not* the agreed format."""
        with self.assertRaises(ValueError):
            _parse_date_filter(
                {"start": "2025-01-01T00:00:00", "end": "2025-12-31T23:59:59"}
            )

    def test_ordering_raises(self):
        with self.assertRaises(ValueError):
            _parse_date_filter(
                {"start": "2025-12-31 23:59:59", "end": "2025-01-01 00:00:00"}
            )


class TestFailedProcException(unittest.TestCase):
    """Test cases for the FailedProcException custom exception."""

    def test_failed_proc_exception_default_message(self):
        """Test FailedProcException with default message."""
        exception = FailedProcException()
        self.assertEqual(str(exception), "There was an issue running the stored procedure.")
        self.assertEqual(exception.message, "There was an issue running the stored procedure.")

    def test_failed_proc_exception_custom_message(self):
        """Test FailedProcException with custom message."""
        custom_msg = "Custom error message"
        exception = FailedProcException(custom_msg)
        self.assertEqual(str(exception), custom_msg)
        self.assertEqual(exception.message, custom_msg)

    def test_failed_proc_exception_is_exception(self):
        """Test that FailedProcException is an Exception."""
        exception = FailedProcException()
        self.assertIsInstance(exception, Exception)


class TestEventPersistenceInitialization(unittest.TestCase):
    """Test cases for EventPersistence initialization."""

    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_initialization(self, mock_config, mock_db_connect, mock_init_server):
        """Test EventPersistence initialization."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        self.assertIsNotNone(ep.config)
        self.assertEqual(ep.db_host, "localhost")
        self.assertEqual(ep.db_user, "test_user")
        self.assertEqual(ep.db_password, "test_pass")
        self.assertEqual(ep.database, "test_db")
        mock_db_connect.assert_called_once()
        mock_init_server.assert_called_once()


class TestEventPersistenceDatabaseConnection(unittest.TestCase):
    """Test cases for database connection."""

    @patch('le_beta_vis.backend.EventPersistenceService.mysql.connector.connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_db_connect_success(self, mock_config, mock_init_server, mock_mysql_connect):
        """Test successful database connection."""
        mock_connection = MagicMock()
        mock_mysql_connect.return_value = mock_connection

        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()
        conn = ep.db_connect()

        mock_mysql_connect.assert_called_with(
            host="localhost",
            user="test_user",
            password="test_pass",
            database="test_db"
        )
        self.assertEqual(conn, mock_connection)

    @patch('le_beta_vis.backend.EventPersistenceService.mysql.connector.connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_db_connect_failure(self, mock_config, mock_init_server, mock_mysql_connect):
        """Test database connection failure."""
        import mysql.connector
        mock_mysql_connect.side_effect = mysql.connector.Error("Connection failed")

        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        with patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect', side_effect=lambda: None):
            ep = EventPersistence()
            with patch('builtins.print') as mock_print:
                conn = ep.db_connect()
                # Connection failure is handled by db_connect method


class TestEventPersistenceStoreFits(unittest.TestCase):
    """Test cases for store_fits method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful fits storage."""
        # Setup mocks
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        # Mock callproc to return tuple where last element is the fits_id
        mock_cursor.callproc.return_value = (None, None, None, None, None, None, 42)

        ep = EventPersistence()
        ep.conn = mock_connection
        fits_request = FitsStoreRequest(
            filename="test.fits",
            date="2022-10-03",
            min=100,
            max=5000,
            exposure_time=3600,
        )

        result = ep.store_fits(fits_request)

        self.assertEqual(result, 42)
        mock_cursor.callproc.assert_called_once()
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_fits_failed_proc(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits storage with failed procedure."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        # Mock failed procedure (id <= 0)
        mock_cursor.callproc.return_value = (None, None, None, None, None, None, -1)

        ep = EventPersistence()
        ep.conn = mock_connection
        fits_request = FitsStoreRequest(
            filename="test.fits",
            date="2022-10-03",
            min=100,
            max=5000,
            exposure_time=3600,
        )

        with self.assertRaises(FailedProcException):
            ep.store_fits(fits_request)

        self.assertIsNone(ep.conn)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    def test_store_fits_reconnect_on_no_connection(self, mock_init_server, mock_config):
        """Test that store_fits reconnects if connection is lost."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.callproc.return_value = (None, None, None, None, None, None, 42)

        with patch.object(EventPersistence, 'db_connect', return_value=mock_connection):
            ep = EventPersistence()
            ep.conn = None
            fits_request = FitsStoreRequest(
                filename="test.fits",
                date="2022-10-03",
                min=100,
                max=5000,
                exposure_time=3600,
            )

            result = ep.store_fits(fits_request)
            self.assertEqual(result, 42)


class TestEventPersistenceStoreClusters(unittest.TestCase):
    """Test cases for store_cluster method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_cluster_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful cluster storage."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        # Mock callproc to return tuple where last element is the cluster_id
        mock_cursor.callproc.return_value = tuple([None] * 12 + [99])

        ep = EventPersistence()
        ep.conn = mock_connection

        # Create bounding box as dictionary
        mock_bbox = {
            "top": 10,
            "left": 20,
            "bottom": 30,
            "right": 40
        }

        cluster_request = ClusterStoreRequest(
            fits_id=1,
            data=np.array([[1, 2], [3, 4]]),
            hdu_id=0,
            bounding_box=mock_bbox,
            total_energy=5000,
            sigma_x=1.5,
            sigma_y=1.5,
            classification="alpha",
            total_pixels=100,
        )

        result = ep.store_cluster(cluster_request)

        self.assertEqual(result, 99)
        mock_cursor.callproc.assert_called_once()
        mock_connection.commit.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_cluster_failed_proc(self, mock_db_connect, mock_init_server, mock_config):
        """Test cluster storage with failed procedure."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        # Mock failed procedure (id <= 0)
        mock_cursor.callproc.return_value = tuple([None] * 12 + [-1])

        ep = EventPersistence()
        ep.conn = mock_connection

        mock_bbox = {
            "top": 10,
            "left": 20,
            "bottom": 30,
            "right": 40
        }

        cluster_request = ClusterStoreRequest(
            fits_id=1,
            data=np.array([[1, 2]]),
            hdu_id=0,
            bounding_box=mock_bbox,
            total_energy=5000,
            sigma_x=1.5,
            sigma_y=1.5,
            classification="alpha",
            total_pixels=100,
        )

        with self.assertRaises(FailedProcException):
            ep.store_cluster(cluster_request)


class TestEventPersistenceRetrieveFits(unittest.TestCase):
    """Test cases for retrieve_fits method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful fits retrieval."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        # Mock database results returned by a dictionary cursor
        mock_cursor.fetchall.return_value = [
            {
                "fitsID": 1,
                "fileName": "test.fits",
                "date": "2022-10-03",
                "min": 100,
                "max": 5000,
                "exposureTime": 3600,
            },
            {
                "fitsID": 2,
                "fileName": "test2.fits",
                "date": "2022-10-04",
                "min": 200,
                "max": 6000,
                "exposureTime": 3600,
            },
        ]

        ep = EventPersistence()
        ep.conn = mock_connection
        retrieval_fits = FitsQueryFilter(
            filename="test.fits",
            date_start=datetime(2022, 10, 3, 0, 0, 0),
            date_end=datetime(2022, 10, 3, 23, 59, 59),
        )

        result = ep.retrieve_fits(retrieval_fits)

        self.assertEqual(result["result"], "success")
        self.assertEqual(len(result["fits"]), 2)
        self.assertEqual(result["fits"][0]["fits_id"], 1)
        self.assertEqual(result["fits"][0]["filename"], "test.fits")

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_fits_with_multiple_filters(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits retrieval with multiple filter parameters."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        mock_cursor.fetchall.return_value = [
            {
                "fitsID": 1,
                "fileName": "test.fits",
                "date": "2022-10-03 00:00:00",
                "min": 100,
                "max": 5000,
                "exposureTime": 3600,
            }
        ]

        ep = EventPersistence()
        ep.conn = mock_connection
        retrieval_fits = FitsQueryFilter(
            filename="test.fits",
            fits_id=1,
            date_start=datetime(2022, 10, 3, 0, 0, 0),
            date_end=datetime(2022, 10, 3, 23, 59, 59),
            minimum=100,
            maximum=5000,
            exposure_time=3600,
        )

        result = ep.retrieve_fits(retrieval_fits)

        self.assertEqual(result["result"], "success")
        # Verify the SELECT query was called with proper WHERE clause
        mock_cursor.execute.assert_called_once()


class TestEventPersistenceRetrieveClusters(unittest.TestCase):
    """Test cases for retrieve_clusters method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_clusters_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful clusters retrieval."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        # Mock database results returned from a dictionary cursor
        mock_cursor.fetchall.return_value = [
            {
                "fitsFile": 1,
                "clusterID": 1,
                "hdu_id": 0,
                "box_top": 10,
                "box_left": 20,
                "box_bottom": 30,
                "box_right": 40,
                "data": b"data1",
                "totalEnergy": 5000,
                "sigmaX": 1.5,
                "sigmaY": 1.5,
                "classification": "alpha",
                "pixelCount": 100,
                "filename": "test.fits",
                "date": "2022-10-03",
            }
        ]

        ep = EventPersistence()
        ep.conn = mock_connection

        retrieval_clusters = ClusterQueryFilter(
            fits_id=1,
            date_start=datetime(2022, 10, 3, 0, 0, 0),
            date_end=datetime(2022, 10, 3, 23, 59, 59),
        )

        result = ep.retrieve_clusters(retrieval_clusters)

        self.assertEqual(result["result"], "success")
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(result["clusters"][0]["fits_id"], 1)
        self.assertEqual(result["clusters"][0]["cluster_id"], 1)


class TestEventPersistenceRecentRetrieval(unittest.TestCase):
    """Test cases for the RecentRetrieval sorted/paginated endpoint."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_recent_clusters_uses_order_and_pagination(
        self, mock_db_connect, mock_init_server, mock_config,
    ):
        """SQL must order by date DESC and apply LIMIT/OFFSET."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        mock_cursor.fetchall.return_value = []

        ep = EventPersistence()
        ep.conn = mock_connection
        retrieval_recent_clusters = ClusterRecentQueryFilter(limit=25, offset=50)

        ep.retrieve_recent_clusters(retrieval_recent_clusters)

        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]
        self.assertIn("ORDER BY fits_files.date DESC", sql)
        self.assertIn("LIMIT %s OFFSET %s", sql)
        self.assertEqual(params, (25, 50))

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_recent_clusters_shapes_response(
        self, mock_db_connect, mock_init_server, mock_config,
    ):
        """Result flows through process_retrieval_clusters."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection

        mock_cursor.fetchall.return_value = [
            {
                "fitsFile": 7,
                "clusterID": 101,
                "hdu_id": 0,
                "box_top": 1,
                "box_left": 2,
                "box_bottom": 3,
                "box_right": 4,
                "data": b"bytes",
                "totalEnergy": 1234,
                "sigmaX": 1.1,
                "sigmaY": 2.2,
                "classification": "alpha",
                "pixelCount": 12,
                "filename": "newest.fits",
                "date": "2026-04-14",
            }
        ]

        ep = EventPersistence()
        ep.conn = mock_connection
        retrieval_recent_clusters = ClusterRecentQueryFilter(limit=1, offset=0)

        result = ep.retrieve_recent_clusters(retrieval_recent_clusters)

        self.assertEqual(result["result"], "success")
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(result["clusters"][0]["cluster_id"], 101)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'retrieve_recent_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_dispatches_recent_retrieval(
        self, mock_db_connect, mock_retrieve_recent, mock_init_server, mock_config,
    ):
        """cluster_event routes 'RecentRetrieval' to retrieve_recent_clusters."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, None)

        mock_socket = MagicMock()
        mock_retrieve_recent.return_value = {
            "result": "success",
            "clusters": [],
        }

        ep = EventPersistence()
        request = {"Action": "RecentRetrieval", "limit": 10, "offset": 20}
        ep.cluster_event(request, mock_socket)

        mock_retrieve_recent.assert_called_once()
        recent_filter = mock_retrieve_recent.call_args.args[0]
        self.assertIsInstance(recent_filter, ClusterRecentQueryFilter)
        self.assertEqual(recent_filter.limit, 10)
        self.assertEqual(recent_filter.offset, 20)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "success")


class TestEventPersistencePagedRetrieval(unittest.TestCase):
    """Test cases for the PagedRetrieval endpoint (issue #147)."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'paged_retrieve_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_dispatches_paged_retrieval(
        self, mock_db_connect, mock_paged_retrieve, mock_init_server, mock_config,
    ):
        """cluster_event routes 'PagedRetrieval' to paged_retrieve_clusters."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, default)

        from le_beta_vis.common.EPSDataClasses import PagedRetrieveClustersResponse
        mock_socket = MagicMock()
        mock_paged_retrieve.return_value = PagedRetrieveClustersResponse(
            result="success", clusters=[], limit=10, offset=20
        )

        ep = EventPersistence()
        request = {"Action": "PagedRetrieval", "limit": 10, "offset": 20}
        ep.cluster_event(request, mock_socket)

        mock_paged_retrieve.assert_called_once()
        paged_filter = mock_paged_retrieve.call_args.args[0]
        self.assertIsInstance(paged_filter, ClusterPagedQueryFilter)
        self.assertEqual(paged_filter.limit, 10)
        self.assertEqual(paged_filter.offset, 20)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "success")

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService._paged_retrieve_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_paged_retrieve_clusters_uses_configured_limits(
        self, mock_db_connect, mock_paged_retrieve, mock_init_server, mock_config,
    ):
        """paged_retrieve_clusters injects eps:retrieval_limit_default/_max from config."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
            "eps:retrieval_limit_default": 100,
            "eps:retrieval_limit_max": 200,
        }.get(key, default)

        mock_connection = MagicMock()
        mock_db_connect.return_value = mock_connection
        from le_beta_vis.common.EPSDataClasses import PagedRetrieveClustersResponse
        mock_paged_retrieve.return_value = PagedRetrieveClustersResponse(
            result="success", clusters=[], limit=10, offset=0
        )

        ep = EventPersistence()
        ep.conn = mock_connection
        paged_filter = ClusterPagedQueryFilter(limit=10, offset=0)

        result = ep.paged_retrieve_clusters(paged_filter)

        mock_paged_retrieve.assert_called_once_with(mock_connection, paged_filter, 100, 200)
        self.assertTrue(result.is_success)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_paged_retrieval_over_limit_returns_failure(
        self, mock_db_connect, mock_init_server, mock_config,
    ):
        """A limit beyond eps:retrieval_limit_max surfaces as a failure response."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
            "eps:retrieval_limit_default": 500,
            "eps:retrieval_limit_max": 2000,
        }.get(key, default)

        mock_connection = MagicMock()
        mock_db_connect.return_value = mock_connection
        mock_socket = MagicMock()

        ep = EventPersistence()
        ep.conn = mock_connection
        request = {"Action": "PagedRetrieval", "limit": 99999, "offset": 0}
        ep.cluster_event(request, mock_socket)

        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "failure")


class TestEventPersistenceBulkStoreClusters(unittest.TestCase):
    """Test cases for the BulkStorage endpoint (issue #140)."""

    def _make_cluster_dict(self, fits_id=1):
        return ClusterStoreRequest(
            data=None, hdu_id=0,
            bounding_box={"top": 1, "left": 2, "bottom": 3, "right": 4},
            sigma_x=1.0, sigma_y=1.0,
            total_energy=100.0, total_pixels=10,
            fits_id=fits_id, classification="tritium",
        ).to_eps_dict()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService._bulk_insert_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_bulk_store_clusters_connects_lazily_and_delegates(
        self, mock_db_connect, mock_bulk_insert, mock_init_server, mock_config,
    ):
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, default)

        mock_connection = MagicMock()
        mock_db_connect.return_value = mock_connection
        mock_bulk_insert.return_value = BulkInsertClustersResponse(
            result="success", cluster_ids=[1, 2]
        )

        ep = EventPersistence()
        ep.conn = None
        bulk_request = BulkClusterStoreRequest(
            clusters=[ClusterStoreRequest.from_eps_dict(self._make_cluster_dict())]
        )

        result = ep.bulk_store_clusters(bulk_request)

        # db_connect is called once in __init__ and once more here since
        # conn was reset to None, proving the lazy-reconnect path is used.
        self.assertEqual(mock_db_connect.call_count, 2)
        mock_bulk_insert.assert_called_once_with(mock_connection, bulk_request.clusters)
        self.assertTrue(result.is_success)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'bulk_store_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_dispatches_bulk_storage_success(
        self, mock_db_connect, mock_bulk_store, mock_init_server, mock_config,
    ):
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, default)

        mock_socket = MagicMock()
        mock_bulk_store.return_value = BulkInsertClustersResponse(
            result="success", cluster_ids=[101, 102]
        )

        ep = EventPersistence()
        request = {
            "Action": "BulkStorage",
            "clusters": [self._make_cluster_dict(1), self._make_cluster_dict(2)],
        }
        ep.cluster_event(request, mock_socket)

        mock_bulk_store.assert_called_once()
        bulk_request = mock_bulk_store.call_args.args[0]
        self.assertIsInstance(bulk_request, BulkClusterStoreRequest)
        self.assertEqual(len(bulk_request.clusters), 2)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "success")
        self.assertEqual(sent["cluster_ids"], [101, 102])

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'bulk_store_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_dispatches_bulk_storage_partial(
        self, mock_db_connect, mock_bulk_store, mock_init_server, mock_config,
    ):
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, default)

        mock_socket = MagicMock()
        mock_bulk_store.return_value = BulkInsertClustersResponse(
            result="partial", cluster_ids=[101, None], error="1/2 fallback rows failed"
        )

        ep = EventPersistence()
        request = {
            "Action": "BulkStorage",
            "clusters": [self._make_cluster_dict(1), self._make_cluster_dict(2)],
        }
        ep.cluster_event(request, mock_socket)

        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "partial")
        self.assertEqual(sent["cluster_ids"], [101, None])

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_bulk_storage_empty_clusters_returns_failure(
        self, mock_db_connect, mock_init_server, mock_config,
    ):
        """An empty clusters list surfaces as a failure response, not an uncaught exception."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, default)

        mock_socket = MagicMock()
        ep = EventPersistence()
        request = {"Action": "BulkStorage", "clusters": []}
        ep.cluster_event(request, mock_socket)

        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "failure")


class TestEventPersistenceClassifyCluster(unittest.TestCase):
    """Test cases for classify_cluster method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful classification update."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        mock_cursor.callproc.return_value = ("tritium", 123, 1)

        ep = EventPersistence()
        ep.conn = mock_connection
        cluster_to_classify = ClassificationUpdateRequest(
            cluster_id=123,
            classification="tritium",
        )

        result = ep.classify_cluster(cluster_to_classify)

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["updated"], 1)
        mock_cursor.callproc.assert_called_once_with(
            "insert_classifications", ("tritium", 123, None)
        )
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_no_rows_updated(self, mock_db_connect, mock_init_server, mock_config):
        """Test classification update where no row is changed."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        mock_cursor.callproc.return_value = ("tritium", 123, 0)

        ep = EventPersistence()
        ep.conn = mock_connection
        cluster_to_classify = ClassificationUpdateRequest(
            cluster_id=123,
            classification="tritium",
        )

        result = ep.classify_cluster(cluster_to_classify)

        self.assertEqual(result["result"], "failure")
        self.assertIn("No clusters were updated", result["error"])
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_failed_proc_output(self, mock_db_connect, mock_init_server, mock_config):
        """Test classification update where procedure reports failure."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        mock_cursor.callproc.return_value = ("tritium", 123, -1)

        ep = EventPersistence()
        ep.conn = mock_connection
        cluster_to_classify = ClassificationUpdateRequest(
            cluster_id=123,
            classification="tritium",
        )

        with self.assertRaises(FailedProcException):
            ep.classify_cluster(cluster_to_classify)

        mock_connection.close.assert_called_once()
        self.assertIsNone(ep.conn)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    def test_classify_cluster_reconnect_on_no_connection(self, mock_init_server, mock_config):
        """Test classify_cluster reconnects when connection is missing."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.callproc.return_value = ("alpha", 7, 1)

        with patch.object(EventPersistence, 'db_connect', return_value=mock_connection):
            ep = EventPersistence()
            ep.conn = None
            cluster_to_classify = ClassificationUpdateRequest(
                cluster_id=7,
                classification="alpha",
            )

            result = ep.classify_cluster(cluster_to_classify)

            self.assertEqual(result["result"], "success")
            self.assertEqual(result["updated"], 1)


class TestEventPersistenceProcessRetrievalFits(unittest.TestCase):
    """Test cases for process_retrieval_fits method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing successful fits retrieval results."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        results = [
            {
                "fitsID": 1,
                "fileName": "test1.fits",
                "date": "2022-10-03",
                "min": 100,
                "max": 5000,
                "exposureTime": 3600,
            },
            {
                "fitsID": 2,
                "fileName": "test2.fits",
                "date": "2022-10-04",
                "min": 200,
                "max": 6000,
                "exposureTime": 3600,
            },
        ]

        response = ep.process_retrieval_fits(results)

        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["fits"]), 2)
        self.assertEqual(response["fits"][0]["fits_id"], 1)
        self.assertEqual(response["fits"][0]["filename"], "test1.fits")
        self.assertEqual(response["fits"][0]["min"], 100)
        self.assertEqual(response["fits"][0]["max"], 5000)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_fits_empty_results(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing empty fits retrieval results."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        results = []
        response = ep.process_retrieval_fits(results)

        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["fits"]), 0)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_fits_error(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing fits retrieval with error."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        error_msg = "Database error occurred"
        response = ep.process_retrieval_fits(error_msg)

        self.assertEqual(response["result"], "failure")
        self.assertIsNone(response["fits"])
        self.assertEqual(response["error"], error_msg)


class TestEventPersistenceProcessRetrievalClusters(unittest.TestCase):
    """Test cases for process_retrieval_clusters method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_clusters_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing successful clusters retrieval results."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        # Dictionary rows returned by mysql cursor(dictionary=True)
        results = [
            {
                "fitsFile": 1,
                "clusterID": 1,
                "hdu_id": 0,
                "box_top": 10,
                "box_left": 20,
                "box_bottom": 30,
                "box_right": 40,
                "data": b"data1",
                "totalEnergy": 5000,
                "sigmaX": 1.5,
                "sigmaY": 1.5,
                "classification": "alpha",
                "pixelCount": 100,
                "filename": "test1.fits",
                "date": "2022-10-03",
            },
            {
                "fitsFile": 1,
                "clusterID": 2,
                "hdu_id": 0,
                "box_top": 15,
                "box_left": 25,
                "box_bottom": 35,
                "box_right": 45,
                "data": b"data2",
                "totalEnergy": 6000,
                "sigmaX": 2.0,
                "sigmaY": 2.0,
                "classification": "beta",
                "pixelCount": 150,
                "filename": "test2.fits",
                "date": "2022-10-04",
            },
        ]

        response = ep.process_retrieval_clusters(results)

        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["clusters"]), 2)
        self.assertEqual(response["clusters"][0]["fits_id"], 1)
        self.assertEqual(response["clusters"][0]["cluster_id"], 1)
        self.assertEqual(response["clusters"][0]["classification"], "alpha")

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_clusters_empty_results(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing empty clusters retrieval results."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        results = []
        response = ep.process_retrieval_clusters(results)

        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["clusters"]), 0)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_clusters_error(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing clusters retrieval with error."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        ep = EventPersistence()

        error_msg = "Database error occurred"
        response = ep.process_retrieval_clusters(error_msg)

        self.assertEqual(response["result"], "failure")
        self.assertIsNone(response["clusters"])
        self.assertEqual(response["error"], error_msg)


class TestEventPersistenceClusterEvent(unittest.TestCase):
    """Test cases for cluster_event method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_storage_success(self, mock_db_connect, mock_store_cluster, mock_init_server, mock_config):
        """Test cluster event with Storage action."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_store_cluster.return_value = 42

        ep = EventPersistence()

        request = {
            "Action": "Storage",
            "data": [1, 2, 3],
            "bounding_box": {"top": 10, "left": 20, "bottom": 30, "right": 40},
            "hdu_id": 0,
            "sigmaX": 1.5,
            "sigmaY": 1.5,
            "total_energy": 5000,
            "total_pixels": 100,
            "fits_id": 1,
            "classification": "alpha"
        }

        ep.cluster_event(request, mock_socket)

        # Should send success with cluster_id
        mock_socket.send_json.assert_called_once()
        call_args = mock_socket.send_json.call_args[0][0]
        self.assertEqual(call_args["result"], "success")
        self.assertEqual(call_args["cluster_id"], 42)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_storage_failure(self, mock_db_connect, mock_store_cluster, mock_init_server, mock_config):
        """Test cluster event with Storage action that fails."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_store_cluster.return_value = None

        ep = EventPersistence()

        request = {
            "Action": "Storage",
            "data": [1, 2, 3],
            "bounding_box": {"top": 10, "left": 20, "bottom": 30, "right": 40},
            "hdu_id": 0,
            "sigmaX": 1.5,
            "sigmaY": 1.5,
            "total_energy": 5000,
            "total_pixels": 100,
            "fits_id": 1,
            "classification": "alpha"
        }

        ep.cluster_event(request, mock_socket)

        # Should send failure
        mock_socket.send_json.assert_called_once()
        call_args = mock_socket.send_json.call_args[0][0]
        self.assertEqual(call_args["result"], "failure")
        self.assertIsNone(call_args["cluster_id"])

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'retrieve_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_retrieval(self, mock_db_connect, mock_retrieve_clusters, mock_init_server, mock_config):
        """Test cluster event with Retrieval action."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_retrieve_clusters.return_value = {"result": "success", "clusters": []}

        ep = EventPersistence()

        request = {
            "Action": "Retrieval",
            "data": None,
            "cluster_id": 1,
            "bounding_box": None,
            "date": None,
            "hdu_id": None,
            "sigmaX": None,
            "sigmaY": None,
            "total_energy": None,
            "total_pixels": None,
            "fits_id": 1,
            "classification": None
        }

        ep.cluster_event(request, mock_socket)

        mock_socket.send_json.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'classify_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_update_classification_success(
            self, mock_db_connect, mock_classify_cluster, mock_init_server, mock_config):
        """Test cluster event with UpdateClassification action."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_classify_cluster.return_value = {"result": "success", "updated": 1}

        ep = EventPersistence()

        request = {
            "Action": "UpdateClassification",
            "cluster_id": 123,
            "classification": "tritium",
        }

        ep.cluster_event(request, mock_socket)

        classify_request = mock_classify_cluster.call_args.args[0]
        self.assertIsInstance(classify_request, ClassificationUpdateRequest)
        self.assertEqual(classify_request.cluster_id, 123)
        self.assertEqual(classify_request.classification, "tritium")
        mock_socket.send_json.assert_called_once_with({"result": "success", "updated": 1})

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'classify_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_update_classification_exception(
            self, mock_db_connect, mock_classify_cluster, mock_init_server, mock_config):
        """Test UpdateClassification action when classify_cluster raises exception."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_classify_cluster.side_effect = FailedProcException("proc failed")

        ep = EventPersistence()

        request = {
            "Action": "UpdateClassification",
            "cluster_id": 55,
            "classification": "beta",
        }

        ep.cluster_event(request, mock_socket)

        mock_socket.send_json.assert_called_once()
        response = mock_socket.send_json.call_args[0][0]
        self.assertEqual(response["result"], "failure")
        self.assertIn("proc failed", response["error"])

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_missing_required_field(self, mock_db_connect, mock_store_cluster, mock_init_server, mock_config):
        """Test cluster event with missing required field."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_store_cluster.return_value = None

        ep = EventPersistence()

        request = {
            "Action": "Storage",
            "data": [1, 2, 3],
            # Missing required fields
        }

        ep.cluster_event(request, mock_socket)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "failure")

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.logger')
    def test_cluster_event_unknown_action_logs_error_and_responds_failure(
        self, mock_logger, mock_db_connect, mock_init_server, mock_config,
    ):
        """An unrecognized Action is logged as an error and does not leave the caller's REQ socket
        hanging without a response."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key, default=None: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db",
        }.get(key, default)

        mock_socket = MagicMock()
        ep = EventPersistence()

        request = {"Action": "NotARealAction"}
        ep.cluster_event(request, mock_socket)

        mock_logger.error.assert_called_once()
        self.assertIn("NotARealAction", mock_logger.error.call_args.args[0])

        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "failure")
        self.assertIn("NotARealAction", sent["error"])


class TestEventPersistenceFitsEvent(unittest.TestCase):
    """Test cases for fits_event method."""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_fits_event_storage_success(self, mock_db_connect, mock_store_fits, mock_init_server, mock_config):
        """Test fits event with Storage action."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_store_fits.return_value = 42

        ep = EventPersistence()

        request = {
            "Action": "Storage",
            "filename": "test.fits",
            "date": "2022-10-03",
            "min": 100,
            "max": 5000,
            "exposure_time": 3600
        }

        ep.fits_event(request, mock_socket)

        # Should send success with fits_id
        mock_socket.send_json.assert_called_once()
        call_args = mock_socket.send_json.call_args[0][0]
        self.assertEqual(call_args["result"], "success")
        self.assertEqual(call_args["fits_id"], 42)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_fits_event_storage_failure(self, mock_db_connect, mock_store_fits, mock_init_server, mock_config):
        """Test fits event with Storage action that fails."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_store_fits.return_value = None

        ep = EventPersistence()

        request = {
            "Action": "Storage",
            "filename": "test.fits",
            "date": "2022-10-03",
            "min": 100,
            "max": 5000,
            "exposure_time": 3600
        }

        ep.fits_event(request, mock_socket)

        # Should send failure
        mock_socket.send_json.assert_called_once()
        call_args = mock_socket.send_json.call_args[0][0]
        self.assertEqual(call_args["result"], "failure")
        self.assertIsNone(call_args["fits_id"])

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'retrieve_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_fits_event_retrieval(self, mock_db_connect, mock_retrieve_fits, mock_init_server, mock_config):
        """Test fits event with Retrieval action."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_retrieve_fits.return_value = {"result": "success", "fits": []}

        ep = EventPersistence()

        request = {
            "Action": "Retrieval",
            "filename": None,
            "fits_id": 1,
            "date": None,
            "minimum": None,
            "maximum": None,
            "exposure_time": None
        }

        ep.fits_event(request, mock_socket)

        mock_socket.send_json.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'retrieve_fits')
    @patch.object(EventPersistence, 'retrieve_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_fits_event_clusters(self, mock_db_connect, mock_retrieve_clusters,
                                 mock_retrieve_fits, mock_init_server, mock_config):
        """Test fits event with Clusters action."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_retrieve_fits.return_value = {"result": "success", "fits": [{"fits_id": 1}]}
        mock_retrieve_clusters.return_value = {"result": "success", "clusters": []}

        ep = EventPersistence()

        request = {
            "Action": "Clusters",
            "filename": None,
            "fits_id": None,
            "date": None,
            "minimum": None,
            "maximum": None,
            "exposure_time": None
        }

        ep.fits_event(request, mock_socket)

        mock_socket.send_json.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_fits_event_missing_required_field(self, mock_db_connect, mock_store_fits, mock_init_server, mock_config):
        """Test fits event with missing required field."""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)

        mock_socket = MagicMock()
        mock_store_fits.return_value = None

        ep = EventPersistence()

        request = {
            "Action": "Storage",
            # Missing required fields like 'filename'
        }
        ep.fits_event(request, mock_socket)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "failure")


def _configured_config_mock(overrides=None):
    """Builds a mock config whose `.get`/`.get_int` resolve from a dict,
    matching the pattern the rest of this file uses for `.get` but also
    covering `.get_int`, which db_connect()/the status-broadcast helpers
    use for the new retry/broadcast keys."""
    values = {
        "global:db:hostname": "localhost",
        "global:db:username": "test_user",
        "global:db:password": "test_pass",
        "global:db:database": "test_db",
        "eps:db_connect_retry_max_attempts": 20,
        "eps:db_connect_retry_backoff_ms": 0,
        "eps:startup_status_broadcast_interval_ms": 250,
        "eps:startup_status_broadcast_window_ms": 3000,
    }
    values.update(overrides or {})

    mock_config = MagicMock()
    mock_config.get.side_effect = lambda key, default=None: values.get(key, default)
    mock_config.get_int.side_effect = lambda key, default=None, **kw: values.get(key, default)
    return mock_config


class TestEventPersistenceDatabaseConnectionRetry(unittest.TestCase):
    """Test cases for db_connect()'s bounded retry/backoff loop."""

    @patch('le_beta_vis.backend.EventPersistenceService.time.sleep')
    @patch('le_beta_vis.backend.EventPersistenceService.mysql.connector.connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_retries_then_succeeds(self, mock_config_cls, mock_init_server, mock_mysql_connect, mock_sleep):
        import mysql.connector
        mock_config_cls.return_value = _configured_config_mock(
            {"eps:db_connect_retry_max_attempts": 5}
        )
        mock_connection = MagicMock()
        mock_mysql_connect.side_effect = [
            mysql.connector.Error("down"),
            mysql.connector.Error("still down"),
            mock_connection,
        ]
        mock_signals = MagicMock()

        with patch(
            'le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect',
            side_effect=lambda: None,
        ):
            ep = EventPersistence(startup_signals=mock_signals)

        with patch('builtins.print'):
            conn = ep.db_connect()

        self.assertEqual(conn, mock_connection)
        self.assertEqual(mock_mysql_connect.call_count, 3)
        self.assertEqual(mock_signals.publish_status.call_count, 2)
        first_call, second_call = mock_signals.publish_status.call_args_list
        self.assertEqual(
            first_call.kwargs,
            {"db_connected": False, "sockets_bound": False, "attempt": 1, "max_attempts": 5},
        )
        self.assertEqual(
            second_call.kwargs,
            {"db_connected": False, "sockets_bound": False, "attempt": 2, "max_attempts": 5},
        )

    @patch('le_beta_vis.backend.EventPersistenceService.time.sleep')
    @patch('le_beta_vis.backend.EventPersistenceService.mysql.connector.connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_exhausts_retries_then_gives_up(self, mock_config_cls, mock_init_server, mock_mysql_connect, mock_sleep):
        import mysql.connector
        mock_config_cls.return_value = _configured_config_mock(
            {"eps:db_connect_retry_max_attempts": 3}
        )
        mock_mysql_connect.side_effect = mysql.connector.Error("down")
        mock_signals = MagicMock()

        with patch(
            'le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect',
            side_effect=lambda: None,
        ):
            ep = EventPersistence(startup_signals=mock_signals)

        with patch('builtins.print'):
            conn = ep.db_connect()

        self.assertIsNone(conn)
        self.assertEqual(mock_mysql_connect.call_count, 3)
        self.assertEqual(mock_signals.publish_status.call_count, 3)

    @patch('le_beta_vis.backend.EventPersistenceService.time.sleep')
    @patch('le_beta_vis.backend.EventPersistenceService.mysql.connector.connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_no_startup_signals_does_not_raise(self, mock_config_cls, mock_init_server, mock_mysql_connect, mock_sleep):
        """startup_signals=None (the default) must not break the retry loop."""
        import mysql.connector
        mock_config_cls.return_value = _configured_config_mock(
            {"eps:db_connect_retry_max_attempts": 2}
        )
        mock_mysql_connect.side_effect = mysql.connector.Error("down")

        with patch(
            'le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect',
            side_effect=lambda: None,
        ):
            ep = EventPersistence()

        with patch('builtins.print'):
            conn = ep.db_connect()

        self.assertIsNone(conn)
        self.assertEqual(mock_mysql_connect.call_count, 2)


class TestPublishInitialStatus(unittest.TestCase):
    """Test cases for EventPersistence._publish_initial_status()."""

    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_no_startup_signals_publishes_nothing(self, mock_config_cls, mock_db_connect, mock_init_server):
        mock_config_cls.return_value = _configured_config_mock()
        ep = EventPersistence()

        deadline, interval_s, next_at = ep._publish_initial_status()

        self.assertIsNone(deadline)
        self.assertEqual(interval_s, 0.0)
        self.assertEqual(next_at, 0.0)

    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_publishes_current_connection_state(self, mock_config_cls, mock_db_connect, mock_init_server):
        mock_config_cls.return_value = _configured_config_mock(
            {
                "eps:startup_status_broadcast_interval_ms": 250,
                "eps:startup_status_broadcast_window_ms": 3000,
            }
        )
        mock_signals = MagicMock()
        ep = EventPersistence(startup_signals=mock_signals)
        ep.conn = MagicMock()  # simulate a live connection

        deadline, interval_s, next_at = ep._publish_initial_status()

        mock_signals.publish_status.assert_called_once_with(
            db_connected=True, sockets_bound=True
        )
        self.assertIsNotNone(deadline)
        self.assertAlmostEqual(interval_s, 0.25)
        self.assertGreater(next_at, 0.0)


class TestMaybeRebroadcastStatus(unittest.TestCase):
    """Test cases for EventPersistence._maybe_rebroadcast_status()."""

    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def _make_ep(self, mock_config_cls, mock_db_connect, mock_init_server):
        mock_config_cls.return_value = _configured_config_mock()
        mock_db_connect.return_value = None
        ep = EventPersistence()
        ep.conn = None
        return ep

    def test_none_deadline_is_noop(self):
        ep = self._make_ep()
        ep._startup_signals = MagicMock()

        deadline, next_at = ep._maybe_rebroadcast_status(None, 999.0, 0.25)

        self.assertIsNone(deadline)
        self.assertEqual(next_at, 999.0)
        ep._startup_signals.publish_status.assert_not_called()

    @patch('le_beta_vis.backend.EventPersistenceService.time.monotonic')
    def test_publishes_when_due_and_before_deadline(self, mock_monotonic):
        ep = self._make_ep()
        mock_signals = MagicMock()
        ep._startup_signals = mock_signals
        mock_monotonic.return_value = 10.0

        deadline, next_at = ep._maybe_rebroadcast_status(
            broadcast_deadline=20.0, next_broadcast_at=10.0, broadcast_interval_s=0.25
        )

        mock_signals.publish_status.assert_called_once_with(
            db_connected=False, sockets_bound=True
        )
        self.assertEqual(deadline, 20.0)
        self.assertEqual(next_at, 10.25)

    @patch('le_beta_vis.backend.EventPersistenceService.time.monotonic')
    def test_no_publish_before_next_broadcast(self, mock_monotonic):
        ep = self._make_ep()
        mock_signals = MagicMock()
        ep._startup_signals = mock_signals
        mock_monotonic.return_value = 10.0

        deadline, next_at = ep._maybe_rebroadcast_status(
            broadcast_deadline=20.0, next_broadcast_at=15.0, broadcast_interval_s=0.25
        )

        mock_signals.publish_status.assert_not_called()
        self.assertEqual(deadline, 20.0)
        self.assertEqual(next_at, 15.0)

    @patch('le_beta_vis.backend.EventPersistenceService.time.monotonic')
    def test_deadline_elapsed_stops_broadcasting(self, mock_monotonic):
        ep = self._make_ep()
        mock_signals = MagicMock()
        ep._startup_signals = mock_signals
        mock_monotonic.return_value = 25.0

        deadline, next_at = ep._maybe_rebroadcast_status(
            broadcast_deadline=20.0, next_broadcast_at=21.0, broadcast_interval_s=0.25
        )

        mock_signals.publish_status.assert_not_called()
        self.assertIsNone(deadline)


if __name__ == '__main__':
    unittest.main()
