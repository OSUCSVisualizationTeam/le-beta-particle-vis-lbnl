"""Cross-platform build script for LE Beta Particle Visualization.

Usage:
    python packaging/build.py [--platform {macos,linux,windows,auto}] [--skip-pyinstaller]
    python packaging/build.py --no-use-venv [--platform ...]
    python packaging/build.py --clear
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
ICON_SOURCE = SRC / "le_beta_vis" / "resources" / "icons" / "lbnl-logo.png"

_BUILD_ARTIFACT_DIRS = [ROOT / "dist", ROOT / "build", ROOT / ".packaging-venv"]
_BUILD_ARTIFACT_FILES = [PACKAGING / "lbnlvis.ico", PACKAGING / "lbnlvis.icns"]

_ICON_GEN_SCRIPT = """\
import sys
from PIL import Image

src, ico_dest, icns_dest = sys.argv[1], sys.argv[2], sys.argv[3]
img = Image.open(src)

if ico_dest != "-":
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_dest, format="ICO", sizes=sizes)
    print(f"Generated {ico_dest}")

if icns_dest != "-":
    img.save(icns_dest, format="ICNS")
    print(f"Generated {icns_dest}")
"""


def _clear_build_artifacts() -> None:
    """Remove all build artifacts so the next build starts fresh."""
    for directory in _BUILD_ARTIFACT_DIRS:
        if directory.exists():
            shutil.rmtree(directory)
            print(f"Removed {directory}")

    for filepath in _BUILD_ARTIFACT_FILES:
        if filepath.exists():
            filepath.unlink()
            print(f"Removed {filepath}")


def _read_version() -> str:
    """Read version from pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    with open(pyproject, "rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def _detect_platform() -> str:
    """Return the current platform name."""
    mapping = {"darwin": "macos", "linux": "linux", "win32": "windows"}
    return mapping.get(sys.platform, "linux")


def _detect_arch() -> str:
    """Return the normalized machine architecture."""
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x86_64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return machine


# ---------------------------------------------------------------------------
# UV virtual-environment helpers
# ---------------------------------------------------------------------------

def _find_uv() -> str:
    """Locate the uv executable on PATH."""
    uv = shutil.which("uv")
    if not uv:
        print(
            "ERROR: uv not found on PATH. "
            "Install from https://docs.astral.sh/uv/",
            file=sys.stderr,
        )
        sys.exit(1)
    return uv


def _venv_python(venv_dir: Path) -> Path:
    """Return the Python interpreter path inside a virtual environment."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_packaging_venv() -> str:
    """Create and sync the UV packaging venv.

    Returns the path to the venv Python interpreter.
    """
    venv_dir = ROOT / ".packaging-venv"
    uv = _find_uv()

    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(venv_dir)}
    print("Syncing packaging dependencies...")
    subprocess.run(
        [uv, "sync", "--extra", "packaging", "--no-dev"],
        cwd=str(ROOT),
        env=env,
        check=True,
    )

    python_bin = _venv_python(venv_dir)
    print(f"Packaging venv ready at {venv_dir}")
    return str(python_bin)


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------

def _generate_icons(python_bin: str) -> None:
    """Generate .icns and .ico icon variants from the source PNG."""
    ico_path = PACKAGING / "lbnlvis.ico"
    icns_path = PACKAGING / "lbnlvis.icns"

    ico_arg = str(ico_path) if not ico_path.exists() else "-"
    icns_arg = (
        str(icns_path)
        if not icns_path.exists() and sys.platform == "darwin"
        else "-"
    )

    if ico_arg == "-" and icns_arg == "-":
        return

    try:
        subprocess.run(
            [python_bin, "-c", _ICON_GEN_SCRIPT,
             str(ICON_SOURCE), ico_arg, icns_arg],
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "WARNING: Icon generation failed — Pillow may not be installed.",
            file=sys.stderr,
        )


def _run_pyinstaller(python_bin: str) -> None:
    """Run PyInstaller with the spec file."""
    spec = PACKAGING / "lbnlvis.spec"
    subprocess.run(
        [python_bin, "-m", "PyInstaller", "--noconfirm", str(spec)],
        cwd=str(ROOT),
        check=True,
    )


def _package_macos(version: str, arch: str) -> None:
    """Create a DMG using dmgbuild."""
    app_path = DIST / "lbnlvis.app"
    if not app_path.exists():
        print(f"ERROR: {app_path} not found. Run PyInstaller first.", file=sys.stderr)
        return

    user_guide = ROOT / "wiki" / "User-Guide.pdf"
    if not user_guide.exists():
        print(
            f"WARNING: {user_guide} not found. "
            "DMG will be created without the User Guide.",
            file=sys.stderr,
        )

    dmg_name = f"LBNLVis-macOS-{arch}-{version}.dmg"
    dmg_path = DIST / dmg_name
    settings = PACKAGING / "dmgbuild_settings.py"

    dmgbuild_args = [
        sys.executable, "-m", "dmgbuild",
        "-s", str(settings),
        "-D", f"app={app_path}",
    ]
    if user_guide.exists():
        dmgbuild_args += ["-D", f"user_guide={user_guide}"]
    dmgbuild_args += ["LE Beta Particle Visualization", str(dmg_path)]

    try:
        subprocess.run(dmgbuild_args, check=True)
        print(f"Created {dmg_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"WARNING: dmgbuild failed: {exc}", file=sys.stderr)
        print("Install with: pip install dmgbuild", file=sys.stderr)


def _package_linux(version: str, arch: str) -> None:
    """Create an AppImage using appimagetool."""
    appdir = DIST / "LBNLVis.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    appdir.mkdir(parents=True)

    src_dir = DIST / "lbnlvis"
    if not src_dir.exists():
        print(f"ERROR: {src_dir} not found. Run PyInstaller first.", file=sys.stderr)
        return

    _populate_appdir(appdir, src_dir)

    appimagetool = _ensure_appimagetool()
    appimage_name = f"LBNLVis-Linux-{arch}-{version}.AppImage"
    appimage_path = DIST / appimage_name

    subprocess.run(
        [str(appimagetool), str(appdir), str(appimage_path)],
        check=True,
    )
    print(f"Created {appimage_path}")


def _populate_appdir(appdir: Path, src_dir: Path) -> None:
    """Copy PyInstaller output and AppImage metadata into the AppDir."""
    shutil.copytree(str(src_dir), str(appdir / "usr" / "bin"), dirs_exist_ok=True)

    shutil.copy2(str(PACKAGING / "appimage" / "AppRun"), str(appdir / "AppRun"))
    os.chmod(str(appdir / "AppRun"), 0o755)
    shutil.copy2(
        str(PACKAGING / "appimage" / "lbnlvis.desktop"),
        str(appdir / "lbnlvis.desktop"),
    )
    shutil.copy2(str(ICON_SOURCE), str(appdir / "lbnlvis.png"))


def _ensure_appimagetool() -> Path:
    """Download appimagetool if not cached and return its path."""
    tools_dir = PACKAGING / "tools"
    tools_dir.mkdir(exist_ok=True)
    appimagetool = tools_dir / "appimagetool-x86_64.AppImage"

    if not appimagetool.exists():
        url = (
            "https://github.com/AppImage/AppImageKit/releases/download/"
            "continuous/appimagetool-x86_64.AppImage"
        )
        print(f"Downloading appimagetool from {url}...")
        subprocess.run(["curl", "-L", "-o", str(appimagetool), url], check=True)
        os.chmod(str(appimagetool), 0o755)

    return appimagetool


def _package_windows(version: str, arch: str) -> None:
    """Create an Inno Setup installer."""
    iss = PACKAGING / "lbnlvis.iss"
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if not iscc:
        print(
            "WARNING: Inno Setup (iscc) not found on PATH. "
            "Skipping Windows installer creation.",
            file=sys.stderr,
        )
        return

    subprocess.run(
        [iscc, f"/DAppVersion={version}", f"/DAppArch={arch}", str(iss)],
        check=True,
    )
    print(f"Created Windows installer in {DIST}")


def main() -> None:
    """Build and package the application."""
    parser = argparse.ArgumentParser(description="Build LE Beta Vis installer")
    parser.add_argument(
        "--platform",
        choices=["macos", "linux", "windows", "auto"],
        default="auto",
        help="Target platform (default: auto-detect)",
    )
    parser.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Skip the PyInstaller step (use existing dist/)",
    )
    parser.add_argument(
        "--no-use-venv",
        action="store_true",
        help="Use the current Python instead of creating a UV packaging venv",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all build artifacts and exit",
    )
    args = parser.parse_args()

    if args.clear:
        _clear_build_artifacts()
        return

    target = args.platform if args.platform != "auto" else _detect_platform()
    version = _read_version()
    arch = _detect_arch()
    print(f"Building LE Beta Vis v{version} for {target} ({arch})")

    if args.no_use_venv:
        python_bin = sys.executable
    else:
        python_bin = _ensure_packaging_venv()

    _generate_icons(python_bin)

    if not args.skip_pyinstaller:
        _run_pyinstaller(python_bin)

    if target == "macos":
        _package_macos(version, arch)
    elif target == "linux":
        _package_linux(version, arch)
    elif target == "windows":
        _package_windows(version, arch)


if __name__ == "__main__":
    main()
