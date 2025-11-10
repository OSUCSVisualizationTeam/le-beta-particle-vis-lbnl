# NOTE: Uses 'photos\\dog.jpg' as the example img for the demo, it can be replaced with any path to an image if needed

import cv2 as cv
import numpy as np
from utilities.image_tools import rescaleFrame, load_img

################################################################################################################
# Load Image
################################################################################################################
img = load_img('photos\\dog.jpg')  # dog is a large image -- rescale for better demo visualization
rescaled_img = rescaleFrame(img, 0.20)
img = rescaled_img

################################################################################################################
# Masking (Multi-Step Process)
################################################################################################################
# 1. create blank image
blank = np.zeros(img.shape[:2], dtype='uint8')

# 2. create a shape on the blank image where we want to mask
mask = cv.circle(blank, (img.shape[1]//2 - 30, img.shape[0]//2), 200, 255, -1)

# 3. use bitwise AND to get the pixels in the circle from original image
masked = cv.bitwise_and(img, img, mask=mask)

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Dog', img)
# cv.imshow('Mask', mask)
# cv.imshow('Masked_Img', masked)

# cv.imwrite('results\\masked_dog.png', masked)

cv.waitKey(0)