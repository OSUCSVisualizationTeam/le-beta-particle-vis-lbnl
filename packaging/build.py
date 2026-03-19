"""Cross-platform build script for LE Beta Particle Visualization.

Usage:
    python packaging/build.py [--platform {macos,linux,windows,auto}] [--skip-pyinstaller]
    python packaging/build.py --clear
"""

import argparse
import os
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

_BUILD_ARTIFACT_DIRS = [ROOT / "dist", ROOT / "build"]
_BUILD_ARTIFACT_FILES = [PACKAGING / "lbnlvis.ico", PACKAGING / "lbnlvis.icns"]


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


def _check_conda_env() -> None:
    """Warn if not running inside a conda environment."""
    if not os.environ.get("CONDA_PREFIX"):
        print(
            "WARNING: No CONDA_PREFIX detected. "
            "Run this script from within the mlccd_viz conda environment.",
            file=sys.stderr,
        )


def _generate_icons() -> None:
    """Generate .icns and .ico icon variants from the source PNG."""
    try:
        from PIL import Image
    except ImportError:
        print(
            "WARNING: Pillow not installed — skipping icon generation. "
            "Install with: pip install Pillow",
            file=sys.stderr,
        )
        return

    img = Image.open(ICON_SOURCE)

    ico_path = PACKAGING / "lbnlvis.ico"
    if not ico_path.exists():
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(str(ico_path), format="ICO", sizes=sizes)
        print(f"Generated {ico_path}")

    icns_path = PACKAGING / "lbnlvis.icns"
    if not icns_path.exists() and sys.platform == "darwin":
        img.save(str(icns_path), format="ICNS")
        print(f"Generated {icns_path}")


def _run_pyinstaller() -> None:
    """Run PyInstaller with the spec file."""
    spec = PACKAGING / "lbnlvis.spec"
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)],
        cwd=str(ROOT),
        check=True,
    )


def _package_macos(version: str) -> None:
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

    dmg_name = f"LBNLVis-{version}.dmg"
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


def _package_linux(version: str) -> None:
    """Create an AppImage using appimagetool."""
    appdir = DIST / "LBNLVis.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    appdir.mkdir(parents=True)

    # Copy PyInstaller output into AppDir
    src_dir = DIST / "lbnlvis"
    if not src_dir.exists():
        print(f"ERROR: {src_dir} not found. Run PyInstaller first.", file=sys.stderr)
        return

    shutil.copytree(str(src_dir), str(appdir / "usr" / "bin"), dirs_exist_ok=True)

    # Copy AppRun and desktop entry
    shutil.copy2(str(PACKAGING / "appimage" / "AppRun"), str(appdir / "AppRun"))
    os.chmod(str(appdir / "AppRun"), 0o755)
    shutil.copy2(
        str(PACKAGING / "appimage" / "lbnlvis.desktop"),
        str(appdir / "lbnlvis.desktop"),
    )
    shutil.copy2(str(ICON_SOURCE), str(appdir / "lbnlvis.png"))

    # Download appimagetool if not cached
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

    appimage_name = f"LBNLVis-{version}-x86_64.AppImage"
    appimage_path = DIST / appimage_name

    subprocess.run(
        [str(appimagetool), str(appdir), str(appimage_path)],
        check=True,
    )
    print(f"Created {appimage_path}")


def _package_windows(version: str) -> None:
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
        [iscc, f"/DAppVersion={version}", str(iss)],
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
    print(f"Building LE Beta Vis v{version} for {target}")

    _check_conda_env()
    _generate_icons()

    if not args.skip_pyinstaller:
        _run_pyinstaller()

    if target == "macos":
        _package_macos(version)
    elif target == "linux":
        _package_linux(version)
    elif target == "windows":
        _package_windows(version)


if __name__ == "__main__":
    main()
