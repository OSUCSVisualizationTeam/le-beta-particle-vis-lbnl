"""Application metadata resolved from pyproject.toml."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

_logger = logging.getLogger(__name__)
_PYPROJECT_PATH = Path(__file__).resolve().parents[3] / "pyproject.toml"

_DEFAULT_REPOSITORY_URL = (
    "https://github.com/OSUCSVisualizationTeam/le-beta-particle-vis-lbnl"
)


def _resolve_pyproject_path() -> Path:
    """Return the pyproject.toml path, handling frozen and dev modes."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "pyproject.toml"  # type: ignore[attr-defined]
    return _PYPROJECT_PATH


def _load_pyproject() -> Optional[dict]:
    """Parse the bundled/dev pyproject.toml, or None if unreadable."""
    path = _resolve_pyproject_path()
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        _logger.warning("Could not read pyproject.toml: %s", exc)
        return None


def _read_pyproject_version() -> Optional[str]:
    """Return the version string, handling both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        try:
            from importlib.metadata import version
            return version("le-beta-vis-lbnl")
        except Exception:
            _logger.debug("importlib.metadata unavailable in frozen app, "
                          "falling back to bundled pyproject.toml")

    data = _load_pyproject()
    if data is None:
        return None
    return data.get("project", {}).get("version")


def _read_pyproject_repository_url() -> Optional[str]:
    """Return the repository URL declared in pyproject.toml's [project.urls]."""
    data = _load_pyproject()
    if data is None:
        return None
    return data.get("project", {}).get("urls", {}).get("Repository")


APP_VERSION: str = _read_pyproject_version() or "0.0.0"
APP_NAME: str = "LE Beta Particle Visualization"
APP_REPOSITORY_URL: str = (
    _read_pyproject_repository_url() or _DEFAULT_REPOSITORY_URL
)
APP_REPOSITORY_BLOB_BASE_URL: str = f"{APP_REPOSITORY_URL}/blob/main/"
