from astropy.io import fits
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt

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

# since our FITS data contains 4 images per file, loop through all HDUs to see each one 
for i, hdu in enumerate(hdul) : 

    # display the image using matplotlib
    if hdu.data is not None : 
        # Display the image
        plt.figure(i)
        plt.imshow(hdu.data, cmap='gray', origin='lower')
        plt.axis('off')
        plt.title(f'HDU {i} Image')
        
        # plt.savefig(f'images\\background_only_hdu_{i}_image.png', bbox_inches='tight', pad_inches=0)     # save image to disk space for easier reference
    else : 
        print("No image data in this HDU")

# display all HDUs
plt.show()

hdul.close()
