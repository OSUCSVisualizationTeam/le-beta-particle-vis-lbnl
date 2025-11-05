# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed

import cv2 as cv

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
# BGR to Gray Scale
################################################################################################################ 
gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

################################################################################################################
# BGR to HSV
################################################################################################################
hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)

################################################################################################################
# BGR to LAB (L*A*B)
################################################################################################################
lab = cv.cvtColor(img, cv.COLOR_BGR2LAB)

################################################################################################################
# BGR to RGB (OpenCV uses BGR and matplotlib uses RGB) -- helpful in needing to use matplotlib 
# and openCV together
################################################################################################################
rgb = cv.cvtColor(img, cv.COLOR_BGR2RGB)

################################################################################################################
# HSV to BGR (Inverse of BGR to HSV)
################################################################################################################
hsv_to_bgr = cv.cvtColor(hsv, cv.COLOR_HSV2BGR)     # should be identical to original image

################################################################################################################
# LAB to BGR (Inverse of BGR to LAB)
################################################################################################################
lab_to_bgr = cv.cvtColor(lab, cv.COLOR_LAB2BGR)     # should be identical to original image

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Gray-Scale', gray)
# cv.imshow('HSV Img', hsv)
# cv.imshow('LAB Img', lab)
# cv.imshow('RGB_Img', rgb)
# cv.imshow('HSV-To-BGR', hsv_to_bgr)
# cv.imshow('LAB-To-BGR', lab_to_bgr)

cv.waitKey(0)

# NOTE: Limitations -- Cannot convert Gray-Scale Images to HSV Images directly
    # Work Around -- Convert Grayscale to BGR, and then convert resulting BGR to HSV
        # Steps:
        # 1. Gray Scale --> BGR
        # 2. BGR --> HSV 

    # Idea: Route color space operations through BGR as all functions will work for BGR