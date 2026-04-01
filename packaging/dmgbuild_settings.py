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

# Window layout — height includes the macOS title bar (~28pt on Big Sur+),
# so add 28 to the background image height (480) to avoid clipping.
window_rect = ((200, 120), (660, 508))
background = defines.get("background", "")  # noqa: F821

icon_size = 80
icon_locations = {
    display_name: (160, 250),
    "Applications": (500, 250),
}
if user_guide:
    icon_locations["User Guide.pdf"] = (330, 340)

# Symlink to /Applications
symlinks = {"Applications": "/Applications"}
