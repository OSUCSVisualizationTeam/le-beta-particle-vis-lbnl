# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed

import cv2 as cv
import numpy as np

# Rescale Function -- from basics.py
def rescaleFrame(frame, scale=0.50) : 
    # works with images, videos, and live videos
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    dims = (width, height)

    return cv.resize(frame, dims, interpolation=cv.INTER_AREA)

################################################################################################################
# Load Image
################################################################################################################
img = cv.imread('photos\\dog.jpg')  # dog is a large image -- rescale for better demo visualization
rescaled_img = rescaleFrame(img, 0.20)
img = rescaled_img

################################################################################################################
# Averaging
################################################################################################################
average = cv.blur(img, (3, 3))      # increase kernel size increases blur intensity

################################################################################################################
# Gaussian Blur
################################################################################################################
gauss = cv.GaussianBlur(img, (3, 3), 0)

################################################################################################################
# Median Blurring (Better at removing noise -- used for computer vision) 
################################################################################################################
median = cv.medianBlur(img, 3)      # not effective for large kernel sizes

################################################################################################################
# Bilateral Blurring 
################################################################################################################
bilateral = cv.bilateralFilter(img, 10, 35, 25)

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Average_Blur', average)
# cv.imshow('Gaussian_Blur', gauss)
# cv.imshow('Median_Blur', median)
# cv.imshow('Bilateral_Blur', bilateral)

cv.waitKey(0)