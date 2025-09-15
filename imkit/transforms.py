"""Image transformation operations for the imkit module."""

from __future__ import annotations
import numpy as np
import mahotas as mh
from PIL import Image, ImageDraw, ImageFilter
from typing import Optional, Sequence, Union
from .utils import ensure_uint8


def to_gray(img: np.ndarray) -> np.ndarray:
    """Grayscale conversion using Pillow."""
    if img.ndim == 3:
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)
        pil_img = Image.fromarray(img)
        gray = pil_img.convert("L")  # Pillow grayscale
        return np.array(gray, dtype=np.uint8)
    elif img.dtype != np.uint8:
        return img.astype(np.uint8)
    return img.copy()


def gaussian_blur(array: np.ndarray, radius: float = 1.0) -> np.ndarray:
    """Apply Gaussian blur to an image array."""
    im = Image.fromarray(ensure_uint8(array))
    return np.array(im.filter(ImageFilter.GaussianBlur(radius=radius)))


def resize(
    image: np.ndarray, 
    size: tuple[int, int], 
    mode: Image.Resampling = Image.Resampling.LANCZOS
) -> np.ndarray:
    """Resize an image array to the specified size."""
    w, h = size
    im = Image.fromarray(ensure_uint8(image))
    im = im.resize((w, h), resample=mode)
    return np.array(im)


def lut(array: np.ndarray, lookup_table: np.ndarray) -> np.ndarray:
    """
    Apply lookup table transformation.
    Replaces cv2.LUT functionality.
    
    Args:
        array: Input array
        lookup_table: Lookup table for transformation
        
    Returns:
        Transformed array
    """
    return lookup_table[array]


def merge_channels(channels: list) -> np.ndarray:
    """
    Merge separate channels into a multi-channel image.
    Replaces cv2.merge functionality.
    
    Args:
        channels: List of single-channel arrays
        
    Returns:
        Multi-channel array
    """
    return np.stack(channels, axis=-1)


def _monotone_chain(points: np.ndarray) -> np.ndarray:
    """Andrew's monotone chain convex hull. 
    Input Nx2 array, returns hull vertices CCW (no duplicate last point).
    """
    pts = np.asarray(points, dtype=np.float64)
    # Handle OpenCV-style contour format (N, 1, 2) -> (N, 2)
    if pts.ndim == 3 and pts.shape[1] == 1:
        pts = pts[:, 0, :]
    if pts.shape[0] <= 1:
        return pts.copy()
    # sort lexicographically by x then y
    pts_sorted = np.array(sorted(map(tuple, pts)))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts_sorted:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(tuple(p))
    upper = []
    for p in reversed(pts_sorted):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(tuple(p))
    hull = np.array(lower[:-1] + upper[:-1], dtype=np.float64)
    return hull


def min_area_rect(points, assume_hull=False):
    """
    Compute minimum-area bounding rectangle for a set of 2D points.

    Returns:
      rect, box
        rect = ((cx, cy), (w, h), angle) with same convention as cv2.minAreaRect:
            - angle in [-90, 0)
            - width <= height
        box = (4,2) array of corner points in the same order as cv2.boxPoints
    """
    pts = np.asarray(points, dtype=np.float64)
    if pts.size == 0:
        raise ValueError("no points")
    if not assume_hull:
        hull = _monotone_chain(pts)
    else:
        hull = pts.copy()

    m = hull.shape[0]
    if m == 0:
        raise ValueError("empty hull")
    if m == 1:
        x, y = hull[0]
        rect = ((x, y), (0.0, 0.0), 0.0)
        return rect
    if m == 2:
        (x0, y0), (x1, y1) = hull
        dx, dy = x1 - x0, y1 - y0
        angle = np.degrees(np.arctan2(dy, dx))
        width = np.hypot(dx, dy)
        height = 0.0
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

        # normalize to OpenCV convention
        if width > height:
            width, height = height, width
            angle += 90
        if angle < -90:
            angle += 180
        elif angle >= 0:
            angle -= 180

        rect = ((cx, cy), (width, height), angle)
        return rect

    # edges
    idx_next = (np.arange(m) + 1) % m
    edges = hull[idx_next] - hull[np.arange(m)]
    edge_len = np.hypot(edges[:, 0], edges[:, 1])
    valid = edge_len > 1e-12
    edges = edges[valid]
    edge_len = edge_len[valid]
    if edges.shape[0] == 0:
        x, y = hull[0]
        rect = ((x, y), (0.0, 0.0), 0.0)
        return rect, np.array([[x, y]] * 4, dtype=np.float32)

    ux = edges / edge_len[:, None]
    uy = np.column_stack((-ux[:, 1], ux[:, 0]))

    proj_x = hull.dot(ux.T)
    proj_y = hull.dot(uy.T)

    min_x = proj_x.min(axis=0)
    max_x = proj_x.max(axis=0)
    min_y = proj_y.min(axis=0)
    max_y = proj_y.max(axis=0)

    widths = max_x - min_x
    heights = max_y - min_y
    areas = widths * heights

    k = int(np.argmin(areas))
    best_ux = ux[k]
    best_uy = uy[k]

    cx_rot = 0.5 * (min_x[k] + max_x[k])
    cy_rot = 0.5 * (min_y[k] + max_y[k])
    center = np.dot([cx_rot, cy_rot], np.column_stack((best_ux, best_uy)).T)

    angle = float(np.degrees(np.arctan2(best_ux[1], best_ux[0])))
    width = float(widths[k])
    height = float(heights[k])

    # normalize to OpenCV convention
    if width > height:
        width, height = height, width
        angle += 90
    if angle < -90:
        angle += 180
    elif angle >= 0:
        angle -= 180

    rect = (tuple(center), (width, height), angle)

    return rect


def box_points(rect: tuple) -> np.ndarray:
    """
    Get corner points of a rotated rectangle.
    This is a pure numpy implementation that replaces cv2.boxPoints.
    
    The `rect` input is expected to be in the format returned by cv2.minAreaRect:
    ((center_x, center_y), (width, height), angle_in_degrees)
    
    Args:
        rect: A tuple containing the center, size, and angle of the rectangle.
        
    Returns:
        A NumPy array of shape (4, 2) with the 4 corner points.
    """
    # Unpack the rectangle data
    (center_x, center_y), (width, height), angle = rect
    center = np.array([center_x, center_y])
    
    # Convert the angle to radians
    # Note: cv2.minAreaRect returns angle in degrees in range [-90, 0)
    theta = np.deg2rad(angle)
    
    c, s = np.cos(theta), np.sin(theta)
    
    # Create the rotation matrix
    # This matrix is used to rotate points around the origin
    rotation_matrix = np.array([[c, -s], 
                                [s, c]])
    
    # Define the half-width and half-height
    half_w, half_h = width / 2, height / 2
    
    # Define the 4 corners of the box in its local, unrotated coordinate system (centered at origin)
    unrotated_points = np.array([
        [-half_w, -half_h], # Bottom-left
        [ half_w, -half_h], # Bottom-right
        [ half_w,  half_h], # Top-right
        [-half_w,  half_h]  # Top-left
    ])
    
    # Rotate the points around the origin
    # We use matrix multiplication (the @ operator)
    # The result is a 4x2 matrix of rotated points
    rotated_points = unrotated_points @ rotation_matrix.T
    
    # Translate the points to the rectangle's center
    box = rotated_points + center
    
    return box.astype(np.float32)


def fill_poly(
    image: np.ndarray,
    pts: Union[Sequence[np.ndarray], np.ndarray],
    color: int = 1
) -> np.ndarray:
    """
    Fills a polygon on an image using mahotas, after converting the polygon
    from the cv2 format.

    Args:
        image (np.ndarray): The canvas (image) on which to draw. This is
                            modified in-place by mahotas.
        pts (Union[Sequence[np.ndarray], np.ndarray]): Either:
                               - A list/sequence of polygons to fill (each polygon as NumPy array)
                               - A single polygon as NumPy array
                               Each polygon can be in either (N, 2) or (N, 1, 2) format with integer dtype.
                               Both formats are supported, similar to cv2.fillPoly.
        color (int, optional): The color value to fill the polygon with.
                               Defaults to 1.
    """
    
    # Handle single array input (convert to list for uniform processing)
    if isinstance(pts, np.ndarray):
        polygons = [pts]
    else:
        polygons = pts
    
    for polygon in polygons:
        # Handle both (N, 2) and (N, 1, 2) formats
        if polygon.ndim == 2 and polygon.shape[1] == 2:
            # Already in (N, 2) format
            reshaped_poly = polygon
        elif polygon.ndim == 3 and polygon.shape[1] == 1 and polygon.shape[2] == 2:
            # In (N, 1, 2) format, reshape to (N, 2)
            reshaped_poly = polygon.reshape(-1, 2)
        else:
            # Try a generic reshape that handles both cases
            reshaped_poly = polygon.reshape(-1, 2)

        # Swap x and y coordinates to convert from (x, y) to (y, x)
        mahotas_poly = reshaped_poly[:, ::-1]

        # mahotas.polygon.fill_polygon expects a list of (y,x) tuples
        mahotas_poly_list = list(map(tuple, mahotas_poly))
        mh.polygon.fill_polygon(mahotas_poly_list, image, color=color)

    return image


def connected_components(image: np.ndarray, connectivity: int = 4) -> tuple:
    """
    Connected components with mahotas.
    
    Args:
        image: Input binary image. Will be converted to boolean.
        connectivity: Connectivity (4 or 8)
        
    Returns:
        num_labels, labels matching cv2.connectedComponents format.
    """
    # 1. Create structuring element based on connectivity
    if connectivity == 8:
        Bc = np.ones((3, 3), dtype=bool)  # 8-connectivity
    else:
        Bc = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool) # 4-connectivity

    # 2. Perform the labeling
    # mh.label returns the labeled image and the number of objects (excluding background)
    labeled, num_labels = mh.label(image > 0, Bc=Bc)

    return num_labels, labeled


def connected_components_with_stats(image: np.ndarray, connectivity: int = 4) -> tuple:
    """
    Connected components with statistics using a vectorized mahotas implementation.
    
    Args:
        image: Input binary image. Will be converted to boolean.
        connectivity: Connectivity (4 or 8)
        
    Returns:
        Tuple of (num_labels, labels, stats, centroids) matching cv2.connectedComponentsWithStats format.
    """
    # 1. Create structuring element based on connectivity
    if connectivity == 8:
        Bc = np.ones((3, 3), dtype=bool)  # 8-connectivity
    else:
        Bc = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool) # 4-connectivity

    # 2. Perform the labeling
    # mh.label returns the labeled image and the number of objects (excluding background)
    labeled, num_labels = mh.label(image > 0, Bc=Bc)
    
    # If there are no objects, return early with the correct empty format
    if num_labels == 0:
        # Background only
        stats = np.array([[0, 0, image.shape[1], image.shape[0], image.size]], dtype=np.int32)
        centroids = np.array([[ (image.shape[1]-1)/2.0, (image.shape[0]-1)/2.0 ]], dtype=np.float64)
        return 0, labeled, stats, centroids

    # 3. Calculate statistics for all labels at once (including background label 0)
    # The output of these functions is an array where the index corresponds to the label.
    # e.g., sizes[3] is the area of the object with label 3.
    
    # Calculate Areas (pixel counts)
    sizes = mh.labeled.labeled_size(labeled)
    
    # Calculate Bounding Boxes
    # bboxes is in the format [ymin, ymax, xmin, xmax] for each label
    bboxes = mh.labeled.bbox(labeled)
    
    # Calculate Centroids
    # Create arrays where each pixel value is its own y or x coordinate
    h, w = labeled.shape
    yy, xx = np.indices((h, w), dtype=np.int64)
    
    # Sum the y and x coordinates for each label
    sums_y = mh.labeled.labeled_sum(yy, labeled)
    sums_x = mh.labeled.labeled_sum(xx, labeled)
    
    # Calculate centroids by dividing sums by the area.
    # Use np.divide to handle division by zero for any potential empty labels,
    # though mh.label should not produce them.
    # The OpenCV format is (x, y)
    cen_x = np.divide(sums_x, sizes, out=np.zeros_like(sums_x, dtype=float), where=sizes!=0)
    cen_y = np.divide(sums_y, sizes, out=np.zeros_like(sums_y, dtype=float), where=sizes!=0)
    centroids = np.stack([cen_x, cen_y], axis=1)

    # 4. Assemble the 'stats' array to match the OpenCV format
    # Format: [CC_STAT_LEFT, CC_STAT_TOP, CC_STAT_WIDTH, CC_STAT_HEIGHT, CC_STAT_AREA]
    ymin, ymax, xmin, xmax = bboxes.T
    width = xmax - xmin + 1
    height = ymax - ymin + 1
    
    # For labels with 0 area, their bbox is [0,0,0,0], making width/height 1. Fix this.
    width[sizes == 0] = 0
    height[sizes == 0] = 0
    
    stats = np.stack([xmin, ymin, width, height, sizes], axis=1).astype(np.int32)
    
    return num_labels, labeled, stats, centroids


def line(
    image: np.ndarray, 
    pt1: tuple, 
    pt2: tuple, 
    color: int, 
    thickness: int = 1
) -> np.ndarray:
    """
    Draw a line on an image using PIL.
    Replaces cv2.line functionality.
    
    Args:
        image: Target image
        pt1: First point (x, y)
        pt2: Second point (x, y)
        color: Line color
        thickness: Line thickness
        
    Returns:
        Image with line drawn
    """
    
    pil_image = Image.fromarray(ensure_uint8(image))
    draw = ImageDraw.Draw(pil_image)
    draw.line([pt1, pt2], fill=color, width=thickness)

    return np.array(pil_image)


def convert_scale_abs(
    array: np.ndarray, 
    alpha: float = 1.0, 
    beta: float = 0.0
) -> np.ndarray:
    """
    Convert array to absolute values with scaling.
    Replaces cv2.convertScaleAbs functionality.
    
    Args:
        array: Input array
        alpha: Scale factor (default 1.0)
        beta: Offset value (default 0.0)
        
    Returns:
        Scaled and converted array as uint8
    """
    # Apply scaling and offset
    scaled = array * alpha + beta
    
    # Convert to absolute values and clip to uint8 range
    abs_scaled = np.abs(scaled)
    clipped = np.clip(abs_scaled, 0, 255)
    
    return clipped.astype(np.uint8)


def threshold(
    array: np.ndarray, 
    thresh: float, 
    maxval: float = 255, 
    thresh_type: int = 0
) -> tuple[float, np.ndarray]:
    """
    Apply threshold to an array.
    Replaces cv2.threshold functionality.
    
    Args:
        array: Input array
        thresh: Threshold value
        maxval: Maximum value to use with thresholding type
        thresh_type: Thresholding type (0 = binary)
        
    Returns:
        Tuple of (threshold_value, thresholded_array)
    """
    if array.ndim == 3:
        array = to_gray(array)
    
    # Binary threshold (thresh_type = 0)
    result = np.where(array > thresh, maxval, 0).astype(np.uint8)
    
    return thresh, result


def otsu_threshold(array: np.ndarray) -> tuple[float, np.ndarray]:
    """
    Apply Otsu's automatic threshold using mahotas.
    
    Args:
        array: Input grayscale array
        
    Returns:
        Tuple of (threshold_value, thresholded_array)
    """
    if array.ndim == 3:
        array = to_gray(array)
    
    # Use mahotas Otsu thresholding
    thresh_val = mh.otsu(array)
    result = (array > thresh_val).astype(np.uint8) * 255
    
    return thresh_val, result


def rectangle(
    image: np.ndarray, 
    pt1: tuple, 
    pt2: tuple, 
    color: Optional[tuple|int], 
    thickness: int = 1
) -> np.ndarray:
    """
    Mimics cv2.rectangle() using PIL.ImageDraw.Draw.rectangle().

    Args:
        image (np.ndarray): The input image as a numpy array.
        pt1 (tuple): The top-left corner coordinates (x, y).
        pt2 (tuple): The bottom-right corner coordinates (x, y).
        color (tuple): The rectangle color in BGR format (e.g., (255, 0, 0) for blue).
        thickness (int, optional): The thickness of the line. 
                                  If a negative number (e.g., -1), the rectangle is filled.
                                  Defaults to 1.

    Returns:
        np.ndarray: The modified image as a numpy array.
    """
    # Create an ImageDraw object
    img_pil = Image.fromarray(ensure_uint8(image))
    draw = ImageDraw.Draw(img_pil)
    
    # Normalize color to what PIL expects depending on image mode.
    # Acceptable inputs:
    #  - int (grayscale or single-value for RGB)
    #  - tuple/list of length 1 (grayscale) or 3 (BGR order expected, will be converted to RGB)
    if color is None:
        color = 1

    mode = img_pil.mode  # e.g. 'L', 'RGB', 'RGBA'

    # Normalize numeric and sequence types
    if isinstance(color, int):
        if mode in ("RGB", "RGBA"):
            pil_color = (int(color),) * 3
        else:
            pil_color = int(color)
    elif isinstance(color, (tuple, list, np.ndarray)):
        col = tuple(int(x) for x in color)
        if len(col) == 3:
            # assume input is BGR (OpenCV-style) -> convert to RGB for PIL
            pil_color = (col[2], col[1], col[0])
        elif len(col) == 1:
            if mode in ("RGB", "RGBA"):
                v = col[0]
                pil_color = (v, v, v)
            else:
                pil_color = col[0]
        else:
            raise ValueError("Color tuple must have length 1 or 3 for grayscale or RGB images.")
    else:
        raise ValueError("Color must be an int or a tuple/list/ndarray of length 1 or 3.")

    if thickness == -1:
        # Draw a filled rectangle
        draw.rectangle([pt1, pt2], fill=pil_color)
    elif thickness > 0:
        # Draw an outlined rectangle with a specified width
        draw.rectangle([pt1, pt2], outline=pil_color, width=thickness)

    return np.array(img_pil)


def add_weighted(
    src1: np.ndarray, 
    alpha: float, 
    src2: np.ndarray, 
    beta: float, 
    gamma: float
) -> np.ndarray:
    """
    Implements cv2.addWeighted() using NumPy.

    Args:
        src1 (np.ndarray): First input array.
        alpha (float): Weight for the first array elements.
        src2 (np.ndarray): Second input array.
        beta (float): Weight for the second array elements.
        gamma (float): Scalar added to the weighted sum.

    Returns:
        np.ndarray: The weighted sum of the two arrays, with the same data type
                    as the input arrays, and values clipped to the valid range.
    """
    # Ensure src1 and src2 have the same dimensions and data type.
    if src1.shape != src2.shape:
        raise ValueError("Input arrays must have the same shape.")

    # Perform the weighted sum using NumPy.
    # Arithmetic operations will be performed on floats to prevent overflow
    # before the final saturation.
    weighted_sum = (alpha * src1.astype(np.float64) +
                    beta * src2.astype(np.float64) +
                    gamma)

    # Re-cast to the original data type and clip values to handle saturation.
    # This prevents the modulo arithmetic behavior of standard NumPy integer operations.
    output = np.clip(weighted_sum,
                     np.iinfo(src1.dtype).min,
                     np.iinfo(src1.dtype).max)

    return output.astype(src1.dtype)