# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed

import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt

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
# Simple Thresholding
################################################################################################################
gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
threshold, thresh = cv.threshold(gray, 200, 255, cv.THRESH_BINARY)

################################################################################################################
# Simple Thresholding -- Inverse
################################################################################################################
threshold2, thresh2 = cv.threshold(gray, 200, 255, cv.THRESH_BINARY_INV)

################################################################################################################
# Adaptive Thresholding -- Computer finds optimal threshold value 
################################################################################################################
adaptive_thresh = cv.adaptiveThreshold(gray, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY, 11, 3)
# adaptive_thresh = cv.adaptiveThreshold(gray, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY_INV, 11, 3)     # can also get the inverse using this methods as well
# adaptive_thresh = cv.adaptiveThreshold(gray, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 11, 3)     # do not necessarily need to use the mean

################################################################################################################
# Show/Display Images
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Gray', gray)
# cv.imshow('Simple_Threshold', thresh)
# cv.imshow('Simple_Threshold_Inverse', thresh2)
# cv.imshow('Adaptive_Threshold', adaptive_thresh)

cv.waitKey(0)
