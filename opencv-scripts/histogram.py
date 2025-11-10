# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed

import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
from utilities.image_tools import rescaleFrame, load_img
from utilities.graphing_tools import plot_color_histogram

################################################################################################################
# Load Image
################################################################################################################
img = load_img('photos\\dog.jpg')  # dog is a large image -- rescale for better demo visualization
rescaled_img = rescaleFrame(img, 0.20)
img = rescaled_img

################################################################################################################
# Gray-Scale Histogram
################################################################################################################
gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
gray_hist = cv.calcHist([gray], [0], None, [256], [0, 256])

################################################################################################################
# Histogram on Masked Image
################################################################################################################
blank = np.zeros(img.shape[:2], dtype='uint8')
circle = cv.circle(blank, (img.shape[1]//2 - 30, img.shape[0]//2), 200, 255, -1)
mask = cv.bitwise_and(gray, gray, mask=circle)

gray_hist_mask = cv.calcHist([gray], [0], mask, [256], [0, 256])

################################################################################################################
# Color Histogram
################################################################################################################
blank2 = np.zeros(img.shape[:2], dtype='uint8')
mask2 = cv.circle(blank2, (img.shape[1]//2 - 30, img.shape[0]//2), 200, 255, -1)
masked2 = cv.bitwise_and(img, img, mask=mask2)


################################################################################################################
# Show/Display Images/Histograms
################################################################################################################
# cv.imshow('Dog', img)

################################################################################################################
# Full Gray Scale Histogram
# cv.imshow('Gray', gray)

# plt.figure()
# plt.title('Grayscale Histogram')
# plt.xlabel('Bins')
# plt.ylabel('# of Pixels')
# plt.plot(gray_hist)
# plt.xlim([0, 256])
# plt.show()

################################################################################################################
# Masked Gray Scale Histogram
# cv.imshow('Mask', mask)
# plt.figure()
# plt.title('Grayscale Histogram')
# plt.xlabel('Bins')
# plt.ylabel('# of Pixels')
# plt.plot(gray_hist_mask)
# plt.xlim([0, 256])
# plt.show()

################################################################################################################
# Color Histogram (No Mask)
plot_color_histogram(img)

################################################################################################################
# Color Histogram (No Mask)
plot_color_histogram(img, 'Color Histogram 2', mask2)

cv.waitKey(0)
 
# NOTE: Histograms allow for graphical visualization of pixel intensity distributions