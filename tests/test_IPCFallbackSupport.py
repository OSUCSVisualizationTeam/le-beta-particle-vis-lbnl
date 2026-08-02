"""Unit tests for IPCFallbackSupport.

``is_ipc_bind_supported`` is exercised with a real ``zmq.Context`` (a
throwaway loopback-style ``ipc://`` bind is cheap and headless-safe) so
the pass/fail path reflects a real socket outcome; ``should_show_ipc_fallback_dialog``
is exercised with the probe mocked/patched so the short-circuit branches
never touch a real socket.
"""

from unittest.mock import patch

import zmq

from le_beta_vis.common.IPCFallbackSupport import (
    any_startup_key_uses_ipc_scheme,
    find_free_tcp_ports,
    is_ipc_bind_supported,
    should_show_ipc_fallback_dialog,
)
from mock_configuration_service import MockConfigurationService


class TestIsIpcBindSupported:

    def test_real_bind_succeeds_and_cleans_up(self):
        # On Linux/macOS CI runners ipc:// binds normally succeed.
        assert is_ipc_bind_supported() is True

    def test_bind_failure_returns_false_and_cleans_up(self):
        ctx = zmq.Context()
        with patch.object(zmq.Socket, "bind", side_effect=zmq.ZMQError("nope")):
            assert is_ipc_bind_supported(context=ctx) is False
        ctx.term()


class TestAnyStartupKeyUsesIpcScheme:

    def test_true_when_any_key_is_ipc(self):
        config = MockConfigurationService()
        assert any_startup_key_uses_ipc_scheme(config) is True

    def test_false_when_all_keys_are_tcp(self):
        config = MockConfigurationService()
        config.set("event_handler:zmq_pub_endpoint", "tcp://127.0.0.1:5555")
        config.set("eps:fits_ipc", "tcp://127.0.0.1:5556")
        config.set("eps:cluster_ipc", "tcp://127.0.0.1:5557")
        config.set("eps:command_ipc", "tcp://127.0.0.1:5558")
        assert any_startup_key_uses_ipc_scheme(config) is False


class TestShouldShowIpcFallbackDialog:

    def test_short_circuits_on_non_windows_without_probing(self):
        config = MockConfigurationService()
        with patch("le_beta_vis.common.IPCFallbackSupport.platform.system", return_value="Linux"), \
                patch("le_beta_vis.common.IPCFallbackSupport.is_ipc_bind_supported") as probe:
            assert should_show_ipc_fallback_dialog(config) is False
            probe.assert_not_called()

    def test_short_circuits_when_already_migrated_without_probing(self):
        config = MockConfigurationService()
        config.set("event_handler:zmq_pub_endpoint", "tcp://127.0.0.1:5555")
        config.set("eps:fits_ipc", "tcp://127.0.0.1:5556")
        config.set("eps:cluster_ipc", "tcp://127.0.0.1:5557")
        config.set("eps:command_ipc", "tcp://127.0.0.1:5558")
        with patch("le_beta_vis.common.IPCFallbackSupport.platform.system", return_value="Windows"), \
                patch("le_beta_vis.common.IPCFallbackSupport.is_ipc_bind_supported") as probe:
            assert should_show_ipc_fallback_dialog(config) is False
            probe.assert_not_called()

    def test_true_when_windows_and_ipc_scheme_and_probe_fails(self):
        config = MockConfigurationService()
        with patch("le_beta_vis.common.IPCFallbackSupport.platform.system", return_value="Windows"), \
                patch(
                    "le_beta_vis.common.IPCFallbackSupport.is_ipc_bind_supported",
                    return_value=False,
        ):
            assert should_show_ipc_fallback_dialog(config) is True

    def test_false_when_windows_and_ipc_scheme_but_probe_succeeds(self):
        config = MockConfigurationService()
        with patch("le_beta_vis.common.IPCFallbackSupport.platform.system", return_value="Windows"), \
                patch(
                    "le_beta_vis.common.IPCFallbackSupport.is_ipc_bind_supported",
                    return_value=True,
        ):
            assert should_show_ipc_fallback_dialog(config) is False


class TestFindFreeTcpPorts:

    def test_returns_distinct_real_ports(self):
        ports = find_free_tcp_ports(4)
        assert len(ports) == 4
        assert len(set(ports)) == 4
        assert all(isinstance(p, int) and 0 < p < 65536 for p in ports)
