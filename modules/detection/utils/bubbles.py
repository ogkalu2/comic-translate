"""
Speech bubble processing utilities.
"""
import numpy as np
import mahotas
from typing import Optional
import imkit as imk



def adjust_contrast_brightness(img: np.ndarray, contrast: float = 1.0, brightness: int = 0):
    """
    Adjusts contrast and brightness of an uint8 image.
    
    Args:
        img: Input image
        contrast: Contrast adjustment factor
        brightness: Brightness adjustment value
    
    Returns:
        Adjusted image
    """
    brightness += int(round(255 * (1 - contrast) / 2))
    return imk.add_weighted(img, contrast, img, 0, brightness)


def make_bubble_mask(frame: np.ndarray):
    """
    Create a mask for speech bubbles.
    
    Args:
        frame: Input image
    
    Returns:
        Bubble mask
    """
    image = frame.copy()
    # Apply a Gaussian blur to reduce noise
    blurred = imk.gaussian_blur(image, 1.1)

    # Use the Canny edge detection algorithm
    edges = mahotas.sobel(imk.to_gray(blurred))

    # Find contours in the image
    contours, _ = imk.find_contours(edges)

    # Create a black image with the same size as the original
    stage_1 = imk.draw_contours(np.zeros_like(image), contours, -1, (255, 255, 255), thickness=2)
    stage_1 = np.bitwise_not(stage_1)
    stage_1 = imk.to_gray(stage_1)
    _, binary_image = imk.threshold(stage_1, 200, 255)

    # Find connected components in the binary image
    num_labels, labels = imk.connected_components(binary_image)
    largest_island_label = np.argmax(np.bincount(labels.flat)[1:]) + 1
    mask = np.zeros_like(image)
    mask[labels == largest_island_label] = 255

    _, mask = imk.threshold(mask, 200, 255)

    # Apply morphological operations to remove black spots
    kernel = imk.get_structuring_element(imk.MORPH_ELLIPSE, (3, 3))
    mask = imk.morphology_ex(mask, imk.MORPH_OPEN, kernel)

    return adjust_contrast_brightness(mask, 100)


def bubble_interior_bounds(
    frame_mask: np.ndarray, 
    shrink_percent: float = 0.15
) -> Optional[tuple[int, int, int, int]]:
    """
    Finds an interior bounding box for a bubble from its binary mask 
    by shrinking the overall bounding box of the mask.

    Args:
        frame_mask: A boolean numpy array representing the bubble mask.
        shrink_percent: The percentage to shrink the bounding box by on each side.

    Returns:
        A tuple (x1, y1, x2, y2) for the interior bounds, or None if not found.
    """
    if not frame_mask.any():
        return None
        
    # Get the bounding box of the white region in the mask
    ymin, ymax, xmin, xmax = mahotas.bbox(frame_mask)
    
    height, width = ymax - ymin, xmax - xmin
    if height <= 0 or width <= 0:
        return None

    # Shrink the box to get an "interior" rectangle
    dx = int(width * shrink_percent)
    dy = int(height * shrink_percent)
    
    ix1, iy1 = xmin + dx, ymin + dy
    ix2, iy2 = xmax - dx, ymax - dy
    
    # Ensure the shrunk box still has a positive area
    if ix2 <= ix1 or iy2 <= iy1:
        # If shrinkage is too aggressive, return the original bounding box
        return int(xmin), int(ymin), int(xmax), int(ymax)

    return int(ix1), int(iy1), int(ix2), int(iy2)
