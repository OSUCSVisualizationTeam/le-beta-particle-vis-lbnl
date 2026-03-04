import cv2 as cv
import numpy as np

blank = np.zeros((400, 400), dtype='uint8')
rectangle = cv.rectangle(blank.copy(), (30, 30), (370, 370), 255, -1)
circle = cv.circle(blank.copy(), (200, 200), 200, 255, -1)

################################################################################################################
# Bitwise AND -- Intersecting Regions
################################################################################################################
bitwise_and = cv.bitwise_and(rectangle, circle)

################################################################################################################
# Bitwise OR -- Non-Intersecting and Intersecting Regions
################################################################################################################
bitwise_or = cv.bitwise_or(rectangle, circle)

################################################################################################################
# Bitwise XOR -- Non-Intersecting Regions
################################################################################################################
bitwise_xor = cv.bitwise_xor(rectangle, circle)

################################################################################################################
# Bitwise NOT -- Inverts Binary Color
################################################################################################################
bitwise_not = cv.bitwise_not(rectangle)
bitwise_not2 = cv.bitwise_not(circle)

################################################################################################################
# Show/Display Image
################################################################################################################
cv.imshow('Rectangle', rectangle)
cv.imshow('Circle', circle)
cv.imshow('Bitwise_AND', bitwise_and)
cv.imshow('Bitwise_OR', bitwise_or)
cv.imshow('Bitwise_XOR', bitwise_xor)
cv.imshow('Rect_NOT', bitwise_not)
cv.imshow('Circle_NOT', bitwise_not2)

cv.waitKey(0)