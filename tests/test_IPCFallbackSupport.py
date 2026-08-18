"""Unit tests for IPCFallbackSupport.

``is_ipc_bind_supported`` is exercised with a real ``zmq.Context`` (a
throwaway loopback-style ``ipc://`` bind is cheap and headless-safe) so
the pass/fail path reflects a real socket outcome; ``should_show_ipc_fallback_dialog``
is exercised with the probe mocked/patched so the short-circuit branches
never touch a real socket.
"""

from unittest.mock import patch

import yaml
import zmq

from le_beta_vis.common.IPCFallbackSupport import (
    any_startup_key_uses_ipc_scheme,
    find_free_tcp_ports,
    is_ipc_bind_supported,
    should_show_ipc_fallback_dialog,
)
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
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
        config.set("eps:status_pub_endpoint", "tcp://127.0.0.1:5559")
        assert any_startup_key_uses_ipc_scheme(config) is False

    def test_true_when_key_absent_from_existing_config(self, tmp_path):
        """Regression test: a key missing from an existing on-disk config
        (not even set to ``ipc://``) must still be detected as needing the
        fallback, via its schema default in ``defaults.yaml`` — not
        silently skipped because ``config.get(key)`` without a default
        returns ``None`` for it.

        Reproduces a returning user whose ``mlccd_viz.yaml`` predates
        ``eps:status_pub_endpoint`` being added to ``STARTUP_IPC_BIND_KEYS``:
        the four legacy keys are already migrated to ``tcp://`` on disk, but
        the new key was never persisted at all. Uses the real
        ``YAMLBackedConfigurationService`` rather than
        ``MockConfigurationService`` — the mock's ``get_metadata()`` is
        derived from its own value store, so a key absent from the store is
        also absent from its metadata, unlike the real service, whose
        ``get_metadata()`` always reflects the full bundled ``defaults.yaml``
        schema regardless of what's been persisted to disk.
        """
        yaml_path = tmp_path / "mlccd_viz.yaml"
        with open(yaml_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(
                {
                    "event_handler:zmq_pub_endpoint": "tcp://127.0.0.1:5555",
                    "eps:fits_ipc": "tcp://127.0.0.1:5556",
                    "eps:cluster_ipc": "tcp://127.0.0.1:5557",
                    "eps:command_ipc": "tcp://127.0.0.1:5558",
                },
                fh,
            )
        config = YAMLBackedConfigurationService(yaml_path=yaml_path)
        assert any_startup_key_uses_ipc_scheme(config) is True


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
        config.set("eps:status_pub_endpoint", "tcp://127.0.0.1:5559")
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

    def test_true_when_windows_and_new_key_absent_from_existing_config(self, tmp_path):
        """End-to-end regression test for the reported crash: a returning
        Windows user whose config already migrated the four legacy keys to
        ``tcp://``, but whose file predates ``eps:status_pub_endpoint``, must
        still get the fallback dialog rather than proceeding straight into
        an ``ipc://`` bind crash."""
        yaml_path = tmp_path / "mlccd_viz.yaml"
        with open(yaml_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(
                {
                    "event_handler:zmq_pub_endpoint": "tcp://127.0.0.1:5555",
                    "eps:fits_ipc": "tcp://127.0.0.1:5556",
                    "eps:cluster_ipc": "tcp://127.0.0.1:5557",
                    "eps:command_ipc": "tcp://127.0.0.1:5558",
                },
                fh,
            )
        config = YAMLBackedConfigurationService(yaml_path=yaml_path)
        with patch("le_beta_vis.common.IPCFallbackSupport.platform.system", return_value="Windows"), \
                patch(
                    "le_beta_vis.common.IPCFallbackSupport.is_ipc_bind_supported",
                    return_value=False,
        ):
            assert should_show_ipc_fallback_dialog(config) is True


class TestFindFreeTcpPorts:

    def test_returns_distinct_real_ports(self):
        ports = find_free_tcp_ports(4)
        assert len(ports) == 4
        assert len(set(ports)) == 4
        assert all(isinstance(p, int) and 0 < p < 65536 for p in ports)
