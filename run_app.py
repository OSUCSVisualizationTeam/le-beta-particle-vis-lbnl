import logging
import platform
import shutil
import subprocess
import sys
import os
from pathlib import Path

# Add the src directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from le_beta_vis.frontend.MainWindow import MainWindow  # noqa: E402
from le_beta_vis.backend.ServicesManager import ServicesManager

log = logging.getLogger(__name__)

APP_ID = "le-beta-vis-lbnl"

ICON_PATH = (
    Path(__file__).resolve().parent
    / "src"
    / "le_beta_vis"
    / "resources"
    / "icons"
    / "lbnl-logo.png"
)

XDG_DATA_HOME = Path(
    os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
)
XDG_ICON_DIR = XDG_DATA_HOME / "icons" / "hicolor" / "256x256" / "apps"
XDG_DESKTOP_DIR = XDG_DATA_HOME / "applications"
XDG_HICOLOR_ROOT = XDG_DATA_HOME / "icons" / "hicolor"

_DESKTOP_ENTRY = """\
[Desktop Entry]
Type=Application
Name=LE Beta Particle Visualization
Comment=Low-Energy Beta Particle Track Visualization Tool (LBNL)
Icon={app_id}
Terminal=false
Categories=Science;Education;
StartupWMClass={app_id}
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


def main():
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

    # In the future, we would load a QTranslator here:
    # translator = QTranslator()
    # if translator.load(QLocale.system(), "app", "_", "translations"):
    #     app.installTranslator(translator)

    services = ServicesManager()
    services.start_all()

    window = MainWindow()
    window.show()

    def cleanup():
        services.stop_all()
    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
