# fits_load experiments

Contains two tools:

- `fits_load.py`: Reads a single fits file, loads it using astropy and renders all its image-based HDUs using matplotlib.
- `pyqt_fits_load.py`: Reads a single fits file, loads it using astropy arrays, renders and image using matplotlib, and displays it using a PyQT widget that allows changing a few characteristics of visualization. The widget is intended to be the basis of the visualization and is being designed to be a drop-in component.

## ccdioutils

This library contains all the source code for the drop-in PyQT Widget, internally reflects the MVVM pattern and is intended to also serve as a guide on how to develop the resp of the application modules.

To test `ccdioutils` run:

```
python -m unittest discover tests
```
