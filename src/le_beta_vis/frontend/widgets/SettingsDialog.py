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
        self.setMinimumSize(700, 500)
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
        self._filterEdit.setObjectName("settingsFilterEdit")
        self._filterEdit.textChanged.connect(self._onFilterTextChanged)
        filterRow.addWidget(self._filterEdit)

        clearBtn = QPushButton(self.tr("Clear"))
        clearBtn.setObjectName("settingsClearButton")
        clearBtn.setProperty("styleRole", "secondary")
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
        restoreBtn.setProperty("styleRole", "destructive")
        restoreBtn.clicked.connect(self._onRestoreDefaults)
        btnRow.addWidget(restoreBtn)

        btnRow.addStretch()

        cancelBtn = QPushButton(self.tr("Cancel"))
        cancelBtn.setProperty("styleRole", "secondary")
        cancelBtn.clicked.connect(self._onCancel)
        btnRow.addWidget(cancelBtn)

        applyBtn = QPushButton(self.tr("Apply"))
        applyBtn.setProperty("styleRole", "primary")
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
            groupLayout = QVBoxLayout(groupBox)
            groupLayout.setSpacing(4)

            for sg_name in sorted(subgroups.keys()):
                entries = subgroups[sg_name]
                header = QLabel(sg_name)
                header.setProperty("class", "settingSubgroupHeader")
                groupLayout.addWidget(header)

                form = QFormLayout()
                form.setLabelAlignment(Qt.AlignRight)
                form.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
                )
                form.setSpacing(6)

                for entry in entries:
                    key, label, type_str, value, _default, desc, choices = entry
                    row = self._createInputWidget(
                        key, type_str, value, choices
                    )
                    labelWidget = QLabel(label)
                    labelWidget.setProperty("class", "settingFieldName")

                    wrapper = QWidget()
                    container = QVBoxLayout(wrapper)
                    container.setContentsMargins(0, 0, 0, 0)
                    container.setSpacing(2)
                    container.addWidget(row)
                    if desc:
                        descLabel = QLabel(desc)
                        descLabel.setProperty("class", "settingFieldDesc")
                        descLabel.setWordWrap(True)
                        container.addWidget(descLabel)

                    form.addRow(labelWidget, wrapper)

                groupLayout.addLayout(form)

            layout.addWidget(groupBox)

        layout.addStretch()
        self._scrollArea.setWidget(content)

    def _createInputWidget(
        self, key: str, type_str: str, value, choices: list = None
    ) -> QWidget:
        """Return a type-dispatched input widget for *key*."""
        if type_str == "bool":
            return self._createBoolWidget(key, value)
        if type_str == "enum":
            return self._createEnumWidget(key, value, choices)
        if type_str == "int":
            return self._createIntWidget(key, value)
        if type_str == "float":
            return self._createFloatWidget(key, value)
        if type_str in ("directory_path", "file_path"):
            return self._createPathWidget(key, value, type_str)
        return self._createStringWidget(key, value)

    def _createBoolWidget(self, key: str, value) -> QCheckBox:
        cb = QCheckBox()
        cb.setChecked(bool(value))
        cb.toggled.connect(
            lambda checked, k=key: self._vm.set_pending(k, checked),
        )
        return cb

    def _createEnumWidget(self, key: str, value, choices: list = None) -> QComboBox:
        combo = QComboBox()
        if choices:
            combo.addItems([str(c) for c in choices])
        if value is not None:
            combo.setCurrentText(str(value))
        combo.currentTextChanged.connect(
            lambda text, k=key: self._vm.set_pending(k, text),
        )
        return combo

    def _createIntWidget(self, key: str, value) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(-999999, 999999)
        spin.setValue(int(value) if value is not None else 0)
        spin.valueChanged.connect(
            lambda v, k=key: self._vm.set_pending(k, v),
        )
        return spin

    def _createFloatWidget(self, key: str, value) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-999999.0, 999999.0)
        spin.setDecimals(4)
        spin.setValue(float(value) if value is not None else 0.0)
        spin.valueChanged.connect(
            lambda v, k=key: self._vm.set_pending(k, v),
        )
        return spin

    def _createPathWidget(self, key: str, value, type_str: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        edit = QLineEdit()
        edit.setText(str(value) if value is not None else "")
        edit.textChanged.connect(
            lambda text, k=key: self._vm.set_pending(k, text),
        )
        layout.addWidget(edit, stretch=1)

        browseBtn = QPushButton(self.tr("Browse..."))
        browseBtn.setObjectName("settingsBrowseButton")
        browseBtn.setProperty("styleRole", "secondary")
        browseBtn.clicked.connect(
            lambda checked=False, edit_widget=edit, t=type_str: self._browsePath(edit_widget, t),
        )
        layout.addWidget(browseBtn)
        return container

    def _browsePath(self, edit_widget: QLineEdit, type_str: str) -> None:
        current_path = edit_widget.text()
        if type_str == "directory_path":
            path = QFileDialog.getExistingDirectory(self, self.tr("Select Directory"), current_path)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self.tr("Select File"), current_path)
        if path:
            edit_widget.setText(path)

    def _createStringWidget(self, key: str, value) -> QLineEdit:
        edit = QLineEdit()
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
