import sys

from PySide6.QtCore import Qt, QMetaObject, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QProgressBar,
    QToolButton,
)
from PySide6.QtGui import QAction, QIcon, QKeySequence
from .viewmodels.MainViewModel import MainViewModel
from .viewmodels.MainWindowStatusViewModel import (
    MainWindowStatusViewModel,
    Severity,
)
from .views.RawDataView import RawDataView
from .views.HistoricalView import HistoricalView
from .viewmodels.RawDataViewModel import RawDataViewModel
from .viewmodels.HistoricalViewModel import HistoricalViewModel
from . import theme
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterExtractorFactory import (
    create_cluster_extractor,
)
from pathlib import Path


_MAX_VISIBLE_PROGRESS_ROWS = 3


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.viewModel = MainViewModel()
        self._setupWindowIdentity()
        self._setupWindowGeometry()
        self._setupCentralWidget()
        self._setupViewModels()
        self._setupStatusBar()
        self._setupViews()
        self.setupMenuBar()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if hasattr(self, "statusViewModel"):
            self.statusViewModel.shutdown()
        super().closeEvent(event)

    # -- Initialization helpers ------------------------------------------------

    def _setupWindowIdentity(self) -> None:
        self.setWindowTitle(self.tr("LE Beta Particle Visualization"))
        icon_path = (
            Path(__file__).resolve().parent.parent
            / "resources"
            / "icons"
            / "lbnl-logo.png"
        )
        self.setWindowIcon(QIcon(str(icon_path)))

    def _setupWindowGeometry(self) -> None:
        self.setMinimumSize(960, 600)
        width = self.viewModel.configService.get("gui:window:default_width", 1024)
        height = self.viewModel.configService.get("gui:window:default_height", 700)
        self.resize(width, height)

    def _setupCentralWidget(self) -> None:
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

    def _setupViewModels(self) -> None:
        self.rawDataViewModel = RawDataViewModel(
            self.viewModel.configService, self.viewModel.physicsManager
        )
        self.rawDataViewModel.setClusterExtractor(
            create_cluster_extractor(
                self.viewModel.configService, self.viewModel.physicsManager
            )
        )
        self.historicalViewModel = HistoricalViewModel(
            self.viewModel.configService,
            self.viewModel.physicsManager,
            self.viewModel.eventRepository,
            self.viewModel.thumbnailService,
        )

    def _setupStatusBar(self) -> None:
        timeout = self.viewModel.configService.get(
            "gui:window:status_bar_clear_timeout_s", 5
        )
        self.statusViewModel = MainWindowStatusViewModel(
            self.viewModel.eventHandler,
            clear_timeout_s=float(timeout),
        )

        statusBar = self.statusBar()
        self._statusMessageLabel = QLabel("", statusBar)
        self._statusMessageLabel.setObjectName("mainWindowStatusMessage")
        statusBar.addWidget(self._statusMessageLabel, 1)

        self._progressHost = QWidget(statusBar)
        self._progressHostLayout = QHBoxLayout(self._progressHost)
        self._progressHostLayout.setContentsMargins(0, 0, 0, 0)
        self._progressHostLayout.setSpacing(8)
        statusBar.addPermanentWidget(self._progressHost)

        self.statusViewModel.add_message_changed_callback(
            lambda: QMetaObject.invokeMethod(
                self, "_onStatusMessageChanged", Qt.AutoConnection
            )
        )
        self.statusViewModel.add_progress_changed_callback(
            lambda: QMetaObject.invokeMethod(
                self, "_onStatusProgressChanged", Qt.AutoConnection
            )
        )
        self._onStatusMessageChanged()
        self._onStatusProgressChanged()

    @Slot()
    def _onStatusMessageChanged(self) -> None:
        message = self.statusViewModel.message
        severity = self.statusViewModel.severity
        self._statusMessageLabel.setText(message)
        color = {
            Severity.INFO: theme.MainWindowStatusBarColors.TEXT_INFO,
            Severity.WARNING: theme.MainWindowStatusBarColors.TEXT_WARNING,
            Severity.ERROR: theme.MainWindowStatusBarColors.TEXT_ERROR,
        }.get(severity, theme.MainWindowStatusBarColors.TEXT_INFO)
        self._statusMessageLabel.setStyleSheet(f"color: {color};")

    @Slot()
    def _onStatusProgressChanged(self) -> None:
        while self._progressHostLayout.count():
            item = self._progressHostLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        snapshots = self.statusViewModel.active_progress
        visible = snapshots[:_MAX_VISIBLE_PROGRESS_ROWS]
        overflow = snapshots[_MAX_VISIBLE_PROGRESS_ROWS:]

        for snap in visible:
            self._progressHostLayout.addWidget(self._buildProgressRow(snap))

        if overflow:
            more = QLabel(
                self.tr("+{n} more").format(n=len(overflow)),
                self._progressHost,
            )
            more.setStyleSheet(
                f"color: {theme.MainWindowStatusBarColors.PROGRESS_LABEL};"
            )
            more.setToolTip("\n".join(s.label for s in overflow))
            self._progressHostLayout.addWidget(more)

    def _buildProgressRow(self, snap) -> QWidget:
        row = QWidget(self._progressHost)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(snap.label, row)
        label.setStyleSheet(
            f"color: {theme.MainWindowStatusBarColors.PROGRESS_LABEL};"
        )
        layout.addWidget(label)

        if snap.message:
            sub = QLabel(f"— {snap.message}", row)
            sub.setStyleSheet(
                f"color: {theme.MainWindowStatusBarColors.PROGRESS_LABEL};"
            )
            layout.addWidget(sub)

        bar = QProgressBar(row)
        bar.setFixedWidth(120)
        bar.setTextVisible(False)
        if snap.fraction < 0.0:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 1000)
            bar.setValue(int(max(0.0, min(1.0, snap.fraction)) * 1000))
        bar.setStyleSheet(
            "QProgressBar {{ background: {bg}; border: none; }}"
            "QProgressBar::chunk {{ background: {chunk}; }}".format(
                bg=theme.MainWindowStatusBarColors.PROGRESS_BACKGROUND,
                chunk=theme.MainWindowStatusBarColors.PROGRESS_CHUNK,
            )
        )
        layout.addWidget(bar)

        if snap.cancelable:
            cancel = QToolButton(row)
            cancel.setText(self.tr("✕"))
            cancel.setToolTip(self.tr("Cancel"))
            token = snap.token
            cancel.clicked.connect(
                lambda _=False, t=token: self.statusViewModel.request_cancel(t)
            )
            layout.addWidget(cancel)

        return row

    def _setupViews(self) -> None:
        self.rawDataView = RawDataView(self.rawDataViewModel)
        self.historicalView = HistoricalView(
            self.historicalViewModel,
            statusViewModel=self.statusViewModel,
            openInRawDataHandler=self._openClusterInRawData,
        )
        self.tabs.addTab(self.rawDataView, self.tr("Raw Data Analysis"))
        self.tabs.addTab(self.historicalView, self.tr("Historical Analysis"))

    # -- Menu bar --------------------------------------------------------------

    def setupMenuBar(self) -> None:
        menuBar = self.menuBar()
        self._setupFileMenu(menuBar)
        self._setupViewMenu(menuBar)
        self._setupHelpMenu(menuBar)

    def _setupFileMenu(self, menuBar) -> None:
        fileMenu = menuBar.addMenu(self.tr("&File"))

        openAction = QAction(self.tr("&Open..."), self)
        openAction.setShortcut(QKeySequence.Open)
        openAction.setStatusTip(self.tr("Open a FITS file"))
        openAction.triggered.connect(self.onOpenFile)
        fileMenu.addAction(openAction)

        fileMenu.addSeparator()

        if sys.platform == "darwin":
            settingsAction = QAction(self.tr("&Preferences"), self)
            settingsAction.setShortcut(QKeySequence("Ctrl+,"))
            settingsAction.setMenuRole(QAction.MenuRole.PreferencesRole)
        else:
            settingsAction = QAction(self.tr("&Settings"), self)
        settingsAction.setStatusTip(self.tr("Configure application settings"))
        settingsAction.triggered.connect(self._onOpenSettings)
        fileMenu.addAction(settingsAction)

        fileMenu.addSeparator()

        exitAction = QAction(self.tr("E&xit"), self)
        exitAction.setShortcut(QKeySequence.Quit)
        exitAction.setStatusTip(self.tr("Exit the application"))
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)

    def _setupViewMenu(self, menuBar) -> None:
        viewMenu = menuBar.addMenu(self.tr("&View"))

        liveModeAction = QAction(self.tr("Live Mode"), self)
        liveModeAction.setShortcut(QKeySequence("Ctrl+Shift+S"))
        liveModeAction.triggered.connect(self._onEnterScreensaver)
        viewMenu.addAction(liveModeAction)

    def _setupHelpMenu(self, menuBar) -> None:
        helpMenu = menuBar.addMenu(self.tr("&Help"))
        aboutAction = QAction(self.tr("About LE Beta Vis"), self)
        if sys.platform == "darwin":
            aboutAction.setMenuRole(QAction.MenuRole.AboutRole)
        aboutAction.triggered.connect(self._onShowAbout)
        helpMenu.addAction(aboutAction)

    # -- Slots -----------------------------------------------------------------

    def _onShowAbout(self) -> None:
        """Open the About dialog."""
        from .viewmodels.AboutViewModel import AboutViewModel
        from .widgets.AboutDialog import AboutDialog

        vm = AboutViewModel()
        dialog = AboutDialog(vm, parent=self)
        dialog.exec()

    def _onEnterScreensaver(self) -> None:
        """Opens the fullscreen Live Mode screensaver."""
        from le_beta_vis.frontend.livemode.LiveModeViewModel import (
            LiveModeViewModel,
        )
        from le_beta_vis.frontend.livemode.LiveModeView import (
            LiveModeView,
        )

        vm = LiveModeViewModel(
            config=self.viewModel.configService,
            eventHandler=self.viewModel.eventHandler,
            repository=self.viewModel.eventRepository,
            physics=self.viewModel.physicsManager,
            thumbnailService=self.viewModel.thumbnailService,
        )
        dialog = LiveModeView(vm, parent=self)
        dialog.exec()

    def _onOpenSettings(self) -> None:
        """Open the Settings dialog."""
        from .viewmodels.SettingsViewModel import SettingsViewModel
        from .widgets.SettingsDialog import SettingsDialog

        vm = SettingsViewModel(self.viewModel.configService)
        dialog = SettingsDialog(vm, parent=self)
        dialog.exec()

    def onOpenFile(self) -> None:
        """Open a file dialog and load it into the Raw Data view."""
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open FITS File"),
            "",
            self.tr("FITS Files (*.fits);;All Files (*)"),
        )
        if filePath:
            self.tabs.setCurrentWidget(self.rawDataView)
            self.rawDataViewModel.loadFile(filePath)

    def _openClusterInRawData(self, cluster: Cluster) -> None:
        """Navigates from the Historical Inspector to Raw Data Analysis.

        Performs a preflight check on the cluster's FITS path, switches
        to the Raw Data Analysis tab, computes a padded ROI rectangle
        around the cluster's bounding box, and delegates the load /
        HDU select / fit-to-ROI sequence to ``RawDataView``.
        """
        path = cluster.fitsFilename
        if not path or not Path(path).exists():
            msg = self.tr(
                "FITS file not found:\n{path}"
            ).format(path=path or self.tr("(no path on cluster)"))
            self.statusViewModel.set_message(msg, severity=Severity.WARNING)
            QMessageBox.warning(self, self.tr("Open in Raw Data"), msg)
            return

        self.tabs.setCurrentWidget(self.rawDataView)

        bb = cluster.boundingBox
        pad = float(
            self.viewModel.configService.get(
                "gui:historical:roi_padding_factor", 2.0,
            )
        )
        # Center the ROI on the bounding-box geometric center so the
        # cluster sits in the middle of the rectangle. The peak-energy
        # pixel (cluster.centerX/Y) is often offset within the bbox.
        cx = (bb.left + bb.right) / 2.0
        cy = (bb.top + bb.bottom) / 2.0
        half_w = ((bb.right - bb.left) * pad) / 2.0
        half_h = ((bb.bottom - bb.top) * pad) / 2.0
        roi = (
            int(round(cy - half_h)),
            int(round(cx - half_w)),
            int(round(cy + half_h)),
            int(round(cx + half_w)),
        )
        self.rawDataView.openClusterForAnalysis(path, cluster.hdu_id, roi)
