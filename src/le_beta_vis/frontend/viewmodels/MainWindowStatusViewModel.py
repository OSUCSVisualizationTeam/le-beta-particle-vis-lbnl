"""Pure-Python ViewModel for the global MainWindow status bar.

Subscribes to ``EventHandler`` log events (``log.info``,
``log.warning``, ``log.error``, ``log.critical``) and renders them
as severity-tagged messages in a native ``QStatusBar``. Also exposes
a small multi-token progress API so arbitrary long-running operations
(export, classification, prefetch) can surface progress without each
spinning up a modal dialog.

Pure Python — no Qt imports. Tested headlessly.
"""

from __future__ import annotations

import enum
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface


class Severity(enum.Enum):
    """Severity tiers used to style the status bar message."""

    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_EVENT_SEVERITY: Dict[str, Severity] = {
    "log.info": Severity.INFO,
    "log.warning": Severity.WARNING,
    "log.error": Severity.ERROR,
    "log.critical": Severity.ERROR,
}


@dataclass(frozen=True)
class ProgressSnapshot:
    """Immutable snapshot of one in-flight progress operation.

    Attributes:
        token: Opaque identifier returned by ``begin_progress``.
        label: Human-readable label, e.g. ``"Exporting report"``.
        fraction: Completion in ``[0.0, 1.0]``. A negative value
            signals indeterminate progress (spinner).
        message: Optional sub-status for the current step.
        cancelable: Whether a cancel affordance should be offered.
    """

    token: str
    label: str
    fraction: float
    message: Optional[str]
    cancelable: bool


@dataclass
class _ProgressState:
    label: str
    fraction: float
    message: Optional[str]
    cancelable: bool
    cancel_callbacks: List[Callable[[], None]] = field(default_factory=list)


class MainWindowStatusViewModel:
    """ViewModel for the global MainWindow status bar.

    Args:
        event_handler: The application's shared ``EventHandler``.
        clear_timeout_s: Seconds after which a stale message is
            auto-cleared. ``0`` (or negative) disables auto-clear.
    """

    def __init__(
        self,
        event_handler: EventHandlerInterface,
        clear_timeout_s: float = 5.0,
    ) -> None:
        self._event_handler = event_handler
        self._clear_timeout_s = max(0.0, float(clear_timeout_s))

        self._lock = threading.Lock()
        self._message: str = ""
        self._severity: Severity = Severity.NONE
        self._progress: Dict[str, _ProgressState] = {}
        self._clear_timer: Optional[threading.Timer] = None

        self._on_message_changed: List[Callable[[], None]] = []
        self._on_progress_changed: List[Callable[[], None]] = []

        self._subscription_ids: List[str] = []
        for event_name in _EVENT_SEVERITY:
            self._subscription_ids.append(
                event_handler.register_callback(
                    event_name, self._on_log_event
                )
            )

    # ------------------------------------------------------------------
    # Observed state
    # ------------------------------------------------------------------

    @property
    def message(self) -> str:
        """The current status bar message (empty when none)."""
        with self._lock:
            return self._message

    @property
    def severity(self) -> Severity:
        """The severity of the current message."""
        with self._lock:
            return self._severity

    @property
    def active_progress(self) -> List[ProgressSnapshot]:
        """Immutable snapshots of all active progress operations."""
        with self._lock:
            return [
                ProgressSnapshot(
                    token=token,
                    label=state.label,
                    fraction=state.fraction,
                    message=state.message,
                    cancelable=state.cancelable,
                )
                for token, state in self._progress.items()
            ]

    @property
    def clear_timeout_s(self) -> float:
        """The configured stale-message clear timeout, in seconds."""
        return self._clear_timeout_s

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def add_message_changed_callback(
        self, cb: Callable[[], None]
    ) -> None:
        """Register a callback fired when the message or severity changes."""
        self._on_message_changed.append(cb)

    def add_progress_changed_callback(
        self, cb: Callable[[], None]
    ) -> None:
        """Register a callback fired when any progress state changes."""
        self._on_progress_changed.append(cb)

    # ------------------------------------------------------------------
    # Message API
    # ------------------------------------------------------------------

    def set_message(self, text: str, severity: Severity = Severity.INFO) -> None:
        """Set the current status bar message.

        Args:
            text: Message body. Empty string clears the bar.
            severity: Severity tier used for styling. Ignored when
                ``text`` is empty (severity forced to ``NONE``).
        """
        with self._lock:
            self._message = text
            self._severity = severity if text else Severity.NONE
            self._reschedule_clear_locked()
        self._notify_message_changed()

    def clear_message(self) -> None:
        """Clear the current status bar message immediately."""
        with self._lock:
            if not self._message and self._severity is Severity.NONE:
                return
            self._message = ""
            self._severity = Severity.NONE
            self._cancel_clear_timer_locked()
        self._notify_message_changed()

    # ------------------------------------------------------------------
    # Progress API (callable from any thread)
    # ------------------------------------------------------------------

    def begin_progress(
        self, label: str, cancelable: bool = False
    ) -> str:
        """Start tracking a new progress operation.

        Args:
            label: Human-readable label for the operation.
            cancelable: Whether the View should render a cancel
                affordance for this operation.

        Returns:
            An opaque token to pass to ``update_progress`` /
            ``end_progress`` / ``request_cancel``.
        """
        token = uuid.uuid4().hex
        with self._lock:
            self._progress[token] = _ProgressState(
                label=label,
                fraction=-1.0,
                message=None,
                cancelable=cancelable,
            )
        self._notify_progress_changed()
        return token

    def update_progress(
        self,
        token: str,
        fraction: float,
        message: Optional[str] = None,
    ) -> None:
        """Update an in-flight progress operation.

        A negative ``fraction`` marks indeterminate progress.
        Unknown tokens are silently ignored.
        """
        with self._lock:
            state = self._progress.get(token)
            if state is None:
                return
            state.fraction = float(fraction)
            if message is not None:
                state.message = message
        self._notify_progress_changed()

    def end_progress(self, token: str) -> None:
        """Remove a progress operation. Unknown tokens are ignored."""
        with self._lock:
            if self._progress.pop(token, None) is None:
                return
        self._notify_progress_changed()

    def add_cancel_callback(
        self, token: str, cb: Callable[[], None]
    ) -> None:
        """Register a cancel callback for a cancelable progress token.

        Silently ignored if the token is unknown or not cancelable.
        """
        with self._lock:
            state = self._progress.get(token)
            if state is None or not state.cancelable:
                return
            state.cancel_callbacks.append(cb)

    def request_cancel(self, token: str) -> None:
        """Fire cancel callbacks for ``token`` (no-op if not cancelable)."""
        with self._lock:
            state = self._progress.get(token)
            if state is None or not state.cancelable:
                return
            callbacks = list(state.cancel_callbacks)
        for cb in callbacks:
            try:
                cb()
            except Exception:
                # A misbehaving consumer must not take the bar down.
                pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Cancel timers and unregister from the EventHandler."""
        with self._lock:
            self._cancel_clear_timer_locked()
        for cb_id in self._subscription_ids:
            try:
                self._event_handler.unregister(cb_id)
            except Exception:
                pass
        self._subscription_ids.clear()

    # ------------------------------------------------------------------
    # Internal — event routing
    # ------------------------------------------------------------------

    def _on_log_event(self, envelope: EventEnvelope) -> None:
        severity = _EVENT_SEVERITY.get(envelope.name)
        if severity is None:
            return
        message = str(envelope.payload.get("message", "")).strip()
        if not message:
            return
        self.set_message(message, severity)

    # ------------------------------------------------------------------
    # Internal — notification + auto-clear timer
    # ------------------------------------------------------------------

    def _notify_message_changed(self) -> None:
        for cb in list(self._on_message_changed):
            try:
                cb()
            except Exception:
                pass

    def _notify_progress_changed(self) -> None:
        for cb in list(self._on_progress_changed):
            try:
                cb()
            except Exception:
                pass

    def _reschedule_clear_locked(self) -> None:
        self._cancel_clear_timer_locked()
        if self._clear_timeout_s <= 0.0 or not self._message:
            return
        timer = threading.Timer(
            self._clear_timeout_s, self._on_clear_timer_fired
        )
        timer.daemon = True
        self._clear_timer = timer
        timer.start()

    def _cancel_clear_timer_locked(self) -> None:
        if self._clear_timer is not None:
            self._clear_timer.cancel()
            self._clear_timer = None

    def _on_clear_timer_fired(self) -> None:
        with self._lock:
            self._clear_timer = None
            if not self._message:
                return
            self._message = ""
            self._severity = Severity.NONE
        self._notify_message_changed()
