"""Raw text access to repo-root license and notice documents."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from .AppInfo import APP_REPOSITORY_BLOB_BASE_URL

_logger = logging.getLogger(__name__)
_REPO_ROOT_PATH = Path(__file__).resolve().parents[3]

# Matches a markdown link target: `](target)`.
_MARKDOWN_LINK_TARGET = re.compile(r"\]\(([^)]+)\)")


def _resolve_repo_root_file(filename: str) -> Path:
    """Return the path to a repo-root file, handling frozen and dev modes."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / filename  # type: ignore[attr-defined]
    return _REPO_ROOT_PATH / filename


def _read_repo_root_text(filename: str, fallback: str) -> str:
    """Read a repo-root file's text, returning fallback if unavailable."""
    path = _resolve_repo_root_file(filename)
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        _logger.warning("Could not read %s: %s", filename, exc)
        return fallback


def _rewrite_relative_links(markdown_text: str, base_url: str) -> str:
    """Rewrite repo-relative markdown link targets to absolute `base_url` links.

    THIRD_PARTY_NOTICES.md is authored to be browsed on GitHub or in a local
    markdown editor, where repo-relative targets (e.g. "pyproject.toml")
    resolve correctly against the file's own location. Neither assumption
    holds once the text is embedded in the app, so relative targets are
    rewritten here before display; already-absolute targets are untouched.
    """
    def _rewrite(match: "re.Match[str]") -> str:
        target = match.group(1)
        if "://" in target or target.startswith("#") or target.startswith("mailto:"):
            return match.group(0)
        return f"]({base_url}{target})"

    return _MARKDOWN_LINK_TARGET.sub(_rewrite, markdown_text)


def get_license_text() -> str:
    """Return the raw text of the project's LICENSE file."""
    return _read_repo_root_text(
        "LICENSE",
        "License file not found. See the project repository for license terms.",
    )


def get_third_party_notices_text() -> str:
    """Return THIRD_PARTY_NOTICES.md text with relative links made absolute."""
    text = _read_repo_root_text(
        "THIRD_PARTY_NOTICES.md",
        "Third-party notices file not found. See the project repository "
        "for third-party license attributions.",
    )
    return _rewrite_relative_links(text, APP_REPOSITORY_BLOB_BASE_URL)
