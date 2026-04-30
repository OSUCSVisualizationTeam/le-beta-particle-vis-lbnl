from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QScrollArea,
    QToolButton,
    QScroller,
    QScrollerProperties,
)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from ..theme import MosaicThumbnailColors
from ..viewmodels.MosaicViewModel import MosaicViewModel


class ThumbnailButton(QToolButton):
    """QToolButton that paints an 'HDU N' label overlay on the icon."""

    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        self._index = index

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        label = f"HDU {self._index}"
        font = QFont()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        padding = 2
        bg_rect = QRect(
            2, 2,
            fm.horizontalAdvance(label) + 2 * padding,
            fm.height() + padding,
        )
        r, g, b, a = MosaicThumbnailColors.LABEL_BACKGROUND_RGBA
        painter.fillRect(bg_rect, QColor(r, g, b, a))
        color_hex = (
            MosaicThumbnailColors.LABEL_TEXT_SELECTED
            if self.isChecked()
            else MosaicThumbnailColors.LABEL_TEXT
        )
        painter.setPen(QColor(color_hex))
        painter.drawText(bg_rect, Qt.AlignCenter, label)
        painter.end()


class MosaicView(QWidget):
    """
    Displays a horizontal strip of HDU thumbnails.
    """

    MIN_HEIGHT = 100

    def __init__(self, viewModel: MosaicViewModel):
        super().__init__()
        self.viewModel = viewModel
        self.buttons = []
        self.initUI()
        self.bindViewModel()

    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setStyleSheet(
            """
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QScrollBar:horizontal {
                height: 12px;
                background: transparent;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(100, 100, 100, 165);
                min-width: 30px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(150, 150, 150, 200);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            """
        )

        self.container = QWidget()
        self.container.setStyleSheet("background-color: #1e1e1e;")
        self.containerLayout = QHBoxLayout(self.container)
        self.containerLayout.setContentsMargins(5, 5, 5, 5)  # Top/Bottom margins
        self.containerLayout.setSpacing(10)
        self.containerLayout.setAlignment(Qt.AlignLeft)

        self.scrollArea.setWidget(self.container)
        layout.addWidget(self.scrollArea)

        # Enable Drag-to-Scroll (Kinetic Scrolling)
        QScroller.grabGesture(
            self.scrollArea.viewport(), QScroller.LeftMouseButtonGesture
        )

        # Lock to Horizontal Axis and disable overshoot/bounce
        scroller = QScroller.scroller(self.scrollArea.viewport())
        props = scroller.scrollerProperties()
        props.setScrollMetric(QScrollerProperties.AxisLockThreshold, 0.6)
        props.setScrollMetric(
            QScrollerProperties.HorizontalOvershootPolicy,
            QScrollerProperties.OvershootAlwaysOff,
        )
        props.setScrollMetric(
            QScrollerProperties.VerticalOvershootPolicy,
            QScrollerProperties.OvershootAlwaysOff,
        )
        scroller.setScrollerProperties(props)

        # Initial height calculation
        self.updateGeometryConstraints()

    def updateGeometryConstraints(self):
        """Calculates and sets the fixed height based on content + scrollbar."""
        thumb_h = self.viewModel.thumbnailHeight

        # Button height = thumb_h + 10 (padding; label is overlaid on icon)
        # Container margins = 5 top + 5 bottom = 10
        # Scrollbar height = 12
        total_h = (thumb_h + 10) + 10 + 12
        total_h = max(total_h, self.MIN_HEIGHT)

        self.setFixedHeight(total_h)

    def bindViewModel(self):
        self.viewModel.add_thumbnails_changed_callback(self.refreshThumbnails)
        self.viewModel.add_selection_changed_callback(self.updateSelection)

    def refreshThumbnails(self):
        # Recalculate height in case config changed
        self.updateGeometryConstraints()

        # Clear existing
        for btn in self.buttons:
            self.containerLayout.removeWidget(btn)
            btn.deleteLater()
        self.buttons = []

        target_h = self.viewModel.thumbnailHeight
        btn_padding = 10  # Extra width for button borders/padding

        # Add new
        for i, buffer in enumerate(self.viewModel.thumbnails):
            # Convert NumPy Buffer -> QImage -> QPixmap
            height, width = buffer.shape
            q_img = QImage(buffer.data, width, height, width, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_img.copy())

            btn = ThumbnailButton(i)
            btn.setIcon(QIcon(pixmap))
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

            # Calculate aspect ratio
            if height > 0:
                aspect = width / height
            else:
                aspect = 1.0

            target_w = int(target_h * aspect)

            # Set Icon Size (Actual Image)
            btn.setIconSize(QSize(target_w, target_h))

            btn.setFixedSize(target_w + btn_padding, target_h + btn_padding)

            btn.setCheckable(True)
            btn.setAutoExclusive(True)  # Only one can be checked
            btn.setStyleSheet(
                """
                QToolButton {
                    background-color: #333;
                    color: #ccc;
                    border: 1px solid #555;
                    border-radius: 4px;
                    font-size: 10px;
                }
                QToolButton:checked {
                    background-color: #444;
                    border: 2px solid #0078d7;
                }
                QToolButton:hover {
                    border: 1px solid #888;
                }
            """
            )

            # Use lambda with default arg to capture 'i' correctly
            btn.clicked.connect(lambda checked, idx=i: self.viewModel.selectIndex(idx))

            self.containerLayout.addWidget(btn)
            self.buttons.append(btn)

        # Set initial selection if any
        if self.viewModel.selectedIndex >= 0 and self.viewModel.selectedIndex < len(
            self.buttons
        ):
            self.buttons[self.viewModel.selectedIndex].setChecked(True)

    def updateSelection(self, index: int):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
