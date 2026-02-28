# Citation for Unit Tests: MockHistogramRenderer returning dummy PNG bytes
# Date: 02/27/2026
# Adapted from GitHub Copilot:
# I need to create unit tests for this file under the tests directory, name it test_EventPersistenceService.
# Ensure that all functions, edge cases, and paths are tested for storage and retrieval.
import unittest
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np
import sys
import os

# Add the src directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from le_beta_vis.backend.EventPersistenceService import EventPersistence, FailedProcException
import zmq


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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    def test_initialization(self, mock_init_server, mock_db_connect, mock_config):
        """Test EventPersistence initialization"""
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
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    def test_db_connect_success(self, mock_config, mock_init_server, mock_mysql_connect):
        """Test successful database connection"""
        mock_connection = MagicMock()
        mock_mysql_connect.return_value = mock_connection
        
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
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    def test_db_connect_failure(self, mock_config, mock_init_server, mock_mysql_connect):
        """Test database connection failure"""
        import mysql.connector
        mock_mysql_connect.side_effect = mysql.connector.Error("Connection failed")
        
        ep = EventPersistence()
        with patch('builtins.print') as mock_print:
            conn = ep.db_connect()
            mock_print.assert_called()


class TestEventPersistenceStoreFits(unittest.TestCase):
    """Test cases for store_fits method"""

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_store_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful fits storage"""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        
        # Mock the stored procedure result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [42]
        mock_cursor.stored_results.return_value = [mock_result]
        
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_store_fits_failed_proc(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits storage with failed procedure"""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        
        # Mock failed procedure (id <= 0)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [-1]
        mock_cursor.stored_results.return_value = [mock_result]
        
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_store_fits_reconnect_on_no_connection(self, mock_init_server, mock_config):
        """Test that store_fits reconnects if connection is lost"""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [42]
        mock_cursor.stored_results.return_value = [mock_result]
        
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_store_cluster_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful cluster storage"""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [99]
        mock_cursor.stored_results.return_value = [mock_result]
        
        ep = EventPersistence()
        ep.conn = mock_connection
        
        # Create mock bounding box
        mock_bbox = MagicMock()
        mock_bbox.top = 10
        mock_bbox.left = 20
        mock_bbox.bottom = 30
        mock_bbox.right = 40
        
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_store_cluster_failed_proc(self, mock_db_connect, mock_init_server, mock_config):
        """Test cluster storage with failed procedure"""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [-1]
        mock_cursor.stored_results.return_value = [mock_result]
        
        ep = EventPersistence()
        ep.conn = mock_connection
        
        mock_bbox = MagicMock()
        mock_bbox.top = 10
        mock_bbox.left = 20
        mock_bbox.bottom = 30
        mock_bbox.right = 40
        
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_retrieve_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful fits retrieval"""
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_retrieve_fits_with_multiple_filters(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits retrieval with multiple filter parameters"""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        
        mock_cursor.fetchall.return_value = [(1, "test.fits", "2022-10-03", 100, 5000, 3600)]
        
        ep = EventPersistence()
        ep.conn = mock_connection
        ep.retrieval_fits = {
            "filename": "test.fits",
            "fits_id": 1,
            "date": "2022-10-03",
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_retrieve_clusters_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test successful clusters retrieval"""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_connection
        
        # Mock database results: (fitsFile, hdu_id, clusterID, data, totalEnergy, sigmaX, sigmaY, classification, pixelCount)
        mock_cursor.fetchall.return_value = [
            (1, 0, 1, b'cluster_data', 5000, 1.5, 1.5, "alpha", 100)
        ]
        
        ep = EventPersistence()
        ep.conn = mock_connection
        
        mock_bbox = MagicMock()
        mock_bbox.top = 10
        mock_bbox.left = 20
        mock_bbox.bottom = 30
        mock_bbox.right = 40
        
        ep.retrieval_clusters = {
            "data": None,
            "hdu_id": None,
            "cluster_id": None,
            "bounding_box": None,
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


class TestEventPersistenceProcessRetrievalFits(unittest.TestCase):
    """Test cases for process_retrieval_fits method"""

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_process_retrieval_fits_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing successful fits retrieval results"""
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_process_retrieval_fits_empty_results(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing empty fits retrieval results"""
        ep = EventPersistence()
        
        results = []
        response = ep.process_retrieval_fits(results)
        
        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["fits"]), 0)

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_process_retrieval_fits_error(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing fits retrieval with error"""
        ep = EventPersistence()
        
        error_msg = "Database error occurred"
        response = ep.process_retrieval_fits(error_msg)
        
        self.assertEqual(response["result"], "failure")
        self.assertIsNone(response["fits"])
        self.assertEqual(response["error"], error_msg)


class TestEventPersistenceProcessRetrievalClusters(unittest.TestCase):
    """Test cases for process_retrieval_clusters method"""

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_process_retrieval_clusters_success(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing successful clusters retrieval results"""
        ep = EventPersistence()
        
        results = [
            (1, 0, 1, b'data1', 5000, 1.5, 1.5, "alpha", 100),
            (1, 0, 2, b'data2', 6000, 2.0, 2.0, "beta", 150)
        ]
        
        response = ep.process_retrieval_clusters(results)
        
        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["clusters"]), 2)
        self.assertEqual(response["clusters"][0]["fits_id"], 1)
        self.assertEqual(response["clusters"][0]["cluster_id"], 1)
        self.assertEqual(response["clusters"][0]["classification"], "alpha")

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_process_retrieval_clusters_empty_results(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing empty clusters retrieval results"""
        ep = EventPersistence()
        
        results = []
        response = ep.process_retrieval_clusters(results)
        
        self.assertEqual(response["result"], "success")
        self.assertEqual(len(response["clusters"]), 0)

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_process_retrieval_clusters_error(self, mock_db_connect, mock_init_server, mock_config):
        """Test processing clusters retrieval with error"""
        ep = EventPersistence()
        
        error_msg = "Database error occurred"
        response = ep.process_retrieval_clusters(error_msg)
        
        self.assertEqual(response["result"], "failure")
        self.assertIsNone(response["clusters"])
        self.assertEqual(response["error"], error_msg)


class TestEventPersistenceClusterEvent(unittest.TestCase):
    """Test cases for cluster_event method"""

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_cluster')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_cluster_event_storage(self, mock_db_connect, mock_store_cluster, mock_init_server, mock_config):
        """Test cluster event with Storage action"""
        mock_socket = MagicMock()
        mock_store_cluster.return_value = {"result": "success", "cluster_id": 42}
        
        ep = EventPersistence()
        
        request = {
            "Action": "Storage",
            "data": [1, 2, 3],
            "bounding_box": {"top": 10, "left": 20, "bottom": 30, "right": 40},
            "sigmaX": 1.5,
            "sigmaY": 1.5,
            "total_energy": 5000,
            "total_pixels": 100,
            "fits_id": 1,
            "classification": "alpha"
        }
        
        ep.cluster_event(request, mock_socket)
        
        mock_socket.send_json.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'retrieve_clusters')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_cluster_event_retrieval(self, mock_db_connect, mock_retrieve_clusters, mock_init_server, mock_config):
        """Test cluster event with Retrieval action"""
        mock_socket = MagicMock()
        mock_retrieve_clusters.return_value = {"result": "success", "clusters": []}
        
        ep = EventPersistence()
        
        request = {
            "Action": "Retrieval",
            "data": [],
            "cluster_id": 1,
            "bounding_box": {},
            "sigmaX": None,
            "sigmaY": None,
            "total_energy": None,
            "total_pixels": None,
            "fits_id": 1,
            "classification": None
        }
        
        ep.cluster_event(request, mock_socket)
        
        mock_socket.send_json.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_cluster_event_missing_required_field(self, mock_db_connect, mock_init_server, mock_config):
        """Test cluster event with missing required field"""
        mock_socket = MagicMock()
        
        ep = EventPersistence()
        
        request = {
            "Action": "Storage",
            "data": [1, 2, 3],
            # Missing required fields
        }
        
        ep.cluster_event(request, mock_socket)
        
        # Should send error via socket
        call_args = mock_socket.send_json.call_args
        self.assertIn("result", call_args[0][0])
        self.assertEqual(call_args[0][0]["result"], "failure")


class TestEventPersistenceFitsEvent(unittest.TestCase):
    """Test cases for fits_event method"""

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'store_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_fits_event_storage(self, mock_db_connect, mock_store_fits, mock_init_server, mock_config):
        """Test fits event with Storage action"""
        mock_socket = MagicMock()
        mock_store_fits.return_value = {"result": "success", "fits_id": 42}
        
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
        
        mock_socket.send_json.assert_called_once()

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch.object(EventPersistence, 'retrieve_fits')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_fits_event_retrieval(self, mock_db_connect, mock_retrieve_fits, mock_init_server, mock_config):
        """Test fits event with Retrieval action"""
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

    @patch('le_beta_vis.backend.EventPersistenceService.RedisBackedConfigurationService')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.initialize_server')
    @patch('le_beta_vis.backend.EventPersistenceService.EventPersistence.db_connect')
    @patch.dict(os.environ, {'DB_USER': 'test_user', 'DB_PASS': 'test_pass', 'DB_NAME': 'test_db'})
    def test_fits_event_missing_required_field(self, mock_db_connect, mock_init_server, mock_config):
        """Test fits event with missing required field"""
        mock_socket = MagicMock()
        
        ep = EventPersistence()
        
        request = {
            "Action": "Storage",
            # Missing required fields
        }
        
        ep.fits_event(request, mock_socket)
        
        # Should send error via socket
        call_args = mock_socket.send_json.call_args
        self.assertIn("result", call_args[0][0])
        self.assertEqual(call_args[0][0]["result"], "failure")


if __name__ == '__main__':
    unittest.main()
