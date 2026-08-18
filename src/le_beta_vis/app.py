"""Application entry point for LE Beta Particle Visualization."""

import gc
import logging
import platform
import shutil
import subprocess
import sys
import os
from pathlib import Path

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

log = logging.getLogger(__name__)

APP_ID = "le-beta-vis-lbnl"
_APPLICATION_DISPLAY_NAME = "LE Beta Particle Visualization"

# CPython's cyclic GC can run on whatever thread happens to trip its
# allocation threshold, including background worker threads. If it sweeps
# up a shiboken-wrapped QObject there, that object's C++ destructor runs
# off the main thread, which can touch Qt internals (timers, animations)
# that assert GUI-thread ownership. Disabling automatic collection and
# driving it from a main-thread QTimer instead keeps all QObject
# deallocation on the GUI thread.
_GC_INTERVAL_MS = 10_000


def _resolve_resource_path(relative: str) -> Path:
    """Resolve a resource path for both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    return base / relative


ICON_PATH = _resolve_resource_path(
    os.path.join("resources", "icons", "lbnl-logo.png")
)
QSS_DIR = _resolve_resource_path(os.path.join("resources", "qss"))
SPLASH_PATH = _resolve_resource_path(
    os.path.join("resources", "images", "splash.png")
)

XDG_DATA_HOME = Path(
    os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
)
XDG_ICON_DIR = XDG_DATA_HOME / "icons" / "hicolor" / "256x256" / "apps"
XDG_DESKTOP_DIR = XDG_DATA_HOME / "applications"
XDG_HICOLOR_ROOT = XDG_DATA_HOME / "icons" / "hicolor"

_DESKTOP_ENTRY = f"""\
[Desktop Entry]
Type=Application
Name={_APPLICATION_DISPLAY_NAME}
Comment=Low-Energy Beta Particle Track Visualization Tool (LBNL)
Icon={{app_id}}
Terminal=false
Categories=Science;Education;
StartupWMClass={{app_id}}
"""


def _install_linux_desktop_integration() -> None:
    """Install the XDG .desktop file and icon on first run.

    Copies the app icon into the hicolor icon theme and writes a
    .desktop file so that GNOME, KDE, and other freedesktop-compliant
    desktops can display the application icon in the app switcher,
    taskbar, and dock.  Runs once; subsequent launches skip the copy
    when both files already exist.
    """
    icon_dest = XDG_ICON_DIR / f"{APP_ID}.png"
    desktop_dest = XDG_DESKTOP_DIR / f"{APP_ID}.desktop"

    if icon_dest.exists() and desktop_dest.exists():
        return

    XDG_ICON_DIR.mkdir(parents=True, exist_ok=True)
    XDG_DESKTOP_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(str(ICON_PATH), str(icon_dest))
    desktop_dest.write_text(_DESKTOP_ENTRY.format(app_id=APP_ID))

    try:
        subprocess.run(
            [
                "gtk-update-icon-cache",
                "-f",
                "-t",
                str(XDG_HICOLOR_ROOT),
            ],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass

    log.info("Installed XDG desktop entry and icon for %s", APP_ID)


def _show_splash(app: QApplication) -> QSplashScreen:
    """Shows the splash screen and confirms it is actually on screen.

    ``processEvents()`` flushes Qt's event queue but does not wait for
    macOS's Core Animation compositor to commit the frame to the display
    (CA commits are vsync-aligned, not tied to the Qt event queue). Spin a
    nested event loop for 50 ms — covering three vsync periods at 60 Hz —
    so the splash is guaranteed to be on screen before blocking imports
    begin.
    """
    splash = QSplashScreen(QPixmap(str(SPLASH_PATH)))
    splash.show()
    app.processEvents()
    splash.showMessage(
        "Loading…", Qt.AlignBottom | Qt.AlignHCenter, Qt.darkGray
    )
    app.processEvents()

    vsync_wait = QEventLoop()
    QTimer.singleShot(50, vsync_wait.quit)
    vsync_wait.exec()
    return splash


def main() -> None:
    """Launch the LE Beta Particle Visualization application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    gc.disable()
    current_platform = platform.system()

    if current_platform == "Windows":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "lbnl.le_beta_vis.app"
        )
    elif current_platform == "Linux":
        try:
            _install_linux_desktop_integration()
        except OSError:
            log.warning(
                "Could not install XDG desktop integration",
                exc_info=True,
            )

    QApplication.setDesktopFileName(APP_ID)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))

    gc_timer = QTimer()
    gc_timer.setInterval(_GC_INTERVAL_MS)
    gc_timer.timeout.connect(gc.collect)
    gc_timer.start()

    splash = _show_splash(app)

    # Deferred until the splash is confirmed on screen: MainWindow and
    # ServicesManager pull a large transitive dependency chain (PySide6's
    # Cocoa platform plugin, pyqtgraph, scipy, numpy) that otherwise delays
    # the first paint on macOS. mlccd_diffusion/cv2 are pre-warmed here too
    # so their first-import GIL cost lands before the user can interact
    # with the main window (issue #207).
    from le_beta_vis.common import APP_VERSION, ThemeManager
    from le_beta_vis.common.YAMLBackedConfigurationService import (
        YAMLBackedConfigurationService,
    )
    from le_beta_vis.common.IPCFallbackSupport import should_show_ipc_fallback_dialog
    from le_beta_vis.common.EPSStartupSignals import (
        DEFAULT_STATUS_PUB_ENDPOINT,
        EPS_STARTUP_STATUS_EVENT,
    )
    from le_beta_vis.common.EventHandler import EventHandler
    from le_beta_vis.common.ZMQEventHandlerSource import ZMQEventHandlerSource
    from le_beta_vis.frontend.MainWindow import MainWindow
    from le_beta_vis.frontend.viewmodels.IPCFallbackViewModel import IPCFallbackViewModel
    from le_beta_vis.frontend.viewmodels.MainWindowStatusViewModel import Severity
    from le_beta_vis.frontend.viewmodels.StartupReadinessViewModel import (
        StartupReadinessViewModel,
    )
    from le_beta_vis.frontend.widgets.IPCFallbackDialogView import IPCFallbackDialogView
    from le_beta_vis.frontend.widgets.SplashScreenView import SplashScreenView
    from le_beta_vis.backend.ServicesManager import ServicesManager

    import mlccd_diffusion.help_functions  # noqa: F401
    import cv2  # noqa: F401

    app.setApplicationName(_APPLICATION_DISPLAY_NAME)
    app.setApplicationDisplayName(_APPLICATION_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(ThemeManager().load_stylesheet(QSS_DIR))

    # In the future, we would load a QTranslator here:
    # translator = QTranslator()
    # if translator.load(QLocale.system(), "app", "_", "translations"):
    #     app.installTranslator(translator)

    config = YAMLBackedConfigurationService()
    if should_show_ipc_fallback_dialog(config):
        # should_show_ipc_fallback_dialog() already logged the probe result;
        # this line marks the app.py decision point in the same console stream.
        log.warning("Windows ipc:// transport unsupported; showing fallback dialog.")
        fallback_vm = IPCFallbackViewModel(config)
        fallback_dialog = IPCFallbackDialogView(fallback_vm)
        fallback_dialog.exec()
        sys.exit(0)

    # Started before ServicesManager so the SUB socket is already
    # subscribing by the time EPS's status PUB socket binds — one half of
    # the mitigation for the ZMQ pub/sub "slow joiner" race (the other half
    # is EventPersistence's bounded re-broadcast burst after binding).
    startup_event_handler = EventHandler(config)
    startup_readiness_vm = StartupReadinessViewModel(config, startup_event_handler)
    startup_event_source = ZMQEventHandlerSource(
        endpoint=str(
            config.get("eps:status_pub_endpoint", DEFAULT_STATUS_PUB_ENDPOINT)
        ),
        event_handler=startup_event_handler,
        config=config,
        subscriptions=[EPS_STARTUP_STATUS_EVENT],
    )
    startup_event_source.start()

    services = ServicesManager()
    services.start_all()

    def _launch_main_window(snapshot) -> None:
        # The temporary startup-phase bus has done its job; MainWindow
        # builds its own permanent EventHandler/ZMQEventHandlerSource pair
        # (on the separate log-forwarding endpoint) in its own ViewModel.
        startup_event_source.shutdown()
        startup_event_handler.shutdown()

        window = MainWindow()
        if snapshot.degraded:
            window.statusViewModel.set_message(
                snapshot.message, severity=Severity.WARNING
            )
        window.show()
        splash.finish(window)

        def cleanup() -> None:
            services.stop_all()

        app.aboutToQuit.connect(cleanup)

    poll_interval_ms = config.get_int(
        "gui:startup:poll_interval_ms", 150, minimum=1
    )
    splash_view = SplashScreenView(splash, startup_readiness_vm, poll_interval_ms)
    splash_view.begin(on_ready=_launch_main_window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
