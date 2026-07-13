"""Export options dialog shown between the file picker and export start.

Stateless view — no ViewModel. Opens, collects the user's PNG opt-in
choice, and returns it. All strings pass through tr().
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class ExportOptionsDialog(QDialog):
    """Modal dialog for choosing whether to embed cluster card PNGs.

    Does not hold state between invocations. Use :meth:`ask` for a
    one-shot convenience wrapper.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._include_pngs: bool = False
        self.setWindowTitle(self.tr("Export Options"))
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._initUI()

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)
        self._buildRadioGroup(root)
        root.addStretch()
        self._buildButtonRow(root)

    def _buildRadioGroup(self, layout: QVBoxLayout) -> None:
        self._btnGroup = QButtonGroup(self)
        self._btnGroup.setExclusive(True)

        self._radioDataOnly = QRadioButton(self.tr("Export data only"))
        self._radioDataOnly.setChecked(True)
        layout.addWidget(self._radioDataOnly)
        self._btnGroup.addButton(self._radioDataOnly)

        self._radioWithCards = QRadioButton(self.tr("Include cluster cards (PNG)"))
        layout.addWidget(self._radioWithCards)
        self._btnGroup.addButton(self._radioWithCards)

        note = QLabel(
            self.tr(
                "Note: The .h5 file and cluster card PNGs will be packed into a "
                "single .zip archive. The archive may be larger than a data-only export."
            )
        )
        note.setWordWrap(True)
        note.setObjectName("exportOptionsNote")
        layout.addWidget(note)

    def _buildButtonRow(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.addStretch()

        cancelBtn = QPushButton(self.tr("Cancel"))
        cancelBtn.setProperty("styleRole", "secondary")
        cancelBtn.clicked.connect(self.reject)
        row.addWidget(cancelBtn)

        exportBtn = QPushButton(self.tr("Export"))
        exportBtn.setProperty("styleRole", "primary")
        exportBtn.clicked.connect(self._onExportClicked)
        row.addWidget(exportBtn)

        layout.addLayout(row)

    def _onExportClicked(self) -> None:
        self._include_pngs = self._radioWithCards.isChecked()
        self.accept()

    @property
    def include_pngs(self) -> bool:
        """True if the user selected "Include cluster cards (PNG)"."""
        return self._include_pngs

    @staticmethod
    def ask(parent: Optional[QWidget] = None) -> Optional[bool]:
        """Show the dialog and return the user's choice.

        Returns:
            ``True``  — Export with cluster cards (PNG) selected
            ``False`` — Export data only selected
            ``None``  — Dialog was cancelled (Cancel button or window close)
        """
        dlg = ExportOptionsDialog(parent)
        if dlg.exec() == QDialog.Accepted:
            return dlg.include_pngs
        return None
