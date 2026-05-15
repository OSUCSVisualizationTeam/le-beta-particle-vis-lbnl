"""Application entry point for LE Beta Particle Visualization."""

import logging
import platform
import shutil
import subprocess
import sys
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

log = logging.getLogger(__name__)

APP_ID = "le-beta-vis-lbnl"
_APPLICATION_DISPLAY_NAME = "LE Beta Particle Visualization"


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


def main() -> None:
    """Launch the LE Beta Particle Visualization application."""
    _t = time.perf_counter()

    def _mark(label: str) -> None:
        print(f"[startup] {(time.perf_counter() - _t) * 1000:6.1f} ms  {label}", flush=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
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

    _mark("main() entered, platform setup done")

    QApplication.setDesktopFileName(APP_ID)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    _mark("QApplication created")

    splash = QSplashScreen(QPixmap(str(SPLASH_PATH)))
    splash.show()
    app.processEvents()
    splash.showMessage("Loading…", Qt.AlignBottom | Qt.AlignHCenter, Qt.darkGray)
    _mark("splash shown + processEvents()")

    def _load() -> None:
        _mark("_load() entered (first event loop frame — splash now on screen)")

        try:
            # mlccd_diffusion and cv2 are pre-warmed here so their first-import
            # GIL cost occurs before the user can interact with the main window.
            from le_beta_vis.common import APP_VERSION
            _mark("imported le_beta_vis.common")

            from le_beta_vis.frontend.MainWindow import MainWindow
            _mark("imported MainWindow")

            from le_beta_vis.backend.ServicesManager import ServicesManager
            _mark("imported ServicesManager")

            import mlccd_diffusion.help_functions  # noqa: F401
            _mark("imported mlccd_diffusion")

            import cv2  # noqa: F401
            _mark("imported cv2")

            app.setApplicationName(_APPLICATION_DISPLAY_NAME)
            app.setApplicationDisplayName(_APPLICATION_DISPLAY_NAME)
            app.setApplicationVersion(APP_VERSION)

            # In the future, we would load a QTranslator here:
            # translator = QTranslator()
            # if translator.load(QLocale.system(), "app", "_", "translations"):
            #     app.installTranslator(translator)

            services = ServicesManager()
            services.start_all()
            _mark("ServicesManager started")

            def cleanup() -> None:
                services.stop_all()

            app.aboutToQuit.connect(cleanup)

            window = MainWindow()
            _mark("MainWindow constructed")

            window.show()
            splash.finish(window)
            _mark("window shown, splash dismissed")

        except Exception:
            log.exception("Fatal error during application startup")
            app.exit(1)

    # Defer all heavy loading so the event loop gets one full iteration first.
    # On macOS, Core Animation defers frame commits until the run loop yields;
    # without this, processEvents() alone does not guarantee the splash paints
    # to screen before blocking imports begin.
    QTimer.singleShot(0, _load)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
