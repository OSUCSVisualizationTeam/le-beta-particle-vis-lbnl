from astropy.io import fits
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt

################################################################################################################
'''
Function Definitions
'''
################################################################################################################
def float32_to_uint8(data) : 
    data_min = np.min(data)
    data_max = np.max(data)

    if data_max == data_min : 
        return np.zeros(data.shape, dtype=uint8)    # error handling for bad data that was passed
    
    normalized = (data - data_min) / (data_max - data_min)
    uint8_data = (normalized * 255).astype(np.uint8)
    return uint8_data
 

################################################################################################################
'''
Read + display raw FITS data using Astropy and Matplotlib
    -- Displays 
'''
################################################################################################################

# fits_data = 'data\\subMed_proc_3oct2022_G2ccd_back_meas___EXP1_NSAMP9_VSUB70_img65.fits'        # Background Only
fits_data ='data\\subMed_proc_6oct2022_G2ccd_h3_meas_v2___EXP1_NSAMP1_VSUB70_img591.fits'     # Background + Tritium

# open the FITS file at the specific path
hdul = fits.open(fits_data)
fits_data = [hdu.data for hdu in hdul if hdu.data is not None]

# close the FITS open() instance
hdul.close()

################################################################################################################
'''
Normalize FITS Data & Convert Float32 To UINT8
'''
################################################################################################################
uint8_data = [float32_to_uint8(image) for image in fits_data]

################################################################################################################
'''
Display UInt8 Images Using OpenCV
'''
################################################################################################################
for i, hdu in enumerate(uint8_data) : 
    cv.imshow(f"HDU: {i}", hdu)

cv.waitKey(0)