# Citation for Unit Tests: MockHistogramRenderer returning dummy PNG bytes
# Date: 02/27/2026
# Adapted from GitHub Copilot:
# I need to create unit tests for this file under the tests directory, name it test_EventPersistenceService.
# Ensure that all functions, edge cases, and paths are tested for storage and retrieval.
import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np
import sys
import os

# Add the src directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from le_beta_vis.backend.EventPersistenceService import (
    EventPersistence,
    FailedProcException,
    _parse_date_filter,
)
import zmq


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
    """Test cases for the FailedProcException custom exception"""

    def test_failed_proc_exception_default_message(self):
        """Test FailedProcException with default message"""
        exception = FailedProcException()
        self.assertEqual(str(exception), "There was an issue running the stored procedure.")
        self.assertEqual(exception.message, "There was an issue running the stored procedure.")

    def test_failed_proc_exception_custom_message(self):
        """Test FailedProcException with custom message"""
        custom_msg = "Custom error message"
        exception = FailedProcException(custom_msg)
        self.assertEqual(str(exception), custom_msg)
        self.assertEqual(exception.message, custom_msg)

    def test_failed_proc_exception_is_exception(self):
        """Test that FailedProcException is an Exception"""
        exception = FailedProcException()
        self.assertIsInstance(exception, Exception)


class TestEventPersistenceInitialization(unittest.TestCase):
    """Test cases for EventPersistence initialization"""

    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_initialization(self, mock_config, mock_db_connect, mock_init_server):
        """Test EventPersistence initialization"""
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
    """Test cases for database connection"""

    @patch('le_beta_vis.backend.EventPersistenceService.mysql.connector.connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    def test_db_connect_success(self, mock_config, mock_init_server, mock_mysql_connect):
        """Test successful database connection"""
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
        """Test database connection failure"""
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
    """Test cases for store_fits method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful fits storage"""
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
        ep.fits_to_store = {
            "filename": "test.fits",
            "date": "2022-10-03",
            "minimum": 100,
            "maximum": 5000,
            "exposure_time": 3600
        }

        result = ep.store_fits()

        self.assertEqual(result, 42)
        mock_cursor.callproc.assert_called_once()
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_fits_failed_proc(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits storage with failed procedure"""
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
        ep.fits_to_store = {
            "filename": "test.fits",
            "date": "2022-10-03",
            "minimum": 100,
            "maximum": 5000,
            "exposure_time": 3600
        }

        with self.assertRaises(FailedProcException):
            ep.store_fits()

        self.assertIsNone(ep.conn)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    def test_store_fits_reconnect_on_no_connection(self, mock_init_server, mock_config):
        """Test that store_fits reconnects if connection is lost"""
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
            ep.fits_to_store = {
                "filename": "test.fits",
                "date": "2022-10-03",
                "minimum": 100,
                "maximum": 5000,
                "exposure_time": 3600
            }

            result = ep.store_fits()
            self.assertEqual(result, 42)


class TestEventPersistenceStoreClusters(unittest.TestCase):
    """Test cases for store_cluster method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_cluster_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful cluster storage"""
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

        ep.cluster_to_store = {
            "fits_id": 1,
            "data": np.array([[1, 2], [3, 4]]),
            "hdu_id": 0,
            "bounding_box": mock_bbox,
            "total_energy": 5000,
            "sigmaX": 1.5,
            "sigmaY": 1.5,
            "classification": "alpha",
            "total_pixels": 100
        }

        result = ep.store_cluster()

        self.assertEqual(result, 99)
        mock_cursor.callproc.assert_called_once()
        mock_connection.commit.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_store_cluster_failed_proc(self, mock_db_connect, mock_init_server, mock_config):
        """Test cluster storage with failed procedure"""
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

        ep.cluster_to_store = {
            "fits_id": 1,
            "data": np.array([[1, 2]]),
            "hdu_id": 0,
            "bounding_box": mock_bbox,
            "total_energy": 5000,
            "sigmaX": 1.5,
            "sigmaY": 1.5,
            "classification": "alpha",
            "total_pixels": 100
        }

        with self.assertRaises(FailedProcException):
            ep.store_cluster()


class TestEventPersistenceRetrieveFits(unittest.TestCase):
    """Test cases for retrieve_fits method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful fits retrieval"""
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

        # Mock database results: (fitsID, fileName, date, min, max, exposureTime)
        mock_cursor.fetchall.return_value = [
            (1, "test.fits", "2022-10-03", 100, 5000, 3600),
            (2, "test2.fits", "2022-10-04", 200, 6000, 3600)
        ]

        ep = EventPersistence()
        ep.conn = mock_connection
        ep.retrieval_fits = {
            "filename": "test.fits",
            "fits_id": None,
            "date": None,
            "minimum": None,
            "maximum": None,
            "exposure_time": None
        }

        result = ep.retrieve_fits()

        self.assertEqual(result["result"], "success")
        self.assertEqual(len(result["fits"]), 2)
        self.assertEqual(result["fits"][0]["fits_id"], 1)
        self.assertEqual(result["fits"][0]["filename"], "test.fits")

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_fits_with_multiple_filters(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits retrieval with multiple filter parameters"""
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

        mock_cursor.fetchall.return_value = [(1, "test.fits", "2022-10-03 00:00:00", 100, 5000, 3600)]

        ep = EventPersistence()
        ep.conn = mock_connection
        ep.retrieval_fits = {
            "filename": "test.fits",
            "fits_id": 1,
            "date": {"start": "2022-10-03 00:00:00", "end": "2022-10-03 23:59:59"},
            "minimum": 100,
            "maximum": 5000,
            "exposure_time": 3600
        }

        result = ep.retrieve_fits()

        self.assertEqual(result["result"], "success")
        # Verify the SELECT query was called with proper WHERE clause
        mock_cursor.execute.assert_called_once()


class TestEventPersistenceRetrieveClusters(unittest.TestCase):
    """Test cases for retrieve_clusters method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_retrieve_clusters_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful clusters retrieval"""
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

        ep.retrieval_clusters = {
            "data": None,
            "hdu_id": None,
            "cluster_id": None,
            "bounding_box": None,
            "date": None,
            "fits_id": 1,
            "sigmaX": None,
            "sigmaY": None,
            "total_energy": None,
            "total_pixels": None,
            "classification": None
        }

        result = ep.retrieve_clusters()

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
        ep.retrieval_recent_clusters = {"limit": 25, "offset": 50}

        ep.retrieve_recent_clusters()

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
        ep.retrieval_recent_clusters = {"limit": 1, "offset": 0}

        result = ep.retrieve_recent_clusters()

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
        self.assertEqual(ep.retrieval_recent_clusters["limit"], 10)
        self.assertEqual(ep.retrieval_recent_clusters["offset"], 20)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        self.assertEqual(sent["result"], "success")


class TestEventPersistenceClassifyCluster(unittest.TestCase):
    """Test cases for classify_cluster method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful classification update"""
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
        ep.cluster_to_classify = {
            "cluster_id": 123,
            "classification": "tritium",
        }

        result = ep.classify_cluster()

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
        """Test classification update where no row is changed"""
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
        ep.cluster_to_classify = {
            "cluster_id": 123,
            "classification": "tritium",
        }

        result = ep.classify_cluster()

        self.assertEqual(result["result"], "failure")
        self.assertIn("No clusters were updated", result["error"])
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_failed_proc_output(self, mock_db_connect, mock_init_server, mock_config):
        """Test classification update where procedure reports failure"""
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
        ep.cluster_to_classify = {
            "cluster_id": 123,
            "classification": "tritium",
        }

        with self.assertRaises(FailedProcException):
            ep.classify_cluster()

        mock_connection.close.assert_called_once()
        self.assertIsNone(ep.conn)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    def test_classify_cluster_reconnect_on_no_connection(self, mock_init_server, mock_config):
        """Test classify_cluster reconnects when connection is missing"""
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
            ep.cluster_to_classify = {
                "cluster_id": 7,
                "classification": "alpha",
            }

            result = ep.classify_cluster()

            self.assertEqual(result["result"], "success")
            self.assertEqual(result["updated"], 1)


class TestEventPersistenceClassifyCluster(unittest.TestCase):
    """Test cases for classify_cluster method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful classification update"""
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
        ep.cluster_to_classify = {
            "cluster_id": 123,
            "classification": "tritium",
        }

        result = ep.classify_cluster()

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
        """Test classification update where no row is changed"""
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
        ep.cluster_to_classify = {
            "cluster_id": 123,
            "classification": "tritium",
        }

        result = ep.classify_cluster()

        self.assertEqual(result["result"], "failure")
        self.assertIn("No clusters were updated", result["error"])
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_classify_cluster_failed_proc_output(self, mock_db_connect, mock_init_server, mock_config):
        """Test classification update where procedure reports failure"""
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
        ep.cluster_to_classify = {
            "cluster_id": 123,
            "classification": "tritium",
        }

        with self.assertRaises(FailedProcException):
            ep.classify_cluster()

        mock_connection.close.assert_called_once()
        self.assertIsNone(ep.conn)

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    def test_classify_cluster_reconnect_on_no_connection(self, mock_init_server, mock_config):
        """Test classify_cluster reconnects when connection is missing"""
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
            ep.cluster_to_classify = {
                "cluster_id": 7,
                "classification": "alpha",
            }

            result = ep.classify_cluster()

            self.assertEqual(result["result"], "success")
            self.assertEqual(result["updated"], 1)


class TestEventPersistenceProcessRetrievalFits(unittest.TestCase):
    """Test cases for process_retrieval_fits method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing successful fits retrieval results"""
        instance = mock_config.return_value
        instance.get.side_effect = lambda key: {
            "global:db:hostname": "localhost",
            "global:db:username": "test_user",
            "global:db:password": "test_pass",
            "global:db:database": "test_db"
        }.get(key, None)
        
        ep = EventPersistence()

        results = [
            (1, "test1.fits", "2022-10-03", 100, 5000, 3600),
            (2, "test2.fits", "2022-10-04", 200, 6000, 3600)
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
        """Test processing empty fits retrieval results"""
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
        """Test processing fits retrieval with error"""
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
    """Test cases for process_retrieval_clusters method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_process_retrieval_clusters_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing successful clusters retrieval results"""
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
        """Test processing empty clusters retrieval results"""
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
        """Test processing clusters retrieval with error"""
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
    """Test cases for cluster_event method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_storage_success(self, mock_db_connect, mock_store_cluster, mock_init_server, mock_config):
        """Test cluster event with Storage action"""
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
        """Test cluster event with Storage action that fails"""
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
        """Test cluster event with Retrieval action"""
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
    def test_cluster_event_update_classification_success(self, mock_db_connect, mock_classify_cluster, mock_init_server, mock_config):
        """Test cluster event with UpdateClassification action"""
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

        self.assertEqual(ep.cluster_to_classify["cluster_id"], 123)
        self.assertEqual(ep.cluster_to_classify["classification"], "tritium")
        mock_socket.send_json.assert_called_once_with({"result": "success", "updated": 1})

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'classify_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_cluster_event_update_classification_exception(self, mock_db_connect, mock_classify_cluster, mock_init_server, mock_config):
        """Test UpdateClassification action when classify_cluster raises exception"""
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
        """Test cluster event with missing required field"""
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

class TestEventPersistenceFitsEvent(unittest.TestCase):
    """Test cases for fits_event method"""

    @patch('le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    def test_fits_event_storage_success(self, mock_db_connect, mock_store_fits, mock_init_server, mock_config):
        """Test fits event with Storage action"""
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
            "minimum": 100,
            "maximum": 5000,
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
        """Test fits event with Storage action that fails"""
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
            "minimum": 100,
            "maximum": 5000,
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
        """Test fits event with Retrieval action"""
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
    def test_fits_event_clusters(self, mock_db_connect, mock_retrieve_clusters, mock_retrieve_fits, mock_init_server, mock_config):
        """Test fits event with Clusters action"""
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
        """Test fits event with missing required field"""
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

if __name__ == '__main__':
    unittest.main()
