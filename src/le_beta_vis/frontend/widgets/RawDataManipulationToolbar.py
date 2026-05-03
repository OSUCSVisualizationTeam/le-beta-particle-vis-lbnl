"""Horizontal toolbar for the Raw Data Analysis view.

Owns the tool-selection buttons (ROI box-select, magnifier), zoom controls,
and the active-HDU indicator label.  Binds ViewModel callbacks directly so
RawDataView only needs to call setZoomControlsEnabled() during a zoom
transform and setEnabled() during clustering.
"""

from PySide6.QtCore import QMetaObject, QSize, Qt, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
)

from ..theme import RawDataManipulationToolbarColors, TooltipStyle
from ..viewmodels.RawDataViewModel import ActiveTool, RawDataViewModel


class _Style:
    TOOLBAR = "background-color: #2d2d2d; border-bottom: 1px solid #3d3d3d;"
    BUTTON = "QToolButton { font-weight: bold; color: #ffffff; }" f"{TooltipStyle.QSS}"
    DIVIDER = "background-color: #555555;"
    ZOOM_IN = (
        "QToolButton { font-size: 20px; font-weight: bold; color: #ffffff; }"
        f"{TooltipStyle.QSS}"
    )
    ZOOM_OUT = (
        "QToolButton { font-size: 20px; font-weight: bold; color: #ffffff; }"
        f"{TooltipStyle.QSS}"
    )
    HDU_LABEL = (
        f"color: {RawDataManipulationToolbarColors.HDU_LABEL};"
        " font-size: 11px; padding-left: 8px; font-weight: bold;"
    )


class RawDataManipulationToolbar(QFrame):
    """Horizontal toolbar strip for the Raw Data Analysis view."""

    def __init__(self, viewModel: RawDataViewModel) -> None:
        super().__init__()
        self._viewModel = viewModel
        self._setupUI()
        self._bindViewModel()

    def _setupUI(self) -> None:
        self.setFixedHeight(46)
        self.setStyleSheet(_Style.TOOLBAR)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(4)
        self._createToolButtons(layout)
        self._createZoomButtons(layout)
        self._createHDULabel(layout)

    def _createToolButtons(self, layout: QHBoxLayout) -> None:
        """Creates the exclusive tool button group (ROI + Magnifier)."""
        btn_size = QSize(36, 36)

        self._toolButtonGroup = QButtonGroup(self)
        self._toolButtonGroup.setExclusive(True)

        self.btnBoxSelect = QToolButton()
        self.btnBoxSelect.setIcon(self._createBoxSelectIcon())
        self.btnBoxSelect.setToolTip(self.tr("Region Of Interest"))
        self.btnBoxSelect.setCheckable(True)
        self.btnBoxSelect.setChecked(True)
        self.btnBoxSelect.setFixedSize(btn_size)
        self.btnBoxSelect.setStyleSheet(_Style.BUTTON)
        self.btnBoxSelect.clicked.connect(
            lambda: self._viewModel.setActiveTool(ActiveTool.BOX_SELECT)
        )
        self._toolButtonGroup.addButton(self.btnBoxSelect)
        layout.addWidget(self.btnBoxSelect)

        self.btnMagnifier = QToolButton()
        self.btnMagnifier.setIcon(self._createMagnifierIcon())
        self.btnMagnifier.setToolTip(self.tr("Magnifier: Inspect pixels in detail"))
        self.btnMagnifier.setCheckable(True)
        self.btnMagnifier.setFixedSize(btn_size)
        self.btnMagnifier.setStyleSheet(_Style.BUTTON)
        self.btnMagnifier.clicked.connect(
            lambda: self._viewModel.setActiveTool(ActiveTool.MAGNIFIER)
        )
        self._toolButtonGroup.addButton(self.btnMagnifier)
        layout.addWidget(self.btnMagnifier)

    def _createZoomButtons(self, layout: QHBoxLayout) -> None:
        """Adds a vertical separator and the three zoom buttons."""
        btn_size = QSize(36, 36)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet(_Style.DIVIDER)
        sep.setFixedHeight(28)
        layout.addWidget(sep)

        self.btnZoomIn = QToolButton()
        self.btnZoomIn.setText("+")
        self.btnZoomIn.setToolTip(self.tr("Zoom In"))
        self.btnZoomIn.setFixedSize(btn_size)
        self.btnZoomIn.setStyleSheet(_Style.ZOOM_IN)
        self.btnZoomIn.clicked.connect(self._viewModel.zoomIn)
        layout.addWidget(self.btnZoomIn)

        self.btnZoomReset = QToolButton()
        self.btnZoomReset.setText("1x")
        self.btnZoomReset.setToolTip(self.tr("Reset Zoom (1:1)"))
        self.btnZoomReset.setFixedSize(btn_size)
        self.btnZoomReset.setStyleSheet(_Style.BUTTON)
        self.btnZoomReset.clicked.connect(self._viewModel.resetZoom)
        layout.addWidget(self.btnZoomReset)

        self.btnZoomOut = QToolButton()
        self.btnZoomOut.setText("-")
        self.btnZoomOut.setToolTip(self.tr("Zoom Out"))
        self.btnZoomOut.setFixedSize(btn_size)
        self.btnZoomOut.setStyleSheet(_Style.ZOOM_OUT)
        self.btnZoomOut.clicked.connect(self._viewModel.zoomOut)
        layout.addWidget(self.btnZoomOut)

    def _createHDULabel(self, layout: QHBoxLayout) -> None:
        layout.addStretch()
        self.selectedHDULabel = QLabel()
        self.selectedHDULabel.setStyleSheet(_Style.HDU_LABEL)
        layout.addWidget(self.selectedHDULabel)

    def _createMagnifierIcon(self) -> QIcon:
        """Creates a magnifier icon from theme or painted fallback."""
        icon = QIcon.fromTheme("edit-find")
        if not icon.isNull():
            return icon

        pixmap = QPixmap(40, 40)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPixelSize(24)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "\U0001f50d")
        painter.end()
        return QIcon(pixmap)

    def _createBoxSelectIcon(self) -> QIcon:
        """Creates a dashed rectangle icon for the Box Select tool."""
        size = 40
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        margin = 8
        painter.drawRect(margin, margin, size - 2 * margin, size - 2 * margin)
        handle = 4
        corners = [
            (margin, margin),
            (size - margin, margin),
            (margin, size - margin),
            (size - margin, size - margin),
        ]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        for cx, cy in corners:
            painter.drawRect(cx - handle // 2, cy - handle // 2, handle, handle)
        painter.end()
        return QIcon(pixmap)

    def setZoomControlsEnabled(self, enabled: bool) -> None:
        """Enables or disables zoom buttons during a zoom transform."""
        self.btnZoomIn.setEnabled(enabled)
        self.btnZoomReset.setEnabled(enabled)
        self.btnZoomOut.setEnabled(enabled)

    def _bindViewModel(self) -> None:
        def on_active_tool_changed():
            QMetaObject.invokeMethod(self, "_updateToolButtons", Qt.AutoConnection)

        def on_active_hdu_changed():
            QMetaObject.invokeMethod(self, "_updateHDULabel", Qt.AutoConnection)

        self._viewModel.add_active_tool_changed_callback(on_active_tool_changed)
        self._viewModel.add_active_hdu_changed_callback(on_active_hdu_changed)

    @Slot()
    def _updateToolButtons(self) -> None:
        tool = self._viewModel.activeTool
        self.btnMagnifier.setChecked(tool == ActiveTool.MAGNIFIER)
        self.btnBoxSelect.setChecked(tool == ActiveTool.BOX_SELECT)

    @Slot()
    def _updateHDULabel(self) -> None:
        label = self._viewModel.activeHDULabel
        self.selectedHDULabel.setText(self.tr(label) if label else "")
