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


def _read_pyproject_version() -> Optional[str]:
    """Return the version string, handling both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        try:
            from importlib.metadata import version
            return version("le-beta-vis-lbnl")
        except Exception as exc:
            _logger.warning("Could not read version via importlib.metadata: %s", exc)
            return None

    try:
        with open(_PYPROJECT_PATH, "rb") as fh:
            data = tomllib.load(fh)
        return data.get("project", {}).get("version")
    except Exception as exc:
        _logger.warning("Could not read version from pyproject.toml: %s", exc)
        return None


APP_VERSION: str = _read_pyproject_version() or "0.0.0"
APP_NAME: str = "LE Beta Particle Visualization"
