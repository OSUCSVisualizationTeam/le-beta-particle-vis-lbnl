"""Unit tests for IPCFallbackViewModel.

Pure Python, no Qt — uses MockConfigurationService directly.
"""

from unittest.mock import patch

from le_beta_vis.common.StartupIPCBindRegistry import STARTUP_IPC_BIND_KEYS
from le_beta_vis.frontend.viewmodels.IPCFallbackViewModel import (
    _ENDPOINT_LABELS,
    IPCFallbackViewModel,
)
from mock_configuration_service import MockConfigurationService


class TestEndpointLabels:

    def test_labels_match_startup_bind_keys(self):
        assert tuple(key for key, _ in _ENDPOINT_LABELS) == STARTUP_IPC_BIND_KEYS


class TestConstruction:

    def test_rows_prefilled_with_localhost_and_distinct_ports(self):
        vm = IPCFallbackViewModel(MockConfigurationService())
        assert len(vm.rows) == len(STARTUP_IPC_BIND_KEYS)
        assert all(row.host == "127.0.0.1" for row in vm.rows)
        ports = [row.port_text for row in vm.rows]
        assert len(set(ports)) == len(ports)
        assert all(port.isdigit() for port in ports)

    def test_row_keys_match_startup_bind_keys_in_order(self):
        vm = IPCFallbackViewModel(MockConfigurationService())
        assert tuple(row.key for row in vm.rows) == STARTUP_IPC_BIND_KEYS


class TestUpdates:

    def test_update_host_mutates_pending_row(self):
        vm = IPCFallbackViewModel(MockConfigurationService())
        vm.update_host(0, "192.168.1.5")
        assert vm.rows[0].host == "192.168.1.5"

    def test_update_port_mutates_pending_row(self):
        vm = IPCFallbackViewModel(MockConfigurationService())
        vm.update_port(0, "9000")
        assert vm.rows[0].port_text == "9000"


class TestSave:

    def test_save_persists_all_four_keys_as_tcp(self):
        config = MockConfigurationService()
        vm = IPCFallbackViewModel(config)
        for i, row in enumerate(vm.rows):
            vm.update_host(i, "127.0.0.1")
            vm.update_port(i, str(6000 + i))

        assert vm.save() is True

        for i, key in enumerate(STARTUP_IPC_BIND_KEYS):
            assert config.get(key) == f"tcp://127.0.0.1:{6000 + i}"

    def test_save_rejects_empty_host_without_persisting(self):
        config = MockConfigurationService()
        vm = IPCFallbackViewModel(config)
        vm.update_host(0, "   ")

        with patch.object(config, "set") as mock_set:
            assert vm.save() is False
            mock_set.assert_not_called()
        assert vm.last_error is not None

    def test_save_rejects_non_numeric_port_without_persisting(self):
        config = MockConfigurationService()
        vm = IPCFallbackViewModel(config)
        vm.update_port(1, "not-a-port")

        with patch.object(config, "set") as mock_set:
            assert vm.save() is False
            mock_set.assert_not_called()
        assert vm.last_error is not None

    def test_save_rejects_out_of_range_port_without_persisting(self):
        config = MockConfigurationService()
        vm = IPCFallbackViewModel(config)
        vm.update_port(2, "70000")

        with patch.object(config, "set") as mock_set:
            assert vm.save() is False
            mock_set.assert_not_called()
        assert vm.last_error is not None

    def test_save_is_all_or_nothing_when_a_later_row_is_invalid(self):
        config = MockConfigurationService()
        vm = IPCFallbackViewModel(config)
        # First rows valid, last row invalid.
        vm.update_port(len(vm.rows) - 1, "0")

        with patch.object(config, "set") as mock_set:
            assert vm.save() is False
            mock_set.assert_not_called()


class TestQuit:

    def test_quit_never_persists(self):
        config = MockConfigurationService()
        vm = IPCFallbackViewModel(config)
        with patch.object(config, "set") as mock_set:
            vm.quit()
            mock_set.assert_not_called()
