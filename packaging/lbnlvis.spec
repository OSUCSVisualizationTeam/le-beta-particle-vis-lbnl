# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for LE Beta Particle Visualization."""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
RESOURCES = SRC / "le_beta_vis" / "resources"
CONFIG = SRC / "le_beta_vis" / "config"

a = Analysis(
    [str(ROOT / "run_app.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(RESOURCES), "resources"),
        (str(CONFIG / "defaults.yaml"), "config"),
    ],
    hiddenimports=[
        "mlccd_models",
        "astropy.io.fits",
    ],
    hookspath=[str(ROOT / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    collect_data=["astropy"],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lbnlvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "packaging" / "lbnlvis.ico")
    if sys.platform == "win32"
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="lbnlvis",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="lbnlvis.app",
        icon=str(ROOT / "packaging" / "lbnlvis.icns"),
        bundle_identifier="edu.oregonstate.lbnl.lbnlvis",
    )
