from dataclasses import dataclass

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QListView

from le_beta_vis.frontend.widgets.event_grid._EventGridSectionGrouping import (
    SectionInfo,
)
from le_beta_vis.frontend.widgets.event_grid._EventGridSectionHeaderWidget import (
    EventGridSectionHeaderWidget,
)


@dataclass
class _SectionRow:
    """Internal bookkeeping for one section in the grid."""

    info: SectionInfo
    header_widget: EventGridSectionHeaderWidget
    list_view: QListView
    model: QStandardItemModel
