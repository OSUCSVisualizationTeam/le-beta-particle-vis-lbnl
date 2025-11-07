from ccdioutils import (
    CCDCaptureModel,
    CCDCaptureViewModel,
    CCDCaptureWidget,
    MatplotlibBasedConverter,
)
from PySide6 import QtWidgets
from sys import argv, stderr
from pathlib import Path


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    kevFactor = 1.02857e-5
    input_path = Path(argv[1])
    if not input_path.exists():
        print(f"File {argv[1]} not found or not a file", file=stderr)
        exit(1)

    dumps = CCDCaptureModel.load(input_path)

    widgets = []
    for i, dump in enumerate(dumps):
        convertedData = kevFactor * dump.rawData()
        exposure = CCDCaptureModel(convertedData, dump.info())
        converter = MatplotlibBasedConverter("Greys_r")
        viewModel = CCDCaptureViewModel(exposure, converter)

        widget = CCDCaptureWidget(viewModel)
        widget.setWindowTitle(f"HDU[{i}]: {exposure.info().captureDate()}")
        widget.setMaximumWidth(1980)
        widget.show()
        widgets.append(widget)  # Keep a reference to prevent garbage collection

    app.exec()
