from matplotlib import colormaps
from ccdioutils import (
    CCDCaptureModel,
    CCDCaptureViewModel,
    CCDCaptureWidget,
    MatplotlibBasedConverter,
    FastPixmapConverter,
)
from PySide6 import QtWidgets
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
    for i, dump in enumerate(dumps):
        convertedData = kevFactor * dump.rawData()
        exposure = CCDCaptureModel(convertedData, dump.info())
        if options.converter == "matplotlib":
            converter = MatplotlibBasedConverter(colormap=colormaps["Greys"])
        else:
            converter = FastPixmapConverter()
        viewModel = CCDCaptureViewModel(exposure, converter)

        widget = CCDCaptureWidget(viewModel)
        widget.setWindowTitle(f"HDU[{i}]: {exposure.info().captureDate()}")
        widget.setMaximumWidth(1980)
        widget.show()
        # Keep a reference to prevent garbage collection
        widgets.append(widget)

    app.exec()
