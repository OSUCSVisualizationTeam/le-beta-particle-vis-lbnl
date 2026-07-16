"""Windows IPC fallback dialog — bound to IPCFallbackViewModel.

Shown once at startup when ``ipc://`` binds are detected as unusable on
this Windows machine (issue #204). Lets the user redirect the four
startup ZMQ endpoints to ``tcp://host:port`` instead, or quit. Has no
close ("X") button and ignores Escape — this is a mandatory startup gate,
not a dismissible dialog.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels.IPCFallbackViewModel import IPCFallbackViewModel


class IPCFallbackDialogView(QDialog):
    """Modal, non-dismissible dialog offering a ``tcp://`` fallback for the
    four startup ``ipc://`` endpoints.

    Save persists the edited endpoints and tells the user to relaunch;
    Quit warns that the application remains unusable until the user acts.
    Both actions end with ``self.accept()``/``self.reject()`` — no result
    page is shown inside the dialog itself.
    """

    def __init__(
        self,
        viewModel: IPCFallbackViewModel,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self._vm = viewModel

        self.setWindowTitle(self.tr("Network Configuration Required"))
        self.setMinimumWidth(480)
        self.setWindowFlags(
            Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )

        self._initUI()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _initUI(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        explanation = QLabel(
            self.tr(
                "This version of LE Beta Particle Visualization cannot "
                "start its background services on Windows using the "
                "default network settings. Choose host/port combinations "
                "below — the suggested values are free ports on this "
                "machine — then Save and relaunch the application."
            )
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        group = QGroupBox(self.tr("Network Endpoints"))
        form = QFormLayout(group)
        form.setSpacing(6)

        self._hostEdits = []
        self._portEdits = []
        port_validator = QIntValidator(1, 65535, self)

        for index, row in enumerate(self._vm.rows):
            rowWidget = QWidget()
            rowLayout = QHBoxLayout(rowWidget)
            rowLayout.setContentsMargins(0, 0, 0, 0)
            rowLayout.setSpacing(4)

            hostEdit = QLineEdit(row.host)
            hostEdit.textChanged.connect(
                lambda text, i=index: self._vm.update_host(i, text)
            )
            rowLayout.addWidget(hostEdit, stretch=2)

            rowLayout.addWidget(QLabel(":"))

            portEdit = QLineEdit(row.port_text)
            portEdit.setValidator(port_validator)
            portEdit.textChanged.connect(
                lambda text, i=index: self._vm.update_port(i, text)
            )
            rowLayout.addWidget(portEdit, stretch=1)

            self._hostEdits.append(hostEdit)
            self._portEdits.append(portEdit)
            form.addRow(QLabel(row.label), rowWidget)

        root.addWidget(group)

        btnRow = QHBoxLayout()
        btnRow.addStretch()

        quitBtn = QPushButton(self.tr("Quit"))
        quitBtn.setProperty("styleRole", "secondary")
        quitBtn.clicked.connect(self._onQuit)
        btnRow.addWidget(quitBtn)

        saveBtn = QPushButton(self.tr("Save"))
        saveBtn.setProperty("styleRole", "primary")
        saveBtn.clicked.connect(self._onSave)
        btnRow.addWidget(saveBtn)

        root.addLayout(btnRow)

    # ------------------------------------------------------------------
    # Startup-gate overrides: no way to dismiss without an explicit choice
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        event.ignore()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _onSave(self) -> None:
        if not self._vm.save():
            QMessageBox.critical(
                self,
                self.tr("Invalid Network Settings"),
                self._vm.last_error or self.tr("Please check the values entered."),
            )
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(self.tr("Settings Saved"))
        box.setText(
            self.tr(
                "Your network settings have been saved. LE Beta Particle "
                "Visualization must be closed and relaunched for the new "
                "settings to take effect."
            )
        )
        box.addButton(self.tr("Exit"), QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        self.accept()

    def _onQuit(self) -> None:
        reply = QMessageBox.warning(
            self,
            self.tr("Quit Without Saving?"),
            self.tr(
                "LE Beta Particle Visualization cannot start its "
                "background services on this machine with the current "
                "network settings. If you quit now, the application will "
                "remain unusable until you edit the configuration file "
                "manually or relaunch and use Save instead.\n\n"
                "Quit anyway?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vm.quit()
            self.reject()
