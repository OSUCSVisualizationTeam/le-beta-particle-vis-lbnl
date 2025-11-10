from astropy.io import fits
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt

# Load FITS file using Astropy
# fits_data = 'data\\subMed_proc_3oct2022_G2ccd_back_meas___EXP1_NSAMP9_VSUB70_img65.fits'        # Background Only
fits_data ='data\\subMed_proc_6oct2022_G2ccd_h3_meas_v2___EXP1_NSAMP1_VSUB70_img591.fits'     # Background + Tritium

hdul = fits.open(fits_data)
hdul.info()

hdul.close()
