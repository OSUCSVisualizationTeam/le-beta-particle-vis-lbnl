# OpenCV Experiments

## Scripts
```
basics.py
bitwise.py
contours.py
gradients.py
histogram.py
masking.py
smoothing.py
spaces.py
splitmerge.py
thresholding.py
transformations.py
```

## Common Definitions/Terminologies
- **contours** -- list of all coordinates of the contours found in the img
- **hierarchies** -- hierarchical representation of the contours

- **RETR_LIST** -- return/finds all contours
- **RETR_EXTERNAL** -- return/finds all external contours
- **RETR_TREE** -- return all hierarchical contours

- **CHAIN_APPROX_NONE** -- returns all contours (does nothing)
- **CHAIN_APPROX_SIMPLE** -- compresses all contours that are returned that is most simple

## Notes
All scripts have most of the image display commented out. Before running a program, **UNCOMMENT** the desired images you want to see.

## Results

### Original/Rescaled Image (Keeps Aspect Ratio)
![Rescaled Dog](results/rescaled_dog.png)

### Resized Dog (Does Not Keep Aspect Ratio)
![Resized Dog](results/resized_dog.png)

### Average Blurring
![Average Blur Dog](results/avg_blur_dog.png)

### Bi-Lateral Blurring (Not Drastic Changes)
![Bilateral Blur Dog](results/bilateral_blur_dog.png)

### Gaussian Blurring (Not Drastic Changes)
![Gaussian Dog](results/gaussian_blur_dog.png)

### Median Blurring (Not Drastic Changes)
![Median Blur Dog](results/median_blur_dog.png)

### Canny Edges
![Canny Edges Dog](results/canny_edges_dog.png)

### Sobel X Edges 
![SobelX Dog](results/sobelx_dog.png)

### Sobel Y Edges
![SobelY Dog](results/sobely_dog.png)

### Combined Sobel (X + Y) Edges
![Combined Sobel Dog](results/combiend_sobel_dog.png)

### Laplacian Edges
![Laplacian Dog](results/laplacian_dog.png)

### Thresholding
![Thresholding Dog](results/threshold_dog.png)

### Inverse Thresholding
![Inverse Thresholding Dog](results/inverse_threshold_dog.png)

### Adaptive Thresholding
![Adaptive Thresholding Dog](results/adaptive_thresholding_dog.png)

### HSV Color Channel
![HSV Dog](results/hsv_dog.png)

### RGB Color Channel
![RGB Dog](results/rgb_dog.png)

### LAB Color Channel 
![LAB Dog](results/lab_dog.png)

### Blue Color Isolated
![Blue Dog](results/blue_dog.png)

### Green Color Isolated
![Green Dog](results/green_dog.png)

### Red Color Isolated
![Red Dog](results/red_dog.png)

### Masking
![Masked Dog](results/masked_dog.png)