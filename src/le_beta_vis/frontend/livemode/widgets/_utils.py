"""Package-internal utilities for Live Mode widgets."""

from PySide6.QtWidgets import QApplication

from ..LiveModeViewModel import LiveModeViewModel


def livemode_icon_size(vm: LiveModeViewModel) -> int:
    """Return the icon side length in pixels for Live Mode controls.

    Scales with screen height via ``gui:livemode:controls:icon_size_pct``,
    with a floor of 24 px so icons remain legible on small or unusual displays.
    """
    screen = QApplication.primaryScreen()
    height = screen.size().height() if screen else 1080
    return max(24, int(height * vm.controls_icon_size_pct / 100))
