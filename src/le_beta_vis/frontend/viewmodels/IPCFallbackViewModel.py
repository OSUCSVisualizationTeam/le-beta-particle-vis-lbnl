"""Pure-Python ViewModel for the Windows IPC fallback dialog.

Presents the startup ``ipc://`` endpoints (see ``STARTUP_IPC_BIND_KEYS``) as
editable host/port pairs pre-filled with free TCP ports, and persists them
as ``tcp://host:port`` on save. No Qt dependencies — testable in headless
CI. See issue #204.

Logging in this module is console-only (plain
``logging.getLogger(__name__)``), for the same reason as
:mod:`~le_beta_vis.common.IPCFallbackSupport`: this ViewModel exists
precisely because the ZMQ event bus may not be usable yet, so its own
diagnostics must never depend on that bus.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.IPCFallbackSupport import find_free_tcp_ports
from le_beta_vis.common.StartupIPCBindRegistry import STARTUP_IPC_BIND_KEYS

logger = logging.getLogger(__name__)


_ENDPOINT_LABELS: List[tuple] = [
    ("event_handler:zmq_pub_endpoint", "Event Bus"),
    ("eps:fits_ipc", "FITS Service"),
    ("eps:cluster_ipc", "Cluster Service"),
    ("eps:command_ipc", "Command Service"),
    ("eps:status_pub_endpoint", "Status Service"),
]

assert tuple(key for key, _ in _ENDPOINT_LABELS) == STARTUP_IPC_BIND_KEYS, (
    "_ENDPOINT_LABELS must stay in sync with STARTUP_IPC_BIND_KEYS"
)

_DEFAULT_HOST = "127.0.0.1"
_MIN_PORT = 1
_MAX_PORT = 65535


@dataclass
class IPCFallbackEndpointRow:
    """One editable host/port row for a single startup IPC bind key."""

    key: str
    label: str
    host: str
    port_text: str


class IPCFallbackViewModel:
    """ViewModel for the Windows IPC fallback dialog.

    On construction, precomputes one distinct free TCP port per startup IPC
    bind key on ``127.0.0.1`` and builds one row per key. ``save()``
    validates all rows before persisting any of them to the config
    service; ``quit()`` is a no-op kept for symmetry with ``save()`` so
    the View can call either without branching.
    """

    def __init__(self, config: ConfigurationService) -> None:
        self._config = config
        self.last_error: Optional[str] = None

        ports = find_free_tcp_ports(len(_ENDPOINT_LABELS))
        self.rows: List[IPCFallbackEndpointRow] = [
            IPCFallbackEndpointRow(
                key=key,
                label=label,
                host=_DEFAULT_HOST,
                port_text=str(port),
            )
            for (key, label), port in zip(_ENDPOINT_LABELS, ports)
        ]
        logger.info(
            "IPCFallbackViewModel: precomputed fallback endpoints: %s",
            ", ".join(f"{row.label}={row.host}:{row.port_text}" for row in self.rows),
        )

    def update_host(self, index: int, host: str) -> None:
        """Record an edited host value for the row at *index*."""
        self.rows[index].host = host

    def update_port(self, index: int, port_text: str) -> None:
        """Record an edited port value for the row at *index*."""
        self.rows[index].port_text = port_text

    def save(self) -> bool:
        """Validate all rows and, if valid, persist them as ``tcp://`` endpoints.

        Validates every row (non-empty host, integer port in
        ``1..65535``) before persisting any of them — either all four
        keys are written, or none are. On validation failure, sets
        ``last_error`` to a human-readable message and returns ``False``
        without touching the config service.
        """
        resolved = []
        for row in self.rows:
            host = row.host.strip()
            if not host:
                self.last_error = f"{row.label}: host must not be empty."
                logger.warning(
                    "IPCFallbackViewModel.save: rejected row %s — empty host",
                    row.label,
                )
                return False
            try:
                port = int(row.port_text.strip())
            except ValueError:
                self.last_error = f"{row.label}: port must be a number."
                logger.warning(
                    "IPCFallbackViewModel.save: rejected row %s — "
                    "non-numeric port %r",
                    row.label,
                    row.port_text,
                )
                return False
            if not (_MIN_PORT <= port <= _MAX_PORT):
                self.last_error = (
                    f"{row.label}: port must be between "
                    f"{_MIN_PORT} and {_MAX_PORT}."
                )
                logger.warning(
                    "IPCFallbackViewModel.save: rejected row %s — "
                    "port %d out of range",
                    row.label,
                    port,
                )
                return False
            resolved.append((row.key, f"tcp://{host}:{port}"))

        for key, endpoint in resolved:
            self._config.set(key, endpoint)
        logger.info(
            "IPCFallbackViewModel.save: persisted fallback endpoints: %s",
            ", ".join(f"{key}={endpoint}" for key, endpoint in resolved),
        )
        self.last_error = None
        return True

    def quit(self) -> None:
        """No-op recorded for the user declining the fallback.

        The application remains unusable on this machine until the
        configuration is edited manually or the dialog is relaunched and
        Save is used instead.
        """
        logger.warning(
            "IPCFallbackViewModel.quit: user declined the IPC fallback; "
            "startup ipc:// endpoints remain unchanged."
        )
