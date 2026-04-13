"""Animated snake-path grid of cluster thumbnails.

Each cell is a ``QLabel`` positioned absolutely within the grid widget.
On each advance step, cells animate to their new positions using
``QPropertyAnimation`` grouped in a ``QParallelAnimationGroup``.
Cell size is computed dynamically from the widget's available space.
"""

from typing import List, Optional

import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import QPropertyAnimation, QParallelAnimationGroup

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)

from .LiveModeViewModel import LiveModeViewModel


class _ThumbnailCell(QLabel):
    """Single thumbnail cell, positioned absolutely in the grid."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)

    def setClusterPixmap(
        self,
        cluster: Optional[Cluster],
        colormap: Optional[Colormap],
        cell_size: int,
        empty_pixmap: Optional[QPixmap] = None,
    ) -> None:
        """Renders a cluster thumbnail into this cell.

        Args:
            cluster: Cluster data, or None for an empty cell.
            colormap: Colormap for rendering.
            cell_size: Target side length in pixels.
            empty_pixmap: Pre-rendered pixmap for empty cells.
        """
        if cluster is None or cluster.data is None:
            if empty_pixmap is not None:
                self.setPixmap(empty_pixmap)
            else:
                pm = QPixmap(cell_size, cell_size)
                pm.fill(Qt.black)
                self.setPixmap(pm)
            return
        pixmap = EnergyClusterWidget.to_pixmap(
            cluster.data,
            colormap,
            cell_size,
        )
        self.setPixmap(pixmap)


class _ThumbnailGridWidget(QWidget):
    """Right-side thumbnail grid for the Live Mode screensaver.

    Displays ``rows * cols`` thumbnail cells arranged in a snake
    path.  Animation is powered by ``QPropertyAnimation``.

    Signals:
        advanceFinished: Emitted when the advance animation completes.
    """

    advanceFinished = Signal()

    def __init__(
        self,
        viewModel: LiveModeViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        rows, cols = viewModel.grid_shape
        self._rows = rows
        self._cols = cols
        self._spacing = viewModel.grid_spacing
        self._cell_size = 1
        self._cells: List[_ThumbnailCell] = []
        self._anim_group: Optional[QParallelAnimationGroup] = None
        self._createCells()

    # --- Public ---

    def populate(self, grid: List[Optional[Cluster]]) -> None:
        """Renders grid state into cell pixmaps without animation.

        Args:
            grid: List of clusters matching the grid capacity.
        """
        colormap = self._vm.colormap
        empty_pm = self._makeEmptyPixmap(colormap, self._cell_size)
        for i, cell in enumerate(self._cells):
            cluster = grid[i] if i < len(grid) else None
            cell.setClusterPixmap(cluster, colormap, self._cell_size, empty_pm)

    @staticmethod
    def _makeEmptyPixmap(
        colormap: Optional[Colormap],
        cell_size: int,
    ) -> QPixmap:
        """Generate a pixmap representing the colormap's zero value."""
        zero_data = np.zeros((1, 1), dtype=np.float32)
        return EnergyClusterWidget.to_pixmap(zero_data, colormap, cell_size)

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
        total = self._rows * self._cols
        for _ in range(total):
            cell = _ThumbnailCell(self)
            cell.setFixedSize(QSize(1, 1))
            self._cells.append(cell)

    def _computeCellSize(self) -> int:
        """Derives cell side length from available widget space."""
        w = self.width()
        h = self.height()
        if self._cols <= 0 or self._rows <= 0:
            return 1
        cell_w = (w - (self._cols - 1) * self._spacing) // self._cols
        cell_h = (h - (self._rows - 1) * self._spacing) // self._rows
        return max(1, min(cell_w, cell_h))

    def _computeVerticalOffset(self) -> int:
        """Returns top margin needed to vertically center the grid."""
        used_h = (
            self._rows * self._cell_size
            + (self._rows - 1) * self._spacing
        )
        return max(0, (self.height() - used_h) // 2)

    def _computeSnakePositions(self) -> List[QPoint]:
        """Returns pixel position for each snake-order index."""
        y_offset = self._computeVerticalOffset()
        positions: List[QPoint] = []
        for i in range(self._rows * self._cols):
            row = i // self._cols
            col_in_row = i % self._cols
            if row % 2 == 0:
                col = col_in_row
            else:
                col = self._cols - 1 - col_in_row
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
        All other cells slide ``shift_count`` positions toward
        index 0.
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
        self._repositionCells()
        self.advanceFinished.emit()

    def _stopAnimation(self) -> None:
        """Stops and cleans up the current animation group."""
        if self._anim_group is not None:
            self._anim_group.stop()
            self._anim_group.deleteLater()
            self._anim_group = None
