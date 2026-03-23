"""dmgbuild settings for macOS DMG creation."""

import os

# The app path is injected via -D app=<path>
app = defines.get("app", "/tmp/lbnlvis.app")  # noqa: F821
user_guide = defines.get("user_guide", "")  # noqa: F821

# Present the app with a user-friendly name inside the DMG
display_name = "LE Beta Vis.app"
files = [(app, display_name)]
if user_guide:
    files.append((user_guide, "User Guide.pdf"))

# Volume settings — title bar doubles as drag instruction
volume_name = "Drag LE Beta Vis to Applications"
format = "UDBZ"
size = None  # auto-calculate

# Window layout
window_rect = ((200, 120), (660, 480))
background_color = "#1e1e1e"

icon_size = 80
icon_locations = {
    display_name: (140, 140),
    "Applications": (500, 140),
}
if user_guide:
    icon_locations["User Guide.pdf"] = (320, 340)

# Symlink to /Applications
symlinks = {"Applications": "/Applications"}
