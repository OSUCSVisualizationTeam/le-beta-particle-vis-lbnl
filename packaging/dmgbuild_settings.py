"""dmgbuild settings for macOS DMG creation."""

import os

# The app path is injected via -D app=<path>
app = defines.get("app", "/tmp/lbnlvis.app")  # noqa: F821

appname = os.path.basename(app)

# Volume settings
volume_name = "LE Beta Particle Visualization"
format = "UDBZ"
size = None  # auto-calculate

# Window layout
window_rect = ((200, 120), (660, 400))
background_color = "#1e1e1e"

icon_size = 80
icon_locations = {
    appname: (140, 160),
    "Applications": (500, 160),
}

# Symlink to /Applications
symlinks = {"Applications": "/Applications"}
