from matplotlib import colormaps
from ccdioutils import (
    CCDCaptureModel,
    CCDCaptureViewModel,
    CCDCaptureWidget,
    MatplotlibBasedConverter,
    FastPixmapConverter,
)
from PySide6 import QtWidgets, QtCore
from sys import argv, stderr
from pathlib import Path
import argparse


def getOptions():
    parser = argparse.ArgumentParser(
        prog="pyqt_fits_load",
        description="Displays a CCD capture and allows minimal filtering",
    )

    parser.add_argument(
        "-c",
        "--converter",
        choices=["matplotlib", "fast"],
        default="matplotlib",
        help="Choose a FITS to pixmap converter",
    )

    parser.add_argument(
        "file",
        help="Path to the FITS file",
    )

    return parser.parse_args(args=argv[1::])


class FitsLoadMainWindow(QtWidgets.QMainWindow):
    def __init__(self, ccd_widgets, window_title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ccd_widgets = ccd_widgets
        self.setWindowTitle(window_title)
        self.resize(1200, 800)

        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.setCentralWidget(self.scrollArea)

        self.contentWidget = QtWidgets.QWidget()
        self.scrollArea.setWidget(self.contentWidget)

        self.layout = QtWidgets.QVBoxLayout(self.contentWidget)
        self.layout.setAlignment(QtCore.Qt.AlignTop)

    def resizeEvent(self, event):
        self.resizeCCDWidgets()
        super().resizeEvent(event)

    def resizeCCDWidgets(self):
        viewport_width = self.scrollArea.viewport().width()
        for w in self.ccd_widgets:
            w.setMaximumWidth(viewport_width - 20)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    options = getOptions()
    print(options)

    kevFactor = 1.02857e-5
    input_path = Path(options.file)
    if not input_path.exists():
        print(f"File {argv[1]} not found or not a file", file=stderr)
        exit(1)

    dumps = CCDCaptureModel.load(input_path)

    widgets = []
    mainWindow = FitsLoadMainWindow(widgets, f"Viewer: {options.file}")

    layout = mainWindow.layout

    for i, dump in enumerate(dumps):
        convertedData = kevFactor * dump.rawData()
        exposure = CCDCaptureModel(convertedData, dump.info())
        if options.converter == "matplotlib":
            converter = MatplotlibBasedConverter(colormap=colormaps["Greys"])
        else:
            converter = FastPixmapConverter()
        viewModel = CCDCaptureViewModel(exposure, converter)

        widget = CCDCaptureWidget(viewModel)

        vbox = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(f"HDU[{i}]: {exposure.info().captureDate()}")
        vbox.addWidget(label)
        vbox.addWidget(widget)

        container = QtWidgets.QWidget()
        container.setLayout(vbox)
        layout.addWidget(container)
        widgets.append(widget)

    mainWindow.show()
    mainWindow.resizeCCDWidgets()
    app.exec()
