"""PyInstaller hook for the mlccd_models private package."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("mlccd_models")
