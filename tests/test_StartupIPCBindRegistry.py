"""Unit tests for StartupIPCBindRegistry.

Uses ``MagicMock(spec=zmq.Socket)`` — no real sockets touched, so the tests run headless in CI.
"""

from unittest.mock import MagicMock

import pytest
import yaml
import zmq

from le_beta_vis.common.StartupIPCBindRegistry import (
    STARTUP_IPC_BIND_KEYS,
    assert_ipc_bind_key_registered,
    bind_tracked_ipc_socket,
)
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from mock_configuration_service import MockConfigurationService


class TestAssertIpcBindKeyRegistered:

    @pytest.mark.parametrize("key", STARTUP_IPC_BIND_KEYS)
    def test_registered_keys_pass(self, key):
        assert_ipc_bind_key_registered(key)

    def test_unregistered_key_raises(self):
        with pytest.raises(RuntimeError, match="not a registered startup IPC bind key"):
            assert_ipc_bind_key_registered("eps:some_new_ipc")


class TestIPCFallbackViewModelStaysInSync:
    """Named tripwire for the registry/ViewModel invariant.

    ``IPCFallbackViewModel`` already asserts this at import time, but that surfaces as a collateral ``AssertionError`` in
    whatever test happens to import the module first. This test gives CI an unambiguous signal that a new
    ``STARTUP_IPC_BIND_KEYS`` entry was added without a matching ``IPCFallbackViewModel._ENDPOINT_LABELS`` row (or vice versa).
    """

    def test_endpoint_labels_match_registry(self):
        from le_beta_vis.frontend.viewmodels.IPCFallbackViewModel import (
            _ENDPOINT_LABELS,
        )

        labeled_keys = tuple(key for key, _ in _ENDPOINT_LABELS)
        assert labeled_keys == STARTUP_IPC_BIND_KEYS


class TestBindTrackedIpcSocket:

    def test_binds_resolved_endpoint_for_registered_key(self):
        config = MockConfigurationService()
        socket = MagicMock(spec=zmq.Socket)

        bind_tracked_ipc_socket(socket, config, "eps:fits_ipc")

        socket.bind.assert_called_once_with(config.get("eps:fits_ipc"))

    def test_unregistered_key_raises_without_binding(self):
        config = MockConfigurationService()
        socket = MagicMock(spec=zmq.Socket)

        with pytest.raises(RuntimeError, match="not a registered startup IPC bind key"):
            bind_tracked_ipc_socket(socket, config, "eps:some_new_ipc")

        socket.bind.assert_not_called()

    def test_falls_back_to_schema_default_for_key_absent_from_existing_config(self, tmp_path):
        """Regression test for issue #238.

        Reproduces a returning user whose ``mlccd_viz.yaml`` predates ``eps:status_pub_endpoint`` being added to
        ``STARTUP_IPC_BIND_KEYS``: the key is registered but was never persisted to disk. Before the fix, ``config.get(key)``
        with no default returned ``None``, and ``socket.bind(None)`` would raise. Uses the real
        ``YAMLBackedConfigurationService`` — ``MockConfigurationService``'s ``get_metadata()`` is derived from its own value
        store, so it can't exercise a key that's absent from the on-disk config but still present in the bundled
        ``defaults.yaml`` schema.
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
        socket = MagicMock(spec=zmq.Socket)

        bind_tracked_ipc_socket(socket, config, "eps:status_pub_endpoint")

        expected_default = config.get_metadata()["eps:status_pub_endpoint"]["default"]
        socket.bind.assert_called_once_with(expected_default)
