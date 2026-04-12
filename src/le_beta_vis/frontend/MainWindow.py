import sys

from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QFileDialog,
)
from PySide6.QtGui import QAction, QIcon, QKeySequence
from .viewmodels.MainViewModel import MainViewModel
from .views.RawDataView import RawDataView
from .views.HistoricalView import HistoricalView
from .viewmodels.RawDataViewModel import RawDataViewModel
from .viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
    HistoricalMode,
)
from le_beta_vis.common.ClusterExtractorFactory import (
    create_cluster_extractor,
)
from pathlib import Path


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.viewModel = MainViewModel()
        self._setupWindowIdentity()
        self._setupWindowGeometry()
        self._setupCentralWidget()
        self._setupViewModels()
        self._setupViews()
        self.setupMenuBar()
        self._bindCallbacks()

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

    def _setupViews(self) -> None:
        self.rawDataView = RawDataView(self.rawDataViewModel)
        self.historicalView = HistoricalView(self.historicalViewModel)
        self.tabs.addTab(self.rawDataView, self.tr("Raw Data Analysis"))
        self.tabs.addTab(self.historicalView, self.tr("Historical Analysis"))

    def _bindCallbacks(self) -> None:
        self.historicalViewModel.add_mode_changed_callback(self.onModeChanged)

    # -- Menu bar --------------------------------------------------------------

    def setupMenuBar(self) -> None:
        menuBar = self.menuBar()
        self._setupFileMenu(menuBar)
        self._setupViewMenu(menuBar)
        self._setupHelpMenu(menuBar)
        self.onModeChanged(self.historicalViewModel.mode)

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

        self.toggleLiveAction = QAction(self.tr("Switch to Live Mode"), self)
        self.toggleLiveAction.setCheckable(True)
        self.toggleLiveAction.setChecked(False)
        self.toggleLiveAction.triggered.connect(self.onToggleLiveMode)
        viewMenu.addAction(self.toggleLiveAction)

        viewMenu.addSeparator()

        screensaverAction = QAction(
            self.tr("Enter &Screensaver"), self,
        )
        screensaverAction.setShortcut(QKeySequence("Ctrl+Shift+S"))
        screensaverAction.triggered.connect(self._onEnterScreensaver)
        viewMenu.addAction(screensaverAction)

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

    def onToggleLiveMode(self) -> None:
        """Handle the toggle action from the menu."""
        if self.tabs.currentWidget() == self.rawDataView:
            self.tabs.setCurrentWidget(self.historicalView)
        self.historicalViewModel.toggleMode()

    def onModeChanged(self, mode: HistoricalMode) -> None:
        """Callback from ViewModel when mode changes."""
        is_live = mode == HistoricalMode.LIVE
        self.toggleLiveAction.setChecked(is_live)
        if is_live:
            self.toggleLiveAction.setText(self.tr("Switch to Historical Mode"))
        else:
            self.toggleLiveAction.setText(self.tr("Switch to Live Mode"))
