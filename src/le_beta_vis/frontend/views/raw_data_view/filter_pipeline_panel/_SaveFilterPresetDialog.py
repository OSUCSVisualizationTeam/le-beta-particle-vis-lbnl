"""Lightweight dialog for entering an annotation when saving a filter preset."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class _SaveFilterPresetDialog(QDialog):
    """Prompts the user for an optional annotation before saving a .rcfilt file.

    The annotation field is pre-filled by the caller (typically with a
    string produced by :func:`~le_beta_vis.frontend.viewmodels.FilterPresetService.compose_annotation`).
    The user may edit or clear it before confirming.
    """

    def __init__(self, annotation: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Save Filter Preset"))
        self.setMinimumWidth(420)
        self._annotation_edit = QLineEdit(annotation, self)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Annotation (optional):"), self))
        layout.addWidget(self._annotation_edit)
        layout.addWidget(buttons)

    @property
    def annotation(self) -> str:
        """The annotation string entered by the user."""
        return self._annotation_edit.text()
