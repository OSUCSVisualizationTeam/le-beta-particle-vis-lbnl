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
        return np.zeros(data.shape, dtype='uint8')    # error handling for bad data that was passed
    
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

# # since our FITS data contains 4 images per file, loop through all HDUs to see each one 
# for i, hdu in enumerate(hdul) : 

#     # display the image using matplotlib
#     if hdu.data is not None : 
#         # Display the image
#         plt.figure(i)
#         plt.imshow(hdu.data, cmap='gray', origin='lower')
#         plt.axis('off')
#         plt.title(f'HDU {i} Image')
        
#         # plt.savefig(f'images\\original\\background_only_hdu_{i}_image.png', bbox_inches='tight', pad_inches=0)     # save image to disk space for easier reference
#     else : 
#         print("No image data in this HDU")

# # display all HDUs
# plt.show()

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
    # cv.imwrite(f"images\\original\\uint8_background_and_tritium_hdu_{i}.png", hdu)
    # cv.imwrite(f"images\\original\\uint8_background_only_hdu_{i}.png", hdu)
cv.imshow('HDU 3', uint8_data[3])

################################################################################################################
'''
Find Contours & Thresholds: Using Canny and Simple/Adaptive Threshold
'''
################################################################################################################
uint8_image = uint8_data[3]     # Using 1 specific HDU for demonstration

# Canny Edge Detection
canny_edges = cv.Canny(uint8_image, threshold1=100, threshold2=200)

# Display Canny Edges
cv.imshow('Canny Edges', canny_edges)
#cv.imwrite('images\\opencv_results\\canny_edges_background_and_tritium_hdu3.png', canny_edges)

# Simple Threshold
ret, thresh = cv.threshold(uint8_image, 25, 255, cv.THRESH_BINARY)

# Display Simple Threshold
cv.imshow('Simple Threshold', thresh)
#cv.imwrite('images\\opencv_results\\simple_thresh_background_and_tritium_hdu3.png', thresh)

# Adaptive Threshold
adaptive_thresh = cv.adaptiveThreshold(uint8_image, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, blockSize=11, C=2)

# Display Adaptive Threshold
cv.imshow('Adaptive Threshold', adaptive_thresh)
#cv.imwrite('images\\opencv_results\\adaptive_thresh_background_and_tritium_hdu3.png', adaptive_thresh)

cv.waitKey(0)