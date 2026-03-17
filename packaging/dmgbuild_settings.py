"""dmgbuild settings for macOS DMG creation."""

import os

# The app path is injected via -D app=<path>
app = defines.get("app", "/tmp/lbnlvis.app")  # noqa: F821
user_guide = defines.get("user_guide", "")  # noqa: F821

appname = os.path.basename(app)

# Files to include in the DMG
files = [app]
if user_guide:
    files.append((user_guide, "User Guide.pdf"))

# Volume settings
volume_name = "LE Beta Particle Visualization"
format = "UDBZ"
size = None  # auto-calculate

# Window layout
window_rect = ((200, 120), (660, 480))
background_color = "#1e1e1e"

icon_size = 80
icon_locations = {
    appname: (140, 140),
    "Applications": (500, 140),
}
if user_guide:
    icon_locations["User Guide.pdf"] = (320, 340)

# Symlink to /Applications
symlinks = {"Applications": "/Applications"}
