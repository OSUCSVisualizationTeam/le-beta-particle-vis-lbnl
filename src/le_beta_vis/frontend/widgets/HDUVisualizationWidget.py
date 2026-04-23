from typing import Optional

from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .CaptureGraphicsView import CaptureGraphicsView
from .HDUVisualizationHUDWidget import HDUVisualizationHUDWidget


class HDUVisualizationWidget(QWidget):
    """Container for the HDU visualization area.

    Hosts the top toolbar, the main CaptureGraphicsView, and the status
    bar. The graphics view lives inside a stack host so that
    :class:`HDUVisualizationHUDWidget` can be drawn on top of it in
    widget space.

    Callers add their toolbar/status-bar widgets via ``contentLayout``
    and register the main view via :meth:`addSourceView`.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._contentLayout = QVBoxLayout(self)
        self._contentLayout.setContentsMargins(0, 0, 0, 0)
        self._contentLayout.setSpacing(0)

        self._stackHost: Optional[QWidget] = None
        self._sourceView: Optional[CaptureGraphicsView] = None
        self._hudWidget: Optional[HDUVisualizationHUDWidget] = None

    @property
    def contentLayout(self) -> QVBoxLayout:
        """Vertical layout for toolbar / graphics view / status bar."""
        return self._contentLayout

    @property
    def hudWidget(self) -> Optional[HDUVisualizationHUDWidget]:
        """The HUD overlay, available after :meth:`addSourceView`."""
        return self._hudWidget

    def addSourceView(self, view: CaptureGraphicsView) -> None:
        """Installs the main graphics view with a HUD stacked on top.

        Adds a stretch-1 stack host to ``contentLayout`` at the current
        end, places ``view`` inside it, then parents an
        :class:`HDUVisualizationHUDWidget` to the stack host.
        """
        if self._sourceView is not None:
            raise RuntimeError("addSourceView called twice")

        self._stackHost = _StackHost()
        self._sourceView = view
        view.setParent(self._stackHost)
        view.setGeometry(self._stackHost.rect())

        self._hudWidget = HDUVisualizationHUDWidget(view, self._stackHost)
        self._hudWidget.setGeometry(self._stackHost.rect())
        self._hudWidget.raise_()

        self._stackHost.bindOverlays(view, self._hudWidget)
        self._contentLayout.addWidget(self._stackHost, 1)


class _StackHost(QWidget):
    """Parent widget that keeps two stacked children at the same geometry."""

    def __init__(self) -> None:
        super().__init__()
        self._primary: Optional[QWidget] = None
        self._overlay: Optional[QWidget] = None

    def bindOverlays(self, primary: QWidget, overlay: QWidget) -> None:
        self._primary = primary
        self._overlay = overlay
        self._resync()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._resync()

    def _resync(self) -> None:
        if self._primary is not None:
            self._primary.setGeometry(self.rect())
        if self._overlay is not None:
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
