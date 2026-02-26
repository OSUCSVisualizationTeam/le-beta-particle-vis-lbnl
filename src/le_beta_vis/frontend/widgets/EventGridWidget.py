from typing import List, Optional

from PySide6.QtCore import (
    QModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QScroller,
    QScrollerProperties,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ParticleType import (
    CLASSIFICATION_THRESHOLD,
    classify_particle,
)
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManager,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap
from le_beta_vis.frontend.widgets.EnergyClusterWidget import (
    EnergyClusterWidget,
)

CLUSTER_ROLE = Qt.UserRole + 1
THUMBNAIL_ROLE = Qt.UserRole + 2


class _EventItemDelegate(QStyledItemDelegate):
    """Paints grid items with thumbnail + badge overlays."""

    BADGE_FONT_SIZE = 9
    BADGE_RADIUS = 4
    BADGE_PAD_X = 4
    BADGE_PAD_Y = 2
    BORDER_WIDTH = 2

    def __init__(
        self,
        item_width: int = 140,
        item_height: int = 160,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._item_width = item_width
        self._item_height = item_height
        self._threshold: float = CLASSIFICATION_THRESHOLD
        self._physics: Optional[PhysicsConversionManager] = None
        self._displayKeV: bool = True

    def setItemSize(self, width: int, height: int) -> None:
        """Updates the item dimensions used for sizeHint."""
        self._item_width = width
        self._item_height = height

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        rect = option.rect

        # Background
        painter.fillRect(rect, QColor("#1e1e1e"))

        # Selection border
        is_selected = bool(
            option.state & QStyle.StateFlag.State_Selected
        )
        if is_selected:
            pen = QPen(QColor("#0078d7"), self.BORDER_WIDTH)
        else:
            pen = QPen(QColor("#555555"), 1)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        # Thumbnail
        pixmap = index.data(THUMBNAIL_ROLE)
        if pixmap and not pixmap.isNull():
            thumb_rect = QRect(
                rect.x() + self.BORDER_WIDTH,
                rect.y() + self.BORDER_WIDTH,
                rect.width() - 2 * self.BORDER_WIDTH,
                rect.width() - 2 * self.BORDER_WIDTH,
            )
            painter.drawPixmap(thumb_rect, pixmap)
            badge_area = thumb_rect
        else:
            badge_area = rect

        # Cluster data for badges
        cluster = index.data(CLUSTER_ROLE)
        if cluster is not None:
            particle_type, confidence = classify_particle(
                cluster, self._threshold
            )
            self._draw_particle_badge(
                painter, badge_area, particle_type
            )
            self._draw_confidence_badge(
                painter, badge_area, confidence
            )
            self._draw_energy_label(
                painter, rect, cluster.energy
            )

        painter.restore()

    def _draw_particle_badge(
        self, painter: QPainter, area: QRect, particle_type
    ) -> None:
        """Draws the particle type symbol badge (top-left)."""
        font = QFont()
        font.setPointSize(self.BADGE_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        text = particle_type.symbol
        text_w = fm.horizontalAdvance(text)
        text_h = fm.height()

        badge_w = text_w + 2 * self.BADGE_PAD_X
        badge_h = text_h + 2 * self.BADGE_PAD_Y
        x = area.x() + 4
        y = area.y() + 4

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(particle_type.badge_color)))
        painter.drawRoundedRect(
            x, y, badge_w, badge_h,
            self.BADGE_RADIUS, self.BADGE_RADIUS,
        )

        painter.setPen(QColor("white"))
        painter.drawText(
            x + self.BADGE_PAD_X,
            y + self.BADGE_PAD_Y + fm.ascent(),
            text,
        )

    def _draw_confidence_badge(
        self, painter: QPainter, area: QRect, confidence: float
    ) -> None:
        """Draws the confidence % badge (top-right)."""
        font = QFont()
        font.setPointSize(self.BADGE_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        text = f"{confidence * 100:.0f}%"
        text_w = fm.horizontalAdvance(text)
        text_h = fm.height()

        badge_w = text_w + 2 * self.BADGE_PAD_X
        badge_h = text_h + 2 * self.BADGE_PAD_Y
        x = area.right() - badge_w - 4
        y = area.y() + 4

        threshold = self._threshold
        bg_color = (
            QColor("#2ecc71") if confidence >= threshold
            else QColor("#f39c12") if confidence >= 0.5
            else QColor("#95a5a6")
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(
            x, y, badge_w, badge_h,
            self.BADGE_RADIUS, self.BADGE_RADIUS,
        )

        text_color = (
            QColor("white") if confidence >= threshold
            else QColor("#fff3cd") if confidence >= 0.5
            else QColor("white")
        )
        painter.setPen(text_color)
        painter.drawText(
            x + self.BADGE_PAD_X,
            y + self.BADGE_PAD_Y + fm.ascent(),
            text,
        )

    def _draw_energy_label(
        self, painter: QPainter, rect: QRect, energy: float
    ) -> None:
        """Draws a compact energy label at the bottom."""
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#cccccc"))
        if self._physics and self._displayKeV:
            energy_kev = self._physics.adu_to_kev(energy)
            text = f"E={energy_kev:.4f} keV"
        else:
            text = f"E={energy:.0f} ADU"
        painter.drawText(
            rect.x() + 4,
            rect.bottom() - 4,
            text,
        )

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        return QSize(self._item_width, self._item_height)


class EventGridWidget(QWidget):
    """Displays cluster events as a responsive grid of thumbnails.

    Each cell shows a cluster thumbnail with particle type badge
    (top-left) and confidence percentage (top-right).  The grid
    re-flows when the window is resized.

    Signals:
        eventSelected(int): Emitted when a grid item is clicked.
    """

    eventSelected = Signal(int)

    def __init__(
        self,
        item_width: int = 140,
        item_height: int = 160,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._item_width = item_width
        self._item_height = item_height
        self._colormap: Optional[Colormap] = None
        self._initUI()

    def _initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._listView = self._buildListView()
        layout.addWidget(self._listView)
        self._configureKineticScrolling(self._listView.viewport())

    def _buildListView(self) -> QListView:
        """Creates and configures the grid's QListView."""
        self._model = QStandardItemModel()
        self._delegate = _EventItemDelegate(
            self._item_width, self._item_height, self,
        )

        view = QListView()
        view.setModel(self._model)
        view.setItemDelegate(self._delegate)
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        view.setGridSize(
            QSize(self._item_width, self._item_height)
        )
        view.setUniformItemSizes(True)
        view.setSpacing(4)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet("background-color: #2d2d2d;")
        view.clicked.connect(self._onItemClicked)
        return view

    def _configureKineticScrolling(
        self, viewport: QWidget
    ) -> None:
        """Sets up touch-style kinetic scrolling on *viewport*."""
        QScroller.grabGesture(
            viewport, QScroller.LeftMouseButtonGesture,
        )
        scroller = QScroller.scroller(viewport)
        props = scroller.scrollerProperties()
        props.setScrollMetric(
            QScrollerProperties.AxisLockThreshold, 0.6
        )
        props.setScrollMetric(
            QScrollerProperties.HorizontalOvershootPolicy,
            QScrollerProperties.OvershootAlwaysOff,
        )
        props.setScrollMetric(
            QScrollerProperties.VerticalOvershootPolicy,
            QScrollerProperties.OvershootAlwaysOff,
        )
        scroller.setScrollerProperties(props)

    def setGridSize(self, width: int, height: int) -> None:
        """Updates the grid cell dimensions from configuration.

        Args:
            width: Cell width in pixels.
            height: Cell height in pixels.
        """
        self._item_width = width
        self._item_height = height
        self._listView.setGridSize(QSize(width, height))
        self._delegate.setItemSize(width, height)

    def setColormap(self, colormap: Optional[Colormap]) -> None:
        """Sets the colormap used for thumbnail rendering.

        Args:
            colormap: Colormap enum or None for grayscale.
        """
        self._colormap = colormap

    def setPhysicsManager(
        self, manager: PhysicsConversionManager
    ) -> None:
        """Sets the physics conversion manager for keV display.

        Args:
            manager: The conversion manager to use.
        """
        self._delegate._physics = manager

    def setDisplayEnergyInKev(self, enabled: bool) -> None:
        """Sets whether energy labels use keV or ADU.

        Args:
            enabled: True for keV display, False for raw ADU.
        """
        self._delegate._displayKeV = enabled

    def setClassificationThreshold(
        self, threshold: float
    ) -> None:
        """Sets the confidence threshold for classification badges.

        Args:
            threshold: Min confidence for positive classification.
        """
        self._delegate._threshold = threshold

    def setColumnConstraints(
        self, default_cols: int, max_cols: int
    ) -> None:
        """Sets minimum/maximum width based on column counts.

        Constrains the grid width so it displays *default_cols*
        columns by default and never exceeds *max_cols* columns,
        keeping the grid narrow and leaving space for the inspector.

        Args:
            default_cols: Number of columns visible by default.
            max_cols: Maximum number of visible columns.
        """
        grid_w = self._listView.gridSize().width()
        spacing = self._listView.spacing()
        self.setMinimumWidth(
            default_cols * (grid_w + spacing)
        )
        self.setMaximumWidth(
            max_cols * (grid_w + spacing)
        )

    def setEvents(self, events: List[Cluster]) -> None:
        """Populates the grid with cluster events.

        Args:
            events: List of Cluster objects to display.
        """
        self._model.clear()
        for cluster in events:
            item = QStandardItem()
            item.setData(cluster, CLUSTER_ROLE)
            item.setData(
                self._make_thumbnail(cluster), THUMBNAIL_ROLE
            )
            item.setEditable(False)
            self._model.appendRow(item)

    def setSelectedIndex(self, index: int) -> None:
        """Programmatically selects a grid item.

        Args:
            index: Index to select, or -1 to clear selection.
        """
        if index < 0:
            self._listView.clearSelection()
        elif index < self._model.rowCount():
            model_index = self._model.index(index, 0)
            self._listView.setCurrentIndex(model_index)

    def clear(self) -> None:
        """Removes all items from the grid."""
        self._model.clear()

    def _make_thumbnail(self, cluster: Cluster) -> QPixmap:
        """Generates a QPixmap thumbnail from cluster data."""
        return EnergyClusterWidget.to_pixmap(
            cluster.data, colormap=self._colormap
        )

    def _onItemClicked(self, index: QModelIndex) -> None:
        self.eventSelected.emit(index.row())
