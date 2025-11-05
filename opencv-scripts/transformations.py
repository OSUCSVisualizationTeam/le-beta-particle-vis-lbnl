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
# Translation
################################################################################################################
# translation function
def translate(img, x, y) :
    transMat = np.float32([[1,0,x], [0,1,y]])
    dims = (img.shape[1], img.shape[0])
    return cv.warpAffine(img, transMat, dims)

# -x --> Left
# -y --> Up
# x --> Right
# y --> Down

translated = translate(img, 100, 100)   # this example shifts the image to the right by 100 and down by 100 pixels
# translated2 = translate(img, -100, -100)   # this example shifts the image to the left by 100 and up by 100 pixels

################################################################################################################
# Rotation
################################################################################################################
# rotation function
def rotate(img, angle, rotPoint=None) : 
    (height, width) = img.shape[:2]
    if rotPoint is None : 
        roPoint = (width//2, height//2)
    rotMat = cv.getRotationMatrix2D(rotPoint, angle, 1.0)
    dims = (width, height)
    return cv.warpAffine(img, rotMat, dims)

rotated = rotate(img, 45)   # rotates the image by 45 degrees

################################################################################################################
# Flipping Image
################################################################################################################
flip = cv.flip(img, 0)
# 1 -- horizontal flip, 0 -- vertical flip, -1 -- both vertical and horizontal flip

################################################################################################################
# Cropping Image
################################################################################################################
cropped = img[0:500, 300:650]

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Translation_Img', translated)
# cv.imshow('Translation_Img_2', translated2)
# cv.imshow('Rotated_Img', rotated)
# cv.imshow('Flipped_Img', flip)
# cv.imshow('Cropped_Img', cropped)
# uncomment the images wanting to be displayed when script is ran

cv.waitKey(0)