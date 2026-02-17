import pytest
import queue
import mysql.connector
from mysql.connector import Error
from unittest.mock import MagicMock, patch, ANY
import os
import numpy as np

from le_beta_vis.backend.FileProcessing import ProcessFile
from le_beta_vis.backend.FileProcessing import Cluster


def test_fits_save():
    """
    Tests the insert_fits procedure call from the store_fits FileProcessing function
    """
    # Mock dictionary, mysql, connection, and cursor for test
    # This mock ENV patch can be removed once the database config changes have pushed
    with patch("mysql.connector.connect") as mock_sql, patch('os.environ.get') as mock_env:
        mock_env.dict(os.environ, {"DB_USER": "Test", "DB_PASS": "Password"})
        mock_connection = mock_sql.return_value
        mock_cursor = mock_connection.cursor.return_value

        # Mock result and fetch return
        result = MagicMock()
        result.fetchone.return_value = (100,)
        mock_cursor.stored_results.return_value = [result]

        fits_processor = ProcessFile()
        # Initialize capture values with mocked ones and preset values
        fits_processor.capture = [MagicMock() for x in range(4)]
        for capture in fits_processor.capture:
            capture.info.min = 1
            capture.info.max = 9999
            capture.captureDate.return_value = "2026-01-01"
            capture.exposureDuration.return_value = 10.0

        # Call procedure function
        fits_processor.store_fits()

        # Assert fits_id matches and each function was called once from cursor and connection
        assert fits_processor.fits_id == 100
        mock_cursor.callproc.assert_called_once()
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once() 

def test_cluster_save():
    """
    Tests the insert_cluster procedure call from the store_clusters Cluster function
    """
    # Mock dictionary, mysql, connection, and cursor for test
    # This mock ENV patch can be removed once the database config changes have pushed
    with patch("mysql.connector.connect") as mock_sql, patch.dict(os.environ, {"DB_USER": "Test", "DB_PASS": "Password"}):
        mock_connection = mock_sql.return_value
        mock_cursor = mock_connection.cursor.return_value

        # Mock result and fetch return
        result = MagicMock()
        result.fetchone.return_value = (100,)
        mock_cursor.stored_results.return_value = [result]

        cluster = Cluster()
        # Initialize capture values with mocked ones and preset values
        cluster.data = np.random.randint(0, 10, size=(20, 20), dtype=np.float32)
        cluster.sigmaX = 1.2
        cluster.sigmaY = 2.1
        cluster.total_energy = np.sum(cluster.data)
        cluster.total_pixels = np.count_nonzero(cluster.data)
        cluster.fits_id = 100
        cluster.cluster_id = None
        cluster.cnn_classification = 0.0
        cluster.nrg_classificaiton = 0.0
        cluster.bdt_classificaiton = 0.0

        # Call procedure function
        cluster.store_clusters()

        # Assert fits_id matches and each function was called once from cursor and connection
        assert cluster.cluster_id == 100
        mock_cursor.callproc.assert_called_once()
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once() 


def test_connection_failed():
    """ 
    Tests to see if the database connection failure is handled gracefully
    """
    with patch("mysql.connector.connect") as mock_sql:
        # Set side effect to failure and call commands, checking assertions
        mock_sql.side_effect = mysql.connector.Error("FAILED")
        file_processor = ProcessFile()
        file_processor.store_fits()
        
        mock_sql.assert_called_once()
        mock_sql.return_value.commit.call_count == 0
