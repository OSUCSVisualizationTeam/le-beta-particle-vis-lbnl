from enum import Enum
from PySide6.QtGui import QPixmap, QImage
import numpy as np
from typing import Optional

class Colormap(str, Enum):
    """Available colormaps for false-color visualization."""
    VIRIDIS = "viridis"
    PLASMA = "plasma"
    INFERNO = "inferno"
    MAGMA = "magma"
    JET = "jet"
    BONE = "bone"
    HOT = "hot"
    COOL = "cool"

def get_cv2_colormap_id(name: str) -> int:
    """
    Returns the OpenCV colormap ID for the given string name.
    Lazily imports cv2 to ensure headless compatibility.
    """
    import cv2
    
    mapping = {
        Colormap.VIRIDIS: cv2.COLORMAP_VIRIDIS,
        Colormap.PLASMA: cv2.COLORMAP_PLASMA,
        Colormap.INFERNO: cv2.COLORMAP_INFERNO,
        Colormap.MAGMA: cv2.COLORMAP_MAGMA,
        Colormap.JET: cv2.COLORMAP_JET,
        Colormap.BONE: cv2.COLORMAP_BONE,
        Colormap.HOT: cv2.COLORMAP_HOT,
        Colormap.COOL: cv2.COLORMAP_COOL,
    }
    # Default to Viridis if unknown
    return mapping.get(name, cv2.COLORMAP_VIRIDIS)

def generate_gradient_pixmap(name: str, width: int = 20, height: int = 256) -> QPixmap:
    """
    Generates a vertical gradient QPixmap for the specified colormap.
    Used for UI widgets (legends/sliders).
    """
    import cv2
    
    # Create a grayscale ramp (0..255)
    # Shape: (height, width)
    # We want 255 at top or bottom? 
    # Usually slider min (0) is bottom. So gradient should go 0->255 bottom-up.
    # OpenCV image origin is Top-Left. 
    # So row 0 is top. We want row 0 to be Max (255) and row 255 to be Min (0)?
    # Or standard: 0 at index 0.
    # Let's create a ramp 0..255.
    ramp = np.linspace(255, 0, height, dtype=np.uint8) # 255 (Top) to 0 (Bottom)
    ramp = np.tile(ramp[:, np.newaxis], (1, width)) # Expand to width
    
    # Apply colormap
    cmap_id = get_cv2_colormap_id(name)
    color_img = cv2.applyColorMap(ramp, cmap_id)
    
    # BGR -> RGB
    color_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)
    
    # Convert to QImage
    h, w, ch = color_img.shape
    bytes_per_line = ch * w
    q_img = QImage(color_img.data, w, h, bytes_per_line, QImage.Format_RGB888)
    
    # Return copy
    return QPixmap.fromImage(q_img.copy())
