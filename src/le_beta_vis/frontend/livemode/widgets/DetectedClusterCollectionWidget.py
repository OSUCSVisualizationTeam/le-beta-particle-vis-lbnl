"""Right panel widget for the Live Mode screensaver.

Displays all recently detected clusters as an animated snake-path grid.
Each cell is a ``QLabel`` positioned absolutely within the widget.
On each advance step, cells animate to their new positions using
``QPropertyAnimation`` grouped in a ``QParallelAnimationGroup``.
Cell size is computed dynamically from the available space.
"""

from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QSize,
    Signal,
)
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QWidget

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.widgets.EnergyClusterWidget import EnergyClusterWidget

from ..LiveModeViewModel import LiveModeViewModel
from ._ThumbnailCell import _ThumbnailCell


class DetectedClusterCollectionWidget(QWidget):
    """Animated snake-path grid panel showing all recently detected clusters.

    Displays ``rows * cols`` thumbnail cells arranged in a snake path.
    Animation is powered by ``QPropertyAnimation``.

    Signals:
        advanceFinished: Emitted when the advance animation completes.

    Args:
        vm: The Live Mode ViewModel.
        parent: Optional parent widget.
    """

    advanceFinished = Signal()

    def __init__(
        self,
        vm: LiveModeViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        rows, cols = vm.grid_shape
        self._rows = rows
        self._cols = cols
        self._spacing = vm.grid_spacing
        self._cell_size = 1
        self._cells: List[_ThumbnailCell] = []
        self._anim_group: Optional[QParallelAnimationGroup] = None
        self._deferred_grid: Optional[List[Optional[Cluster]]] = None
        self._cell_click_handler: Optional[Callable[[Cluster], None]] = None
        self._createCells()

    # --- Public ---

    def populate(self, grid: List[Optional[Cluster]]) -> None:
        """Render grid state into cell pixmaps without animation.

        Args:
            grid: List of clusters matching the grid capacity.
        """
        colormap = self._vm.colormap
        empty_pm = self._makeEmptyPixmap(colormap, self._cell_size)
        target_side = self._computeCommonBboxSide(grid)
        classifiers_enabled = self._vm.badges_classifiers_enabled
        min_cell_size_px = self._vm.badges_min_cell_size_px
        physics = self._vm.physics
        for i, cell in enumerate(self._cells):
            cluster = grid[i] if i < len(grid) else None
            cell.setClusterPixmap(
                cluster, colormap, self._cell_size, empty_pm,
                target_side=target_side,
                physics=physics,
                classifiers_enabled=classifiers_enabled,
                min_cell_size_px=min_cell_size_px,
            )

    def isAnimating(self) -> bool:
        """True while a snake-shift animation group is running."""
        return (
            self._anim_group is not None
            and self._anim_group.state() == QAbstractAnimation.Running
        )

    def scheduleRepaint(self, grid: List[Optional[Cluster]]) -> None:
        """Repaint immediately, or defer until any active animation ends.

        During an active ``animateAdvance`` the positional pixmap
        mapping is in the middle of shifting; calling ``populate``
        mid-flight would paint post-advance content onto cells that
        are still physically at their old positions and cause
        visible jitter. When animating, the latest grid is stashed
        and applied from ``_onAnimationFinished``.
        """
        if self.isAnimating():
            self._deferred_grid = grid
            return
        self.populate(grid)

    def animateAdvance(
        self,
        new_grid: List[Optional[Cluster]],
        shift_count: int = 1,
    ) -> None:
        """Animate a snake-path shift, then update cell content.

        Args:
            new_grid: The grid state AFTER the advance.
            shift_count: Number of positions each cell shifts toward
                index 0.  Typically equals the number of clusters
                drained from the incoming queue.
        """
        self._stopAnimation()
        positions = self._computeSnakePositions()
        self._anim_group = QParallelAnimationGroup(self)
        duration = self._vm.animation_duration_ms

        for i, cell in enumerate(self._cells):
            target = self._targetAfterShift(i, positions, shift_count)
            anim = QPropertyAnimation(cell, b"pos", self)
            anim.setDuration(duration)
            anim.setStartValue(cell.pos())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            self._anim_group.addAnimation(anim)

        self._pending_grid = new_grid
        self._anim_group.finished.connect(self._onAnimationFinished)
        self._anim_group.start()

    def set_cell_click_handler(
        self, handler: Optional[Callable[[Cluster], None]],
    ) -> None:
        """Set a callback invoked when any thumbnail cell is clicked.

        Args:
            handler: Called with the clicked cluster, or None to clear.
        """
        self._cell_click_handler = handler
        for cell in self._cells:
            cell._on_click = handler

    def pause_animation(self) -> None:
        """Pause the current animation group if one is running."""
        if self._anim_group is not None:
            self._anim_group.pause()

    def resume_animation(self) -> None:
        """Resume a paused animation group."""
        if self._anim_group is not None:
            self._anim_group.resume()

    def stop(self) -> None:
        """Immediately stop any running animation."""
        self._stopAnimation()

    # --- Events ---

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute cell sizes and reposition on resize."""
        super().resizeEvent(event)
        self._cell_size = self._computeCellSize()
        self._repositionCells()

    # --- Private ---

    def _createCells(self) -> None:
        """Instantiate all thumbnail cell widgets."""
        for _ in range(self._rows * self._cols):
            cell = _ThumbnailCell(self)
            cell.setFixedSize(QSize(1, 1))
            cell._on_click = self._cell_click_handler
            self._cells.append(cell)

    @staticmethod
    def _makeEmptyPixmap(colormap: Optional[Colormap], cell_size: int) -> QPixmap:
        """Generate a pixmap representing the colormap's zero value."""
        return EnergyClusterWidget.to_pixmap(
            np.zeros((1, 1), dtype=np.float32), colormap, cell_size
        )

    @staticmethod
    def _computeCommonBboxSide(
        grid: List[Optional[Cluster]],
    ) -> Optional[int]:
        """Returns the largest bbox side across data-bearing clusters.

        All cells pad to this shared side so a 5×5 cluster and a
        40×40 cluster render at proportionally different on-screen
        sizes, preserving relative spatial scale. Returns ``None``
        when the grid has no cluster data.
        """
        sides = [
            max(c.data.shape[:2])
            for c in grid
            if c is not None and c.data is not None and c.data.size > 0
        ]
        return max(sides) if sides else None

    def _computeCellSize(self) -> int:
        """Derives cell side length from available widget space."""
        if self._cols <= 0 or self._rows <= 0:
            return 1
        cell_w = (self.width() - (self._cols - 1) * self._spacing) // self._cols
        cell_h = (self.height() - (self._rows - 1) * self._spacing) // self._rows
        return max(1, min(cell_w, cell_h))

    def _computeVerticalOffset(self) -> int:
        """Returns top margin needed to vertically center the grid."""
        used_h = self._rows * self._cell_size + (self._rows - 1) * self._spacing
        return max(0, (self.height() - used_h) // 2)

    def _computeSnakePositions(self) -> List[QPoint]:
        """Returns pixel position for each snake-order index."""
        y_offset = self._computeVerticalOffset()
        positions: List[QPoint] = []
        for i in range(self._rows * self._cols):
            row = i // self._cols
            col_in_row = i % self._cols
            col = col_in_row if row % 2 == 0 else self._cols - 1 - col_in_row
            x = col * (self._cell_size + self._spacing)
            y = y_offset + row * (self._cell_size + self._spacing)
            positions.append(QPoint(x, y))
        return positions

    def _targetAfterShift(
        self,
        index: int,
        positions: List[QPoint],
        shift_count: int = 1,
    ) -> QPoint:
        """Computes where cell at index moves after a multi-step shift.

        Cells at indices below ``shift_count`` stay in place (they
        will be repainted by ``populate`` after the animation).
        All other cells slide ``shift_count`` positions toward index 0.
        """
        if index < shift_count:
            return positions[index]
        return positions[index - shift_count]

    def _repositionCells(self) -> None:
        """Moves all cells to their current snake positions."""
        positions = self._computeSnakePositions()
        size = QSize(self._cell_size, self._cell_size)
        for i, cell in enumerate(self._cells):
            if i < len(positions):
                cell.setFixedSize(size)
                cell.move(positions[i])

    def _onAnimationFinished(self) -> None:
        """Slot: animation done, update pixmaps and reposition."""
        if hasattr(self, "_pending_grid"):
            self.populate(self._pending_grid)
            del self._pending_grid
        if self._deferred_grid is not None:
            self.populate(self._deferred_grid)
            self._deferred_grid = None
        self._repositionCells()
        self.advanceFinished.emit()

    def _stopAnimation(self) -> None:
        """Stops and cleans up the current animation group."""
        if self._anim_group is not None:
            self._anim_group.stop()
            self._anim_group.deleteLater()
            self._anim_group = None
