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