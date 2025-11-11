from astropy.io import fits
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import silhouette_score

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
 
def kmeans_segmentation(image, k=2) : 
    pixel_values = image.reshape((-1, 1))  # Reshape to (num_pixels, 1)
    pixel_values = np.float32(pixel_values)  # Convert to float32 (if not already)

    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    ret, labels, centers = cv.kmeans(pixel_values, k, None, criteria, 10, cv.KMEANS_RANDOM_CENTERS)

    # Convert to uint8 for visualization purposes
    centers = float32_to_uint8(centers)
    segmented_image = centers[labels.flatten()]
    
    # Reshape back to the original image shape
    segmented_image = segmented_image.reshape(image.shape)

    return segmented_image, ret, labels



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

hdul.close()

################################################################################################################
'''
Preform K-Means
'''
################################################################################################################
# demo different k-values on a singular image: using HDU 3
hdu_3 = fits_data[3]

for i in range(2, 11) : 
    print(f'HDU 3 (K = {i}): ')
    segmented_hdu, ret, labels = kmeans_segmentation(hdu_3, k=i)
    
    # Calculate silhouette score, however only works when k >= 2
    # silhouette_avg = silhouette_score(segmented_hdu.reshape(-1, 1), labels.flatten())       # 
    # print(f'Silhouette Score: {silhouette_avg}')
    
    # Print inertia
    print(f'Inertia: {ret}')

    # Calculate and print cluster sizes
    unique, counts = np.unique(labels, return_counts=True)
    cluster_sizes = dict(zip(unique, counts))
    cleaned_cluster_sizes = {int(k): int(v) for k, v in cluster_sizes.items()}      # convert into integers for readability
    print(f'Cluster sizes for k={i}: {cleaned_cluster_sizes}\n')

cv.waitKey(0)