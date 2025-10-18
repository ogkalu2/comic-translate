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
