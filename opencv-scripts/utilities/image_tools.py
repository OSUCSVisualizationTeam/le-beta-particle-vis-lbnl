import cv2 as cv
import numpy as np

################################################################################################################
'''
Resize Function

Args: 
    -- frame: numpy array (uint8/uint16/etc..)
    -- scale: scale factor, where the default value is 0.5, halving the dimensions

Returns: 
    -- the resized frame
'''
################################################################################################################
def rescaleFrame(frame, scale=0.50) : 
    if frame is None:
        raise ValueError("rescale_frame: 'frame' is None.")
    if scale <= 0:
        raise ValueError("rescale_frame: 'scale' must be > 0.")

    # works with images, videos, and live videos
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    dims = (width, height)

    return cv.resize(frame, dims, interpolation=cv.INTER_AREA)