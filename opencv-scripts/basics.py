# Note: If wanting to run basics.py, change PATH_TO_IMAGE to the file path to the image you want to use
import cv2 as cv
from utilities.image_tools import rescaleFrame, load_img

################################################################################################################
# rescale function
################################################################################################################
# Called from a custom package (see utilities/imgae_tools.py for reference)

################################################################################################################
# Read Image
################################################################################################################
# img = cv.imread('PATH_TO_IMAGE')
# img = cv.imread('photos\\dog.jpg')
img = load_img('photos\\dog.jpg')

################################################################################################################
# Rescale Image (via rescaleFrame)
################################################################################################################
rescaled_img = rescaleFrame(img, 0.10)
# img = rescaled_img       # use rescaled image for following example because original img is very large

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
# cv.imshow('NAME_OF_IMAGE', img)
# cv.imshow('Dog', img)
cv.imshow('Rescaled_Dog', rescaled_img)
# cv.imshow('Blurred_Dog', blur)
# cv.imshow('Canny_Edges1', canny1)
# cv.imshow('Canny_Edges2', canny2)
# cv.imshow('Dilated_Dog', dilated)
# cv.imshow('Eroded_Dog', eroded)
# cv.imshow('Resized_Dog', resized)

# To save results into a folder e.g. results/...
# cv.imwrite('results\\rescaled_dog.png', rescaled_img)
# cv.imwrite('results\\blurred_dog.png', blur)
# cv.imwrite('results\\canny_edges_dog.png', canny1)
# cv.imwrite('results\\dialted_dog.png', rescaled_img)
# cv.imwrite('results\\eroded_dog.png', rescaled_img)
# cv.imwrite('results\\resized_dog.png', rescaled_img)

# uncomment the images wanting to be displayed when script is ran

# click any key to exit out of the running process
cv.waitKey(0)