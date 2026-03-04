#import cv2 as cv
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt

################################################################################################################
'''
Histogram Plotting Function

Args: 
    -- img: the numpy array that represents the image
    -- title: the name of the hisogram
    -- mask: if any, the mask applied to the image

Returns: 
    -- NONE: Just displays the plot
'''
################################################################################################################
def plot_color_histogram(img, title="Color Histogram", mask=None) : 
    colors = ('b', 'g', 'r')
    plt.figure()
    plt.title(title)
    plt.xlabel('Bins')
    plt.ylabel('# of Pixels')

    for i, col in enumerate(colors) : 
        hist = cv.calcHist([img], [i], mask, [256], [0, 256])
        plt.plot(hist, color=col)
        plt.xlim([0, 256])

    plt.show()