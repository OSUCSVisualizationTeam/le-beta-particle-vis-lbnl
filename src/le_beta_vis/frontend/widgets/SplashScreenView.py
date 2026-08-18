"""Splash screen View — thin wrapper around QSplashScreen.

All readiness state lives in StartupReadinessViewModel; this class only
polls it on a timer and renders the result, per the "Only create Qt
widgets for views that do not hold state" rule.
"""

from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSplashScreen

from le_beta_vis.frontend.viewmodels.StartupReadinessViewModel import (
    StartupReadinessSnapshot,
    StartupReadinessViewModel,
)


class SplashScreenView:
    """Polls StartupReadinessViewModel on a QTimer and updates splash text.

    Not a QWidget subclass — wraps an already-shown QSplashScreen and owns
    only a QTimer. Call ``begin()`` once the splash is visible.
    """

    def __init__(
        self,
        splash: QSplashScreen,
        view_model: StartupReadinessViewModel,
        poll_interval_ms: int,
    ) -> None:
        self._splash = splash
        self._view_model = view_model
        self._on_ready: Callable[[StartupReadinessSnapshot], None] = lambda _snapshot: None
        self._timer = QTimer()
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._on_tick)

    def begin(self, on_ready: Callable[[StartupReadinessSnapshot], None]) -> None:
        """Starts polling readiness; invokes ``on_ready(snapshot)`` once
        ready, then stops. Starts the timer before the first tick so an
        already-ready result (``_on_tick`` calling ``self._timer.stop()``)
        cleanly cancels it rather than racing a separate start call."""
        self._on_ready = on_ready
        self._timer.start()
        self._on_tick()

    def _on_tick(self) -> None:
        snapshot = self._view_model.poll()
        self._splash.showMessage(
            snapshot.message, Qt.AlignBottom | Qt.AlignHCenter, Qt.darkGray
        )
        if snapshot.ready:
            self._timer.stop()
            self._on_ready(snapshot)
