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
# Split Image into Color Channels
################################################################################################################
b, g, r = cv.split(img)     # displays each on in a gray-scale image depicting the intensities of the respective color

# print(img.shape)    # (701, 1051, 3)
# print(b.shape)      # (701, 1051)
# print(g.shape)      # (701, 1051)
# print(r.shape)      # (701, 1051)

################################################################################################################
# Merge Color Channels 
################################################################################################################
merged = cv.merge([b, g, r])       # should be identical to original image

################################################################################################################
# Split Image into Color Channels -- Draw Respective Colors (Shows colors rather than gray scale)
################################################################################################################
blank = np.zeros(img.shape[:2], dtype='uint8')

blue = cv.merge([b, blank, blank])      # display only blue channel
green = cv.merge([blank, g, blank])      # display only green channel
red = cv.merge([blank, blank, r])        # display only red channel

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Dog', img)

# cv.imshow('Blue', b)
# cv.imshow('Green', g)
# cv.imshow('Red', r)
# cv.imshow('Merged', merged)

# cv.imshow('Blue2', blue)
# cv.imshow('Green2', green)
# cv.imshow('Red2', red)

cv.waitKey(0)








################################################################################################################
# 
################################################################################################################