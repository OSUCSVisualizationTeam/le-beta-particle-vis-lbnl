"""Pure-Python ViewModel for gating the splash screen on EPS startup readiness.

Registers a callback for ``eps.startup.status`` envelopes (published by
:class:`~le_beta_vis.common.EPSStartupSignals.EPSStartupSignals`) against an
injected ``EventHandlerInterface`` and exposes a ``poll()``-based snapshot
API for a Qt View (``SplashScreenView``) to drive on a timer. No Qt
imports — testable headlessly, mirroring
:class:`~le_beta_vis.frontend.viewmodels.IPCFallbackViewModel.IPCFallbackViewModel`'s
construction pattern.
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional

from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EPSStartupSignals import EPS_STARTUP_STATUS_EVENT
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface

_DEFAULT_READY_TIMEOUT_MS = 12000


@dataclass(frozen=True)
class StartupReadinessSnapshot:
    """Immutable snapshot of EPS startup readiness at one ``poll()`` call.

    Attributes:
        db_connected: Whether EPS last reported a live MySQL connection.
        sockets_bound: Whether EPS last reported its ZMQ sockets bound
            and serving. Once ``True``, EPS has finished resolving its
            own startup (connected or gave up after retries) — this is
            a definitive signal, not a partial one.
        elapsed_ms: Milliseconds since this ViewModel was constructed.
        ready: Whether the splash should proceed to show ``MainWindow``.
        degraded: Whether ``ready`` is ``True`` without full readiness
            (``sockets_bound`` without ``db_connected``, or the overall
            timeout elapsed without ever hearing from EPS at all).
        message: Human-readable status text for ``splash.showMessage()``.
    """

    db_connected: bool
    sockets_bound: bool
    elapsed_ms: float
    ready: bool
    degraded: bool
    message: str


class StartupReadinessViewModel:
    """Aggregates EPS startup-readiness status for the splash screen.

    Registers a callback for ``eps.startup.status`` against the injected
    ``event_handler`` and records the latest known state under a lock
    (the callback fires from a background dispatch thread). ``poll()``
    combines that state with elapsed time against
    ``gui:startup:ready_timeout_ms`` to decide readiness — never blocks,
    intended to be called repeatedly by a View-owned timer.
    """

    def __init__(
        self,
        config: ConfigurationService,
        event_handler: EventHandlerInterface,
    ) -> None:
        self._config = config
        self._start_time = time.monotonic()
        self._lock = threading.Lock()
        self._db_connected = False
        self._sockets_bound = False
        self._attempt: Optional[int] = None
        self._max_attempts: Optional[int] = None
        event_handler.register_callback(
            EPS_STARTUP_STATUS_EVENT, self._on_status_event
        )

    def _on_status_event(self, envelope: EventEnvelope) -> None:
        payload = envelope.payload
        with self._lock:
            self._db_connected = bool(payload.get("db_connected", False))
            self._sockets_bound = bool(payload.get("sockets_bound", False))
            self._attempt = payload.get("attempt")
            self._max_attempts = payload.get("max_attempts")

    def poll(self) -> StartupReadinessSnapshot:
        """Returns the current readiness snapshot.

        ``sockets_bound`` alone is treated as EPS's final word for this
        session — once received, ``ready`` is ``True`` immediately
        (``degraded`` set if ``db_connected`` is still ``False``),
        without waiting out the rest of ``gui:startup:ready_timeout_ms``.
        That timeout only guards the case where EPS never reports in at
        all (e.g. its thread crashed before publishing anything).
        """
        with self._lock:
            db_connected = self._db_connected
            sockets_bound = self._sockets_bound
            attempt = self._attempt
            max_attempts = self._max_attempts

        elapsed_ms = (time.monotonic() - self._start_time) * 1000.0

        if sockets_bound:
            degraded = not db_connected
            message = "Ready." if db_connected else self._degraded_message()
            return StartupReadinessSnapshot(
                db_connected=db_connected,
                sockets_bound=True,
                elapsed_ms=elapsed_ms,
                ready=True,
                degraded=degraded,
                message=message,
            )

        timeout_ms = self._config.get_int(
            "gui:startup:ready_timeout_ms", _DEFAULT_READY_TIMEOUT_MS, minimum=0
        )
        if elapsed_ms >= timeout_ms:
            return StartupReadinessSnapshot(
                db_connected=db_connected,
                sockets_bound=False,
                elapsed_ms=elapsed_ms,
                ready=True,
                degraded=True,
                message=(
                    "Starting without a connection to the backend service — "
                    "some features will be unavailable."
                ),
            )

        return StartupReadinessSnapshot(
            db_connected=db_connected,
            sockets_bound=False,
            elapsed_ms=elapsed_ms,
            ready=False,
            degraded=False,
            message=self._waiting_message(attempt, max_attempts),
        )

    @staticmethod
    def _degraded_message() -> str:
        return (
            "Starting without a database connection — some features will "
            "be unavailable."
        )

    @staticmethod
    def _waiting_message(
        attempt: Optional[int], max_attempts: Optional[int]
    ) -> str:
        if attempt is not None and max_attempts is not None:
            return f"Connecting to database (attempt {attempt}/{max_attempts})…"
        return "Starting backend services…"
