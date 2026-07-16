"""Registry of configuration keys bound to an ``ipc://`` endpoint at startup.

``ipc://`` transport is unsupported by ``pyzmq`` on Windows (see issue #204).
Every startup-time ``.bind()`` call for one of these keys must be reachable
by the Windows fallback dialog (:mod:`IPCFallbackSupport`,
:mod:`IPCFallbackViewModel`) so it can be redirected to ``tcp://``. This
module exists so that adding a fifth startup bind without registering it
here fails loudly instead of silently reintroducing partial Windows
breakage.
"""

import logging
from typing import Tuple

import zmq

from .ConfigurationService import ConfigurationService

logger = logging.getLogger(__name__)


STARTUP_IPC_BIND_KEYS: Tuple[str, ...] = (
    "event_handler:zmq_pub_endpoint",
    "eps:fits_ipc",
    "eps:cluster_ipc",
    "eps:command_ipc",
)
"""Configuration keys whose value is ``.bind()``-ed as an ``ipc://`` socket
during application startup. Keep in sync with the Windows fallback dialog —
see ``wiki/Front-Design-IPC-Fallback-Dialog.md``."""


def assert_ipc_bind_key_registered(key: str) -> None:
    """Raise ``RuntimeError`` if *key* is not in :data:`STARTUP_IPC_BIND_KEYS`.

    A new startup-time ``ipc://`` bind must be added to the registry before
    it can be bound through :func:`bind_tracked_ipc_socket`, so the Windows
    fallback dialog cannot silently miss it.
    """
    if key not in STARTUP_IPC_BIND_KEYS:
        raise RuntimeError(
            f"{key!r} is not a registered startup IPC bind key. "
            "Add it to STARTUP_IPC_BIND_KEYS in "
            "le_beta_vis/common/StartupIPCBindRegistry.py so the Windows "
            "ipc:// fallback dialog stays in sync with this socket."
        )


def bind_tracked_ipc_socket(
    socket: zmq.Socket,
    config: ConfigurationService,
    key: str,
) -> None:
    """Bind *socket* to the endpoint stored under *key*, guarded by the registry.

    Resolves the endpoint from *config* internally rather than accepting a
    pre-resolved string, so the registry-checked key and the bound key can
    never drift apart.
    """
    assert_ipc_bind_key_registered(key)
    endpoint = config.get(key)
    socket.bind(endpoint)
    logger.debug("bind_tracked_ipc_socket: bound %s -> %s", key, endpoint)
