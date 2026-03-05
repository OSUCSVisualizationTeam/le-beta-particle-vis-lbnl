"""Settings dialog for editing application configuration.

Displays all configuration keys grouped by namespace with type-dispatched
input widgets.  Pending changes are tracked in the SettingsViewModel and
only written to disk on Apply.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.SettingsViewModel import SettingsViewModel


class _Style:
    DIALOG = "background-color: #2d2d2d; color: #eeeeee;"
    GROUP_BOX = (
        "QGroupBox {"
        "  color: #eeeeee;"
        "  font-weight: bold;"
        "  font-size: 13px;"
        "  border: 1px solid #555555;"
        "  border-radius: 4px;"
        "  margin-top: 12px;"
        "  padding-top: 16px;"
        "}"
        "QGroupBox::title {"
        "  subcontrol-origin: margin;"
        "  left: 10px;"
        "  padding: 0 4px;"
        "}"
    )
    SUBGROUP_HEADER = (
        "color: #0078d7;"
        "font-weight: bold;"
        "font-size: 12px;"
        "padding-top: 6px;"
    )
    LABEL = "color: #cccccc; font-size: 12px;"
    DESC_LABEL = "color: #888888; font-size: 10px;"
    INPUT = (
        "QLineEdit, QSpinBox, QDoubleSpinBox {"
        "  background-color: #3d3d3d;"
        "  color: #eeeeee;"
        "  border: 1px solid #555555;"
        "  border-radius: 3px;"
        "  padding: 3px;"
        "}"
        "QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {"
        "  border: 1px solid #0078d7;"
        "}"
    )
    CHECKBOX = (
        "QCheckBox {"
        "  color: #eeeeee;"
        "  spacing: 6px;"
        "}"
        "QCheckBox::indicator {"
        "  width: 16px;"
        "  height: 16px;"
        "}"
    )
    FILTER_INPUT = (
        "QLineEdit {"
        "  background-color: #3d3d3d;"
        "  color: #eeeeee;"
        "  border: 1px solid #555555;"
        "  border-radius: 3px;"
        "  padding: 5px;"
        "  font-size: 12px;"
        "}"
        "QLineEdit:focus {"
        "  border: 1px solid #0078d7;"
        "}"
    )
    APPLY_BTN = (
        "QPushButton {"
        "  background-color: #0078d7;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "  padding: 6px 16px;"
        "  font-weight: bold;"
        "}"
        "QPushButton:hover {"
        "  background-color: #005fa3;"
        "}"
    )
    CANCEL_BTN = (
        "QPushButton {"
        "  background-color: #3d3d3d;"
        "  color: #cccccc;"
        "  border: 1px solid #555555;"
        "  border-radius: 4px;"
        "  padding: 6px 16px;"
        "}"
        "QPushButton:hover {"
        "  background-color: #505050;"
        "}"
    )
    RESTORE_BTN = (
        "QPushButton {"
        "  background-color: #8b0000;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "  padding: 6px 16px;"
        "  font-weight: bold;"
        "}"
        "QPushButton:hover {"
        "  background-color: #a00000;"
        "}"
    )
    CLEAR_BTN = (
        "QPushButton {"
        "  background-color: #3d3d3d;"
        "  color: #cccccc;"
        "  border: 1px solid #555555;"
        "  border-radius: 4px;"
        "  padding: 5px 10px;"
        "}"
        "QPushButton:hover {"
        "  background-color: #505050;"
        "}"
    )


class SettingsDialog(QDialog):
    """Modal dialog for editing all application configuration keys.

    Groups settings by namespace, provides type-dispatched input widgets,
    text filtering, and Apply/Cancel/Restore Defaults actions.
    """

    _DEBOUNCE_MS = 200

    def __init__(
        self,
        viewModel: SettingsViewModel,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel
        self._debounce_timer_id: int = 0

        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumSize(600, 500)
        self.setStyleSheet(_Style.DIALOG)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        self._initUI()
        self._buildSettings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Filter bar
        filterRow = QHBoxLayout()
        self._filterEdit = QLineEdit()
        self._filterEdit.setPlaceholderText(self.tr("Filter settings..."))
        self._filterEdit.setClearButtonEnabled(True)
        self._filterEdit.setStyleSheet(_Style.FILTER_INPUT)
        self._filterEdit.textChanged.connect(self._onFilterTextChanged)
        filterRow.addWidget(self._filterEdit)

        clearBtn = QPushButton(self.tr("Clear"))
        clearBtn.setStyleSheet(_Style.CLEAR_BTN)
        clearBtn.clicked.connect(self._onClearFilter)
        filterRow.addWidget(clearBtn)
        root.addLayout(filterRow)

        # Scroll area
        self._scrollArea = QScrollArea()
        self._scrollArea.setWidgetResizable(True)
        self._scrollArea.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(self._scrollArea, stretch=1)

        # Button row
        btnRow = QHBoxLayout()
        restoreBtn = QPushButton(self.tr("Restore Defaults"))
        restoreBtn.setStyleSheet(_Style.RESTORE_BTN)
        restoreBtn.clicked.connect(self._onRestoreDefaults)
        btnRow.addWidget(restoreBtn)

        btnRow.addStretch()

        cancelBtn = QPushButton(self.tr("Cancel"))
        cancelBtn.setStyleSheet(_Style.CANCEL_BTN)
        cancelBtn.clicked.connect(self._onCancel)
        btnRow.addWidget(cancelBtn)

        applyBtn = QPushButton(self.tr("Apply"))
        applyBtn.setStyleSheet(_Style.APPLY_BTN)
        applyBtn.clicked.connect(self._onApply)
        btnRow.addWidget(applyBtn)

        root.addLayout(btnRow)

    def _buildSettings(self) -> None:
        """Tear down and rebuild the scroll area content."""
        grouped = self._vm.filtered_grouped_settings()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(4)

        for group_name in sorted(grouped.keys()):
            subgroups = grouped[group_name]
            groupBox = QGroupBox(group_name)
            groupBox.setStyleSheet(_Style.GROUP_BOX)
            groupLayout = QVBoxLayout(groupBox)
            groupLayout.setSpacing(4)

            for sg_name in sorted(subgroups.keys()):
                entries = subgroups[sg_name]
                header = QLabel(sg_name)
                header.setStyleSheet(_Style.SUBGROUP_HEADER)
                groupLayout.addWidget(header)

                form = QFormLayout()
                form.setLabelAlignment(Qt.AlignRight)
                form.setSpacing(6)

                for entry in entries:
                    key, label, type_str, value, _default, desc, choices = entry
                    row = self._createInputWidget(
                        key, type_str, value, choices
                    )
                    labelWidget = QLabel(label)
                    labelWidget.setStyleSheet(_Style.LABEL)

                    container = QVBoxLayout()
                    container.setSpacing(2)
                    container.addWidget(row)
                    if desc:
                        descLabel = QLabel(desc)
                        descLabel.setStyleSheet(_Style.DESC_LABEL)
                        descLabel.setWordWrap(True)
                        container.addWidget(descLabel)

                    form.addRow(labelWidget, container)

                groupLayout.addLayout(form)

            layout.addWidget(groupBox)

        layout.addStretch()
        self._scrollArea.setWidget(content)

    def _createInputWidget(
        self, key: str, type_str: str, value, choices: list = None
    ) -> QWidget:
        """Return a type-dispatched input widget for *key*."""
        if type_str == "bool":
            cb = QCheckBox()
            cb.setStyleSheet(_Style.CHECKBOX)
            cb.setChecked(bool(value))
            cb.toggled.connect(
                lambda checked, k=key: self._vm.set_pending(k, checked),
            )
            return cb

        if type_str == "enum":
            combo = QComboBox()
            combo.setStyleSheet(_Style.INPUT)
            if choices:
                combo.addItems([str(c) for c in choices])
            if value is not None:
                combo.setCurrentText(str(value))
            combo.currentTextChanged.connect(
                lambda text, k=key: self._vm.set_pending(k, text),
            )
            return combo

        if type_str == "int":
            spin = QSpinBox()
            spin.setStyleSheet(_Style.INPUT)
            spin.setRange(-999999, 999999)
            spin.setValue(int(value) if value is not None else 0)
            spin.valueChanged.connect(
                lambda v, k=key: self._vm.set_pending(k, v),
            )
            return spin

        if type_str == "float":
            spin = QDoubleSpinBox()
            spin.setStyleSheet(_Style.INPUT)
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(4)
            spin.setValue(float(value) if value is not None else 0.0)
            spin.valueChanged.connect(
                lambda v, k=key: self._vm.set_pending(k, v),
            )
            return spin

        if type_str in ("directory_path", "file_path"):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            
            edit = QLineEdit()
            edit.setStyleSheet(_Style.INPUT)
            edit.setText(str(value) if value is not None else "")
            edit.textChanged.connect(
                lambda text, k=key: self._vm.set_pending(k, text),
            )
            layout.addWidget(edit, stretch=1)
            
            browseBtn = QPushButton(self.tr("Browse..."))
            # Re-use clear button style for a small neutral button
            browseBtn.setStyleSheet(_Style.CLEAR_BTN)
            
            def browse(checked=False, edit_widget=edit, t=type_str):
                current_path = edit_widget.text()
                if t == "directory_path":
                    path = QFileDialog.getExistingDirectory(self, self.tr("Select Directory"), current_path)
                else:
                    path, _ = QFileDialog.getOpenFileName(self, self.tr("Select File"), current_path)
                if path:
                    edit_widget.setText(path)
                    
            browseBtn.clicked.connect(browse)
            layout.addWidget(browseBtn)
            return container

        # Default: str
        edit = QLineEdit()
        edit.setStyleSheet(_Style.INPUT)
        edit.setText(str(value) if value is not None else "")
        if "password" in key.lower():
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.textChanged.connect(
            lambda text, k=key: self._vm.set_pending(k, text),
        )
        return edit

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _onFilterTextChanged(self, text: str) -> None:
        QTimer.singleShot(
            self._DEBOUNCE_MS,
            lambda: self._applyFilter(text),
        )

    def _applyFilter(self, text: str) -> None:
        if self._filterEdit.text() != text:
            return
        self._vm.filter(text)
        self._buildSettings()

    def _onClearFilter(self) -> None:
        self._filterEdit.clear()

    def _onCancel(self) -> None:
        self._vm.cancel()
        self.reject()

    def _onApply(self) -> None:
        reply = QMessageBox.question(
            self,
            self.tr("Apply Settings"),
            self.tr("Save all changes to the configuration file?"),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vm.apply()
            self.accept()

    def _onRestoreDefaults(self) -> None:
        reply = QMessageBox.warning(
            self,
            self.tr("Restore Defaults"),
            self.tr(
                "This will reset ALL settings to their default values. "
                "This action cannot be undone.\n\nContinue?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vm.restore_defaults()
            self._buildSettings()
