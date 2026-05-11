"""SVG icon loading + resource path resolution for the frontend.

This module hosts the first SVG-icon path in the project. Icons live
under ``src/le_beta_vis/resources/icons/`` (bundled wholesale by the
PyInstaller spec). The :func:`load_icon` helper supports optional fill
recolouring so neutral Material Symbols icons can be tinted at the
call site (e.g. green for an active toggle).
"""

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_DEFAULT_RENDER_SIZE = QSize(256, 256)
_UPSTREAM_FILL_HEX = b"#e3e3e3"


def resolve_resource_path(relative: str) -> Path:
    """Resolve a path under the packaged ``resources/`` tree.

    Works both in dev (where the file lives under
    ``src/le_beta_vis/<relative>``) and in PyInstaller-frozen bundles
    (where ``sys._MEIPASS`` is the extraction root).

    Mirrors ``_resolve_resource_path`` in ``app.py`` but is anchored on
    the package root rather than ``app.py``'s parent, so it can be
    called from any module under ``frontend/``.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        # icons.py lives at src/le_beta_vis/frontend/icons.py — two
        # parents up gives the le_beta_vis package root.
        base = Path(__file__).resolve().parent.parent
    return base / relative


def load_icon(name: str, color: Optional[str] = None) -> QIcon:
    """Load an SVG icon from ``resources/icons/<name>.svg``.

    When *color* is supplied, the upstream Material Symbols fill
    (``#e3e3e3``) is substituted in the SVG text before rendering, so
    the same source asset serves multiple visual states (e.g. neutral
    grey vs accent green for a toggle).

    Returns an empty :class:`QIcon` if the file is missing — callers
    can treat that as a no-op without crashing.
    """
    path = resolve_resource_path(f"resources/icons/{name}.svg")
    if not path.exists():
        return QIcon()
    if color is None:
        return QIcon(str(path))
    svg_bytes = path.read_bytes()
    recoloured = svg_bytes.replace(_UPSTREAM_FILL_HEX, color.lower().encode())
    renderer = QSvgRenderer(QByteArray(recoloured))
    pixmap = QPixmap(_DEFAULT_RENDER_SIZE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
