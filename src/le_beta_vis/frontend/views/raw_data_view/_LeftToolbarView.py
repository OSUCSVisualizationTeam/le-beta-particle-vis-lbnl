from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFrame, QVBoxLayout

from ...widgets.VerticalRangeControl import VerticalRangeControl

if TYPE_CHECKING:
    from ...viewmodels.RawDataViewModel import RawDataViewModel


class _LeftToolbarView(QFrame):
    """Narrow left sidebar: vertical range control and future tool buttons."""

    def __init__(self, viewModel: RawDataViewModel) -> None:
        super().__init__()
        self._vm = viewModel
        self._initUI()

    def _initUI(self) -> None:
        self.setFixedWidth(100)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(0)

        self.rangeControl = VerticalRangeControl(abs_min=0.0, abs_max=1.0)
        self.rangeControl.setVisible(False)
        self.rangeControl.rangeChanged.connect(
            lambda vmin, vmax: self._vm.setVisualizationRange(vmin, vmax)
        )
        layout.addWidget(self.rangeControl, 1)
