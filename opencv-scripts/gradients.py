# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed

import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
from utilities.image_tools import rescaleFrame, load_img

################################################################################################################
# Load Image
################################################################################################################
img = load_img('photos\\dog.jpg')  # dog is a large image -- rescale for better demo visualization
rescaled_img = rescaleFrame(img, 0.20)
img = rescaled_img

gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

################################################################################################################
# Laplacian
################################################################################################################
lap = cv.Laplacian(gray, cv.CV_64F)     # computes the gradient of the image 
lap = np.uint8(np.absolute(lap))        # addresses negative values resulting from laplacian

################################################################################################################
# Sobel
################################################################################################################
sobelx = cv.Sobel(gray, cv.CV_64F, 1, 0)
sobely = cv.Sobel(gray, cv.CV_64F, 0, 1)

# combining both sobels
combined_sobel = cv.bitwise_or(sobelx, sobely)

################################################################################################################
# Canny (Multi-Stage Process) -- used in previous examples
################################################################################################################
canny = cv.Canny(gray, 150, 175)

################################################################################################################
# Show/Display Images
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Gray', gray)
# cv.imshow('Laplacian', lap)
# cv.imshow('Sobel_X', sobelx)
# cv.imshow('Sobel_Y', sobely)
# cv.imshow('Combined_Sobel', combined_sobel)
# cv.imshow('Canny', canny)

cv.waitKey(0)

# Canny Edge Detector is a more clean edge detector, however sobel is also used alot