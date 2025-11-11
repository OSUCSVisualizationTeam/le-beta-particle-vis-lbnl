# Prototype: Using OpenCV on FITS data

## Libraries

### Astropy
A Python library for astronomy that provides tools to read, write, and manipulate FITS files and other astronomical data formats.
```
pip install astropy
```

### OpenCV
A computer vision library used for image processing, analysis, and manipulation tasks.
```
pip install opencv-contrib-python
```

### Numpy
A fundamental package for scientific computing in Python, providing support for large, multi-dimensional arrays and matrices along with mathematical functions.
```
pip install numpy
```

### Matplotlib
A plotting library for creating static, interactive, and animated visualizations in Python.
```
pip install matplotlib
```

## Data

### Background Only
```
Filename: data\subMed_proc_3oct2022_G2ccd_back_meas___EXP1_NSAMP9_VSUB70_img65.fits
No.    Name      Ver    Type      Cards   Dimensions   Format
  0  PRIMARY       1 PrimaryHDU     163   (3200, 550)   float32
  1                1 ImageHDU       162   (3200, 550)   float32
  2                1 ImageHDU       162   (3200, 550)   float32
  3                1 ImageHDU       162   (3200, 550)   float32
```

### Background + Tritium
```
Filename: data\subMed_proc_6oct2022_G2ccd_h3_meas_v2___EXP1_NSAMP1_VSUB70_img591.fits
No.    Name      Ver    Type      Cards   Dimensions   Format
  0  PRIMARY       1 PrimaryHDU     163   (3200, 550)   float32
  1                1 ImageHDU       162   (3200, 550)   float32
  2                1 ImageHDU       162   (3200, 550)   float32
  3                1 ImageHDU       162   (3200, 550)   float32
```

## Read FITS Data

### Load FITS data
```
fits_data ='data\\subMed_proc_6oct2022_G2ccd_h3_meas_v2___EXP1_NSAMP1_VSUB70_img591.fits'

# open the FITS file at the specific path
hdul = fits.open(fits_data)
# save FIST data for later usage
fits_data = [hdu.data for hdu in hdul if hdu.data is not None]
```

### Display Raw FITS Data via Matplotlib
NOTE: FITS data supplied by LBNL contains 4 HDUs in each FITS file
```
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
```

## Normalizing FITS Data: Float32 --> UInt8

### Conversion Function
Normalizes a NumPy float32 array to the 0–255 range and returns it as uint8, with a fallback to zeros if all values are identical
```
def float32_to_uint8(data) : 
    data_min = np.min(data)
    data_max = np.max(data)

    if data_max == data_min : 
        return np.zeros(data.shape, dtype.uint8)    # error handling for bad data that was passed
    
    normalized = (data - data_min) / (data_max - data_min)
    uint8_data = (normalized * 255).astype(np.uint8)
    return uint8_data
```

### Apply Conversion Function To FITS Data
```
uint8_data = [float32_to_uint8(image) for image in fits_data]
```

## Display Original HDU Images Using OpenCV

### Use OpenCV's imshow() Function
```
for i, hdu in enumerate(uint8_data) : 
    cv.imshow(f"HDU: {i}", hdu)
```

## Original UInt8 Image of HDU 3 - Background + Tritium
![UInt8 HDU 3 Original](images/original/uint8_background_and_tritium_hdu_3.png)

## OpenCV Operations on FITS Data: Edge Detection + Thresholds
FITS HDU used for follow OpenCV operations: `uint8_image = uint8_data[3]`

### Canny Edge Detection
The cv.Canny function detects edges in the image. You can adjust the `threshold1` and `threshold2` parameters to control the sensitivity of edge detection.
```
# Canny Edge Detection
canny_edges = cv.Canny(uint8_image, threshold1=100, threshold2=200)

# Display Canny Edges
cv.imshow('Canny Edges', canny_edges)
```

### Canny Edge Results
![Canny Edges](images/opencv_results/canny_edges_background_and_tritium_hdu3.png)

### Simple Threshold
The cv.threshold function converts the image to a binary image based on a fixed threshold (25 in this case). Pixels above this threshold are set to 255 (white), and those below are set to 0 (black).
```
# Simple Threshold
ret, thresh = cv.threshold(uint8_image, 25, 255, cv.THRESH_BINARY)

# Display Simple Threshold
cv.imshow('Simple Threshold', thresh)
```

### Simple Threshold Results
![Simple Thresh](images/opencv_results/simple_thresh_background_and_tritium_hdu3.png)

### Adaptive Threshold
The cv.adaptiveThreshold function calculates the threshold for smaller regions of the image, which can be useful for images with varying lighting conditions.
```
# Adaptive Threshold
adaptive_thresh = cv.adaptiveThreshold(uint8_image, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, blockSize=11, C=2)

# Display Adaptive Threshold
cv.imshow('Adaptive Threshold', adaptive_thresh)
```

### Adaptive Threshold Results
![Adaptive Thresh](images/opencv_results/adaptive_thresh_background_and_tritium_hdu3.png)

## K Means Implementation
NOTE: Limited Variation - If you notice that images look similar beyond k=3, it may indicate that the underlying data does not have enough distinct intensity values to warrant more clusters. In such cases, additional clusters may not provide meaningful segmentation.

### Function Definition
This function performs K-Means clustering on the input image, reshaping it for processing, applying the K-Means algorithm, and returning a segmented image based on the specified number of clusters k.
```
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

    return segmented_image
```

### Read FITS Data
This section opens the specified FITS file, extracts the image data from each HDU (Header Data Unit), and stores it in a list for further processing, ensuring that only valid data is retained.
NOTE: No need to convert float32 to uint8 until later, as k-means expects float32 values.
```
fits_data ='data\\subMed_proc_6oct2022_G2ccd_h3_meas_v2___EXP1_NSAMP1_VSUB70_img591.fits'     # Background + Tritium

# open the FITS file at the specific path
hdul = fits.open(fits_data)
fits_data = [hdu.data for hdu in hdul if hdu.data is not None]

hdul.close()
```

### Preform K Means
This part selects the third HDU from the FITS data and iteratively applies K-Means segmentation with varying values of k (from 1 to 10), saving the resulting segmented images to the specified directory for analysis.
```
hdu_3 = fits_data[3]
for i in range(1, 11) : 
    segmented_hdu = kmeans_segmentation(hdu_3, k=i)
```

## K Means Results For K = 2-10 On HDU 3 - Background + Tritium Image
NOTE: On the sample data provided by LBNL, there is not much visual variation, increasing the number of clusters may still help in identifying subtle differences in pixel intensity distributions or in enhancing specific features that could be relevant for further analysis.

### Definitions
- **Inertia**: Inertia, also known as the within-cluster sum of squares, is a metric used to evaluate the compactness of clusters formed by the K-Means clustering algorithm. It measures the total distance between each data point and the centroid (center) of the cluster to which it belongs. Mathematically, inertia is calculated as the sum of squared distances from each point to its assigned cluster centroid. 
    - A lower inertia value indicates that the clusters are more compact, meaning that the data points are closer to their respective centroids. Conversely, a higher inertia value suggests that the clusters are more spread out. When comparing different values of the number of clusters (k), a decrease in inertia typically indicates improved clustering performance.

- **Cluster Size**: Cluster sizes refer to the number of data points assigned to each cluster after performing K-Means clustering. Each cluster is represented by a unique label, and the size of a cluster is determined by counting how many data points belong to that cluster.
    -  Analyzing cluster sizes provides insight into the distribution of data points across different clusters. It helps to understand how well the data is partitioned and whether certain clusters are significantly larger or smaller than others. This information can be useful for evaluating the effectiveness of the clustering and for identifying potential imbalances in the data distribution.

### Numerical Outputs:
```
HDU 3 (K = 2):
Inertia: 187950035155300.66
Cluster sizes for k=2: {0: 1758159, 1: 1841}

HDU 3 (K = 3):
Inertia: 86314520999836.31
Cluster sizes for k=3: {0: 670, 1: 4744, 2: 1754586}

HDU 3 (K = 4):
Inertia: 47899679496499.21
Cluster sizes for k=4: {0: 6029, 1: 1752383, 2: 1279, 3: 309}

HDU 3 (K = 5):
Inertia: 31371455486042.89
Cluster sizes for k=5: {0: 1749934, 1: 248, 2: 777, 3: 2330, 4: 6711}

HDU 3 (K = 6):
Inertia: 22591338836445.742
Cluster sizes for k=6: {0: 2908, 1: 190, 2: 464, 3: 1748317, 4: 7075, 5: 1046}

HDU 3 (K = 7):
Inertia: 17086301540888.545
Cluster sizes for k=7: {0: 626, 1: 1747299, 2: 274, 3: 129, 4: 1292, 5: 3104, 6: 7276}

HDU 3 (K = 8):
Inertia: 13514509376135.861
Cluster sizes for k=8: {0: 108, 1: 393, 2: 750, 3: 1746135, 4: 1704, 5: 196, 6: 3380, 7: 7334}

HDU 3 (K = 9):
Inertia: 11023379616080.006
Cluster sizes for k=9: {0: 102, 1: 583, 2: 980, 3: 329, 4: 2098, 5: 1744530, 6: 3709, 7: 7496, 8: 173}

HDU 3 (K = 10):
Inertia: 9308014294049.87
Cluster sizes for k=10: {0: 95, 1: 1743628, 2: 228, 3: 454, 4: 690, 5: 1263, 6: 2161, 7: 151, 8: 3768, 9: 7562}
```

### K = 2
![K Means 2](images/kmeans_results/_kmeans_at_2_background_and_tritium_hdu_3.png)

### K = 3
![K Means 3](images/kmeans_results/_kmeans_at_3_background_and_tritium_hdu_3.png)

### K = 4
![K Means 4](images/kmeans_results/_kmeans_at_4_background_and_tritium_hdu_3.png)

### K = 5
![K Means 5](images/kmeans_results/_kmeans_at_5_background_and_tritium_hdu_3.png)

### K = 6
![K Means 6](images/kmeans_results/_kmeans_at_6_background_and_tritium_hdu_3.png)

### K = 7
![K Means 7](images/kmeans_results/_kmeans_at_7_background_and_tritium_hdu_3.png)

### K = 8
![K Means 8](images/kmeans_results/_kmeans_at_8_background_and_tritium_hdu_3.png)

### K = 9
![K Means 9](images/kmeans_results/_kmeans_at_9_background_and_tritium_hdu_3.png)

### K = 10
![K Means 10](images/kmeans_results/_kmeans_at_10_background_and_tritium_hdu_3.png)