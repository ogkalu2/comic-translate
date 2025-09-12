"""
Speech bubble processing utilities.
"""
import numpy as np
import mahotas
from typing import Optional
import imkit as imk


def make_bubble_mask(frame: np.ndarray) -> np.ndarray:
    """
    Creates a binary mask of the largest contiguous area in an image,
    assumed to be a speech bubble interior. Handles both light and dark bubbles.
    
    Args:
        frame: Input image, expected to be a cropped region of a speech bubble.
    
    Returns:
        A boolean numpy array representing the bubble mask.
    """
    if frame is None or frame.size == 0:
        return np.zeros((1, 1), dtype=bool)

    gray = imk.to_gray(frame)
    
    # 2. Use Otsu's method to get a binary image.
    try:
        threshold = mahotas.thresholding.otsu(gray)
        # Initially, assume the bubble is light.
        binary_mask = (gray > threshold)
    except ValueError:
        return gray > gray.mean()

    # 3. Detect and correct for inverted (dark) bubbles.
    # Heuristic: If the selected region covers most of the image corners,
    # it's likely the background. In that case, we invert the mask.
    h, w = binary_mask.shape
    corners = [
        binary_mask[0, 0], binary_mask[0, w-1], 
        binary_mask[h-1, 0], binary_mask[h-1, w-1]
    ]
    # If 3 or more corners are 'True', we've probably masked the background.
    if sum(corners) >= 3:
        binary_mask = ~binary_mask

    # 4. Clean up the mask: fill holes and remove small noise.
    # A closing operation (dilate then erode) is good for filling small holes.
    # An opening operation (erode then dilate) is good for removing small objects.
    # We do closing first to make the bubble solid, then opening to remove other speckles.
    struct_elem = imk.get_structuring_element(imk.MORPH_ELLIPSE, (11, 11))
    cleaned_mask = imk.morphology_ex(binary_mask, imk.MORPH_CLOSE, struct_elem)
    cleaned_mask = imk.morphology_ex(cleaned_mask, imk.MORPH_OPEN, struct_elem)

    # 5. Find all connected regions (islands)
    labeled_mask, num_regions = mahotas.label(cleaned_mask)
    
    if num_regions < 1:
        return np.zeros_like(gray, dtype=bool)

    # 6. Find the largest region (excluding background which is label 0)
    sizes = mahotas.labeled.labeled_size(labeled_mask)
    if len(sizes) > 1:
        largest_label = np.argmax(sizes[1:]) + 1
        # Create a final mask with only the largest region
        return labeled_mask == largest_label
    else:
        # No regions found other than background
        return np.zeros_like(gray, dtype=bool)


def bubble_interior_bounds(
    frame_mask: np.ndarray, 
    shrink_percent: float = 0.07
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
