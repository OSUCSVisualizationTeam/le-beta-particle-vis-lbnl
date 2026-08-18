"""Unit tests for EPSRunner's EPSStartupSignals wiring.

All collaborators (config service, log handler, ZMQ context,
EventPersistence, EPSStartupSignals) are mocked — no real sockets or
threads are exercised, so these tests run headless in CI.
"""

import unittest
from unittest.mock import MagicMock, patch

from le_beta_vis.backend.EPSRunner import EPSRunner


class TestConstruction(unittest.TestCase):

    @patch('le_beta_vis.backend.EPSRunner.EPSStartupSignals')
    @patch('le_beta_vis.backend.EPSRunner.attach_to_root_logger')
    @patch('le_beta_vis.backend.EPSRunner.YAMLBackedConfigurationService')
    def test_builds_startup_signals_from_config(
        self, mock_config_cls, mock_attach_logger, mock_signals_cls
    ):
        runner = EPSRunner()

        config_instance = mock_config_cls.return_value
        mock_signals_cls.assert_called_once_with(config_instance, source="eps")
        self.assertEqual(runner._startup_signals, mock_signals_cls.return_value)


class TestRun(unittest.TestCase):

    @patch('le_beta_vis.backend.EPSRunner.EventPersistence')
    @patch('le_beta_vis.backend.EPSRunner.EPSStartupSignals')
    @patch('le_beta_vis.backend.EPSRunner.attach_to_root_logger')
    @patch('le_beta_vis.backend.EPSRunner.YAMLBackedConfigurationService')
    def test_run_passes_startup_signals_into_event_persistence(
        self, mock_config_cls, mock_attach_logger, mock_signals_cls, mock_event_persistence
    ):
        runner = EPSRunner()

        runner.run()

        mock_event_persistence.assert_called_once_with(
            startup_signals=runner._startup_signals
        )


class TestStop(unittest.TestCase):

    @patch('le_beta_vis.backend.EPSRunner.zmq.Context')
    @patch('le_beta_vis.backend.EPSRunner.EPSStartupSignals')
    @patch('le_beta_vis.backend.EPSRunner.attach_to_root_logger')
    @patch('le_beta_vis.backend.EPSRunner.YAMLBackedConfigurationService')
    def test_stop_closes_startup_signals(
        self, mock_config_cls, mock_attach_logger, mock_signals_cls, mock_context_cls
    ):
        mock_context_cls.return_value.socket.return_value = MagicMock()
        runner = EPSRunner()

        runner.stop()

        runner._startup_signals.close.assert_called_once()
