# Note: If wanting to run basics.py, change PATH_TO_IMAGE to the file path to the image you want to use
import cv2 as cv

################################################################################################################
# rescale function
################################################################################################################
def rescaleFrame(frame, scale=0.50) : 
    # works with images, videos, and live videos
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    dims = (width, height)

    return cv.resize(frame, dims, interpolation=cv.INTER_AREA)

################################################################################################################
# Read Image
################################################################################################################
img = cv.imread('PATH_TO_IMAGE')    # for example 'photos/dog.jpg

################################################################################################################
# Rescale Image (via rescaleFrame)
################################################################################################################
rescaled_img = rescaleFrame(img)

################################################################################################################
# Gray Scale
################################################################################################################
gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

################################################################################################################
# Blur Image
################################################################################################################
blur = cv.GaussianBlur(rescaled_img, (7,7), cv.BORDER_DEFAULT)

################################################################################################################
# Create Edge Cascade (via Canny)
################################################################################################################
canny1 = cv.Canny(img, 125, 175)
canny2 = cv.Canny(blur, 125, 175)   # remove more edges by passing a blurred img

################################################################################################################
# Dialate Image 
################################################################################################################
dilated = cv.dilate(img, (7,7), iterations=3)

################################################################################################################
# Erode Image
################################################################################################################
eroded = cv.erode(img, (3,3), iterations=1)

################################################################################################################
# Resizing Image (NOTE: DIFFERENT FROM RESCALING -- ASPECT RATIO NOT KEPT)
################################################################################################################
resized = cv.resize(img, (500,500), interpolation=cv.INTER_AREA)     # does not keep aspect ratio
# INTER_AREA -- for resizing to smaller
# INTER_LINEAR or INTER_CUBIC for resizing to larger

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('NAME_OF_IMAGE', img)
# cv.imshow('NAME_OF_IMAGE', rescaled_img)
# cv.imshow('NAME_OF_IMAGE', blur)
# cv.imshow('NAME_OF_IMAGE', canny1)
# cv.imshow('NAME_OF_IMAGE', canny2)
# cv.imshow('NAME_OF_IMAGE', dilated)
# cv.imshow('NAME_OF_IMAGE', eroded)
# cv.imshow('NAME_OF_IMAGE', resized)

# uncomment the images wanting to be displayed when script is ran

# click any key to exit out of the running process
cv.waitKey(0)