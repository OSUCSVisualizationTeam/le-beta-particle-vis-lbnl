# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed
# Contours -- Can be used for shape analysis, and object detect/recognition

import cv2 as cv
import numpy as np
from utilities.image_tools import rescaleFrame

################################################################################################################
# Load Image
################################################################################################################
img = cv.imread('photos\\dog.jpg')  # dog is a large image -- rescale for better demo visualization
rescaled_img = rescaleFrame(img, 0.20)
img = rescaled_img  

################################################################################################################
# METHOD 1: Find Contours (Multi-Step) via canny (RECOMMENDED AS PRIMARY OPTION)
################################################################################################################
# 1. Get a gray-scaled visualization of the image
gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

# 1.5 Blur image before finding edges (OPTIONAL)
blur = cv.GaussianBlur(gray, (5, 5), cv.BORDER_DEFAULT)

# 2. Retrieve the edges via Canny
canny = cv.Canny(img, 125, 175)
# canny = cv.Canny(blur, 125, 175)    # reduction in edges/contours when blurring the image

# 3. Use findContours() function
contours, hierarchies = cv.findContours(canny, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)      # -- the function looks at structuring elements (edges found in the image), and returns 2 values
# contours -- list of all coordinates of the contours found in the img
# hierarchies -- hierarchical representation of the contours

# RETR_LIST -- return/finds all contours
# RETR_EXTERNAL -- return/finds all external contours
# RETR_TREE -- return all hierarchical contours

# CHAIN_APPROX_NONE -- returns all contours (does nothing)
# CHAIN_APPROX_SIMPLE -- compresses all contours that are returned that is most simple

# print(f'Total Contours Found: {len(contours)}')     # in the 'dog.jpg' example there are 625 contours found (using CHAIN_APPROX_NONE)

################################################################################################################
# METHOD 2: FINDING CONTOURS (Multi-Step) via threshold
################################################################################################################

# 1. REPEAT AS IN METHOD 1 -- Getting Gray-scale

# 2. Use threshold() function
ret, thresh = cv.threshold(gray, 125, 255, cv.THRESH_BINARY)      # in this example: if a intensity of a pixel is below 125, it is set to black, if above 125 it is set to white (255)

# 3. Use findContours() function via passing threshold
contours2, hierarchies2 = cv.findContours(thresh, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)

# print(f'Total Contours Found: {len(contours2)}')     # in the 'dog.jpg' example there are 469 contours found (using CHAIN_APPROX_NONE)

################################################################################################################
# Visualize Contours By Drawing
################################################################################################################
# Create a blank image (same dims of original image)
blank = np.zeros(img.shape, dtype='uint8')

# draw contours onto blank image
# cv.drawContours(blank, contours, -1, (0, 0, 255), 1)
cv.drawContours(blank, contours2, -1, (0, 0, 255), 1)

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Gray_Scale_Dog', gray)
# cv.imshow('Blur_Dog', blur)
# cv.imshow('Canny_Edges', canny)
# cv.imshow('Threshold_Img', thresh)
# cv.imshow('Drawn_Contours', blank)

cv.waitKey(0)

# NOTE: From a programming POV, canny CAN be seen as the edges of an image (even though by definition they are NOT the same)