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
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.AboutViewModel import AboutViewModel
from ..viewmodels.LicensesViewModel import LicensesViewModel
from ..theme import COLOR_ACCENT_LINK

_ICON_SIZE = 80


def _resolve_icon_path() -> Path:
    """Return the application icon path for both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "resources" / "icons" / "lbnl-logo.png"


class AboutDialog(QDialog):
    """Modal dialog displaying application metadata."""

    def __init__(
        self,
        viewModel: AboutViewModel,
        licensesViewModel: LicensesViewModel = None,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._licenses_vm = licensesViewModel or LicensesViewModel()

        self.setWindowTitle(self.tr("About {0}").format(self._vm.app_name))
        self.setFixedSize(480, 440)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        self._initUI()

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._buildAboutTab(), self.tr("About"))
        tabs.addTab(self._buildLicensesTab(), self.tr("Licenses"))
        root.addWidget(tabs)

        self._buildButtonBox(root)

    def _buildAboutTab(self) -> QWidget:
        """About tab — existing application metadata content, unchanged."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._buildHeader(layout)
        self._buildSeparator(layout)
        self._buildDetails(layout)
        self._buildRepoLink(layout)
        layout.addStretch()

        return page

    def _buildLicensesTab(self) -> QWidget:
        """Licenses tab — MIT license and third-party notices, scrollable."""
        browser = QTextBrowser()
        browser.setReadOnly(True)
        # LicensesViewModel.third_party_notices_text already rewrites
        # THIRD_PARTY_NOTICES.md's repo-relative links to absolute GitHub
        # URLs (see LicenseDocuments._rewrite_relative_links), so every link
        # this browser ever renders is external — safe to hand off to
        # QDesktopServices rather than navigating within the dialog.
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(self._composeLicensesMarkdown())
        return browser

    def _composeLicensesMarkdown(self) -> str:
        """Combine LICENSE and THIRD_PARTY_NOTICES.md into one markdown doc.

        LICENSE's paragraphs are already blank-line separated, so it reads
        correctly as plain markdown text and word-wraps in QTextBrowser; a
        fenced code block was tried first but disabled wrapping and forced
        an unwanted horizontal scrollbar.
        """
        return (
            "## MIT License\n\n"
            f"{self._licenses_vm.license_text}\n\n"
            "---\n\n"
            f"{self._licenses_vm.third_party_notices_text}"
        )

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
        nameLabel.setObjectName("aboutNameLabel")
        titleStack.addWidget(nameLabel)

        versionLabel = QLabel(self._vm.formatted_version())
        versionLabel.setObjectName("aboutVersionLabel")
        titleStack.addWidget(versionLabel)
        self._buildLicenseLink(titleStack)
        titleStack.addStretch()

        row.addLayout(titleStack)
        row.addStretch()
        layout.addLayout(row)

    def _buildSeparator(self, layout: QVBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
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
            label.setProperty("class", "aboutFieldName")
            value = QLabel(value_text)
            value.setProperty("class", "aboutFieldValue")
            form.addRow(label, value)

        copyright_label = QLabel(self._vm.copyright_line())
        copyright_label.setObjectName("aboutCopyrightLabel")
        copyright_label.setAlignment(Qt.AlignCenter)
        form.addRow(copyright_label)

        layout.addLayout(form)

    def _buildLicenseLink(self, layout: QVBoxLayout) -> None:
        url = self._vm.license_url
        link = QLabel(
            f'<a href="{url}" style="color: {COLOR_ACCENT_LINK};">'
            f'{self.tr("View License")}</a>'
        )
        link.setOpenExternalLinks(True)
        link.setObjectName("aboutLicenseLink")
        layout.addWidget(link)

    def _buildRepoLink(self, layout: QVBoxLayout) -> None:
        url = self._vm.repository_url
        link = QLabel(
            f'<a href="{url}" style="color: {COLOR_ACCENT_LINK};">{url}</a>'
        )
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignCenter)
        link.setObjectName("aboutRepoLink")
        layout.addWidget(link)

    def _buildButtonBox(self, layout: QVBoxLayout) -> None:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
