# fits_load experiments

`pyqt_fits_load.py`: Reads a single fits file, loads it using astropy arrays, renders and image using matplotlib, and displays it using a PyQT widget that allows changing a few characteristics of visualization. The widget is intended to be the basis of the visualization and is being designed to be a drop-in component.

To run it:

```
usage: pyqt_fits_load [-h] [-c {matplotlib,fast}] file

Displays a CCD capture and allows minimal filtering

positional arguments:
  file                  Path to the FITS file

options:
  -h, --help            show this help message and exit
  -c, --converter {matplotlib,fast}
                        Choose a FITS to pixmap converter
```

Use the `fast` converter to get a 16-bit grayscale colormap and the ability to cull data in realtime

Example:

```bash
# Fast render (allows SNR reduction in realtime)
python pyqt_fits_load -c fast somefile.fits

# Beautiful matplotlib render (slow)
python pyqt_fits_load -c matplotlib somefile.fits
```

## ccdioutils

This library contains all the source code for the drop-in PyQT Widget, internally reflects the MVVM pattern and is intended to also serve as a guide on how to develop the resp of the application modules.

To test `ccdioutils` run:

```
python -m unittest discover tests
```
