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
![HDU 3 Original](images/original/background_and_tritium_hdu_3_image.png)

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