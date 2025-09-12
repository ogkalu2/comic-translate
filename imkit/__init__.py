"""
Images module providing a unified interface for image processing operations.

This module replaces select cv2 functionality with PIL, mahotas, and numpy-based implementations.
Uses the pattern: import imkit as imk, then imk.function_name()
"""

# Import all functions to provide the imk.function_name interface
from .io import (
    read_image,
    write_image,
    encode_image,
    decode_image,
)

from .transforms import (
    to_gray,
    gaussian_blur,
    resize,
    convert_scale_abs,
    threshold,
    otsu_threshold,
    lut,
    merge_channels,
    min_area_rect,
    box_points,
    fill_poly,
    connected_components,
    connected_components_with_stats,
    line,
    rectangle,
)

# Constants to match cv2 connected components stats indices
CC_STAT_LEFT = 0
CC_STAT_TOP = 1
CC_STAT_WIDTH = 2
CC_STAT_HEIGHT = 3
CC_STAT_AREA = 4


from .morphology import (
    dilate,
    erode,
    get_structuring_element,
    morphology_ex,

    MORPH_CROSS,
    MORPH_ELLIPSE,
    MORPH_RECT,

    MORPH_OPEN,
    MORPH_CLOSE, 
    MORPH_GRADIENT,
    MORPH_TOPHAT,
    MORPH_BLACKHAT,
)

from .analysis import (
    find_contours,
    bounding_rect,
    contour_area,
    draw_contours,
    get_perspective_transform,
    warp_perspective,
)

# Re-export all functions for the imk.function_name pattern
__all__ = [
    # I/O operations
    'read_image',
    'write_image', 
    'encode_image',
    'decode_image',
    
    # Transformations
    'to_gray',
    'gaussian_blur',
    'resize',
    'convert_scale_abs',
    'threshold',
    'otsu_threshold',
    'lut',
    'merge_channels',
    'min_area_rect',
    'box_points',
    'fill_poly',
    'connected_components',
    'connected_components_with_stats',
    'line',
    'rectangle',
    
    # Constants
    'CC_STAT_LEFT',
    'CC_STAT_TOP', 
    'CC_STAT_WIDTH',
    'CC_STAT_HEIGHT',
    'CC_STAT_AREA',

    # Morphological operation constants
    'MORPH_RECT',
    'MORPH_CROSS',
    'MORPH_ELLIPSE',

    'MORPH_OPEN',
    'MORPH_CLOSE',
    'MORPH_GRADIENT',
    'MORPH_TOPHAT',
    'MORPH_BLACKHAT',

    # Morphological operations
    'dilate',
    'erode',
    'get_structuring_element',
    'morphology_ex',
    
    # Analysis operations
    'find_contours',
    'bounding_rect',
    'contour_area',
    'draw_contours',
    'get_perspective_transform',
    'warp_perspective',
]