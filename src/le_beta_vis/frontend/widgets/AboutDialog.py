"""About dialog showing application metadata."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.AboutViewModel import AboutViewModel
from ..theme import (
    COLOR_BACKGROUND_SURFACE,
    COLOR_TEXT_PRIMARY,
    COLOR_ACCENT_LINK,
)

_ICON_SIZE = 80


def _resolve_icon_path() -> Path:
    """Return the application icon path for both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "resources" / "icons" / "lbnl-logo.png"


class AboutDialog(QDialog):
    """Modal dialog displaying application metadata."""

    def __init__(
        self,
        viewModel: AboutViewModel,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel

        self.setWindowTitle(self.tr("About {0}").format(self._vm.app_name))
        self.setFixedSize(420, 340)
        self.setStyleSheet(
            f"background-color: {COLOR_BACKGROUND_SURFACE};"
            f" color: {COLOR_TEXT_PRIMARY};"
        )
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        self._initUI()

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        self._buildHeader(root)
        self._buildSeparator(root)
        self._buildDetails(root)
        self._buildRepoLink(root)
        self._buildButtonBox(root)

    def _buildHeader(self, layout: QVBoxLayout) -> None:
        """Icon + title/version row."""
        row = QHBoxLayout()
        row.setSpacing(16)

        iconLabel = QLabel()
        icon_path = _resolve_icon_path()
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(
                _ICON_SIZE,
                _ICON_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            iconLabel.setPixmap(pixmap)
        iconLabel.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        row.addWidget(iconLabel)

        titleStack = QVBoxLayout()
        titleStack.setSpacing(4)

        nameLabel = QLabel(self._vm.app_name)
        nameLabel.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY};"
            " font-size: 18px;"
            " font-weight: bold;"
        )
        titleStack.addWidget(nameLabel)

        versionLabel = QLabel(self._vm.formatted_version())
        versionLabel.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px;"
        )
        titleStack.addWidget(versionLabel)
        titleStack.addStretch()

        row.addLayout(titleStack)
        row.addStretch()
        layout.addLayout(row)

    def _buildSeparator(self, layout: QVBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #555555;")
        layout.addWidget(sep)

    def _buildDetails(self, layout: QVBoxLayout) -> None:
        """Form layout with metadata fields."""
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(6)

        entries = [
            (self.tr("Authors"), self._vm.authors),
            (self.tr("Year"), self._vm.year),
            (self.tr("Organization"), self._vm.organization),
            (self.tr("Developed for"), self._vm.developed_for),
        ]
        for label_text, value_text in entries:
            label = QLabel(label_text)
            label.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY};"
                " font-weight: bold;"
                " font-size: 12px;"
            )
            value = QLabel(value_text)
            value.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px;"
            )
            form.addRow(label, value)

        copyright_label = QLabel(self._vm.copyright_line())
        copyright_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px;"
        )
        copyright_label.setAlignment(Qt.AlignCenter)
        form.addRow(copyright_label)

        layout.addLayout(form)

    def _buildRepoLink(self, layout: QVBoxLayout) -> None:
        url = self._vm.repository_url
        link = QLabel(
            f'<a href="{url}" style="color: {COLOR_ACCENT_LINK};">{url}</a>'
        )
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignCenter)
        link.setStyleSheet("font-size: 11px;")
        layout.addWidget(link)

    def _buildButtonBox(self, layout: QVBoxLayout) -> None:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(
            "QPushButton {"
            f"  background-color: #3d3d3d;"
            f"  color: {COLOR_TEXT_PRIMARY};"
            "  border: 1px solid #555555;"
            "  border-radius: 4px;"
            "  padding: 6px 16px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #505050;"
            "}"
        )
        layout.addWidget(buttons)
