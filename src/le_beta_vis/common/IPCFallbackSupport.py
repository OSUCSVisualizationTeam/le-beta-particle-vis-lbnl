"""Detects whether ``ipc://`` ZMQ binds are usable on this machine.

``pyzmq`` on Windows cannot bind ``ipc://`` endpoints (issue #204) — the
bind raises ``zmq.ZMQError: Protocol not supported`` regardless of the
path. This module probes for that condition at startup, before any real
socket that the rest of the application depends on is created, so the
frontend can offer a one-time TCP fallback instead of crashing.

Logging in this module is deliberately console-only (plain
``logging.getLogger(__name__)``, never
:func:`~le_beta_vis.common.ZMQEventLoggingHandler.attach_to_root_logger`).
The whole point of the probe is to run before we know whether the ZMQ
event bus can come up at all, so routing its own diagnostics through that
same bus would be circular. ``app.py`` calls into this module before
constructing ``ServicesManager`` (and therefore before anything attaches a
ZMQ logging handler to the root logger), so every log call here reaches
only the console ``StreamHandler`` installed by ``logging.basicConfig()``
in ``app.py:main()``.
"""

import logging
import platform
import socket as socket_module
from typing import List, Optional

import zmq

from .ConfigurationService import ConfigurationService
from .StartupIPCBindRegistry import STARTUP_IPC_BIND_KEYS

logger = logging.getLogger(__name__)

_PROBE_ENDPOINT = "ipc://le_beta_vis_probe.ipc"
"""Placeholder endpoint for the bind probe. No real path is needed — the
Windows failure is protocol-level (``ipc://`` itself is unsupported), not
path-level, so this never needs to resolve to a real filesystem location."""


def is_ipc_bind_supported(context: Optional[zmq.Context] = None) -> bool:
    """Return whether this machine's ``pyzmq`` can bind an ``ipc://`` socket.

    Binds a throwaway ``zmq.PUB`` socket to a placeholder endpoint and
    reports whether the bind succeeded. Always releases the socket and
    context it created.
    """
    ctx = context or zmq.Context()
    probe_socket = ctx.socket(zmq.PUB)
    try:
        probe_socket.bind(_PROBE_ENDPOINT)
        return True
    except zmq.ZMQError as exc:
        logger.warning(
            "ipc:// bind probe failed (%s); ipc:// transport is not "
            "usable on this machine.",
            exc,
        )
        return False
    finally:
        probe_socket.close(linger=0)
        if context is None:
            ctx.term()


def any_startup_key_uses_ipc_scheme(config: ConfigurationService) -> bool:
    """Return whether any startup IPC bind key is still configured as ``ipc://``.

    Resolves each key's schema default via ``config.get_metadata()`` before
    checking, rather than calling ``config.get(key)`` bare. A key freshly
    added to :data:`STARTUP_IPC_BIND_KEYS` may not exist yet in an existing
    on-disk config written before that key was introduced — without a
    default, ``.get()`` returns ``None`` for a missing key indistinguishably
    from an explicitly-cleared one, which would silently skip the fallback
    dialog for a returning user instead of detecting the still-``ipc://``
    default.
    """
    metadata = config.get_metadata()
    return any(
        str(
            config.get(key, metadata.get(key, {}).get("default", ""))
        ).startswith("ipc://")
        for key in STARTUP_IPC_BIND_KEYS
    )


def should_show_ipc_fallback_dialog(config: ConfigurationService) -> bool:
    """Return whether the Windows IPC fallback dialog should be shown.

    Short-circuits to ``False`` without running the real bind probe when
    not on Windows, or when every startup IPC bind key has already been
    migrated to ``tcp://``. Only binds a throwaway socket when there is
    something to actually check: Windows and at least one key still using
    ``ipc://``.
    """
    if platform.system() != "Windows":
        logger.info(
            "IPC fallback probe skipped: not running on Windows."
        )
        return False
    if not any_startup_key_uses_ipc_scheme(config):
        logger.info(
            "IPC fallback probe skipped: all startup endpoints already "
            "use tcp://."
        )
        return False
    supported = is_ipc_bind_supported()
    if not supported:
        logger.warning(
            "Windows ipc:// bind probe failed; showing IPC fallback dialog."
        )
    return not supported


def find_free_tcp_ports(count: int, host: str = "127.0.0.1") -> List[int]:
    """Return *count* distinct free TCP ports on *host*.

    Opens *count* throwaway sockets bound to port 0 simultaneously, reads
    back the OS-assigned port for each, then closes them all together —
    closing sequentially and re-binding would risk the OS handing back the
    same just-freed ephemeral port twice.
    """
    sockets = []
    try:
        for _ in range(count):
            sock = socket_module.socket(
                socket_module.AF_INET, socket_module.SOCK_STREAM
            )
            sock.bind((host, 0))
            sockets.append(sock)
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()
