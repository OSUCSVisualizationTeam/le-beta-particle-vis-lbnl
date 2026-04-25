# Validate set_export_running fires observers exactly once per real transition

"""Tests for HistoricalFilterBarViewModel.is_export_running (#56)."""
from typing import List

from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.frontend.viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)

from mock_configuration_service import MockConfigurationService


def _build():
    cfg = MockConfigurationService()
    physics = PhysicsConversionManagerImpl(cfg)
    return HistoricalFilterBarViewModel(cfg, physics)


class TestExportLock:
    def test_default_is_unlocked(self):
        vm = _build()
        assert vm.is_export_running is False

    def test_set_true_emits_callback(self):
        vm = _build()
        events: List[bool] = []
        vm.add_export_running_callback(events.append)
        vm.set_export_running(True)
        assert events == [True]

    def test_idempotent_set_does_not_refire(self):
        vm = _build()
        events: List[bool] = []
        vm.add_export_running_callback(events.append)
        vm.set_export_running(True)
        vm.set_export_running(True)
        assert events == [True]

    def test_round_trip_true_false(self):
        vm = _build()
        events: List[bool] = []
        vm.add_export_running_callback(events.append)
        vm.set_export_running(True)
        vm.set_export_running(False)
        assert events == [True, False]
