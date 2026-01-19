from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QFileDialog
from PySide6.QtGui import QAction, QKeySequence
from .viewmodels.MainViewModel import MainViewModel
from .views.RawDataView import RawDataView
from .views.HistoricalView import HistoricalView
from .viewmodels.RawDataViewModel import RawDataViewModel
from .viewmodels.HistoricalViewModel import HistoricalViewModel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.viewModel = MainViewModel()
        
        # self.tr() marks the string for translation
        self.setWindowTitle(self.tr("LE Beta Particle Visualization"))
        self.resize(1024, 768)

        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Tab Widget for Modes
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Initialize Child ViewModels with Configuration Service
        self.rawDataViewModel = RawDataViewModel(self.viewModel.configService)
        self.historicalViewModel = HistoricalViewModel() # Will add config later

        # Initialize Child Views
        self.rawDataView = RawDataView(self.rawDataViewModel)
        self.historicalView = HistoricalView(self.historicalViewModel)

        # Add Tabs - Strings inside self.tr()
        self.tabs.addTab(self.rawDataView, self.tr("Raw Data Analysis"))
        self.tabs.addTab(self.historicalView, self.tr("Historical Analysis"))

        # Setup Menu Bar
        self.setupMenuBar()

    def setupMenuBar(self):
        menuBar = self.menuBar()

        # File Menu
        fileMenu = menuBar.addMenu(self.tr("&File"))

        # Open Action
        openAction = QAction(self.tr("&Open..."), self)
        openAction.setShortcut(QKeySequence.Open)
        openAction.setStatusTip(self.tr("Open a FITS file"))
        openAction.triggered.connect(self.onOpenFile)
        fileMenu.addAction(openAction)

        fileMenu.addSeparator()

        # Exit Action
        exitAction = QAction(self.tr("E&xit"), self)
        exitAction.setShortcut(QKeySequence.Quit)
        exitAction.setStatusTip(self.tr("Exit the application"))
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)

    def onOpenFile(self):
        """Open a file dialog to select a FITS file and load it into the Raw Data view."""
        filePath, _ = QFileDialog.getOpenFileName(
            self, 
            self.tr("Open FITS File"), 
            "", 
            self.tr("FITS Files (*.fits);;All Files (*)")
        )
        if filePath:
            # Switch to Raw Data tab
            self.tabs.setCurrentWidget(self.rawDataView)
            # Load the file via the ViewModel
            self.rawDataViewModel.loadFile(filePath)