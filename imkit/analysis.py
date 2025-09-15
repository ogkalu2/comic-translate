"""Image analysis operations for the imkit module."""

from __future__ import annotations
import numpy as np
from PIL import Image, ImageDraw



# neighbors in clockwise order
_NEIGH = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
# 3x3 lookup table for neighbor index: NEI_MAP[dy+1, dx+1] -> index 0..7
_NEI_MAP = np.full((3, 3), -1, dtype=np.int8)
for idx, (di, dj) in enumerate(_NEIGH):
    _NEI_MAP[di + 1, dj + 1] = idx

def _as_mask(img, threshold: int = 0):
    a = np.asarray(img)
    if a.ndim == 3:
        a = a[..., 0]
    # use uint8 or bool; uint8 keeps parity with many libs
    return (a > threshold).astype(np.uint8)

def _trace_border_fast(
    pad_mask: np.ndarray, 
    start_i: int, 
    start_j: int, 
    prev_i: int, 
    prev_j: int,
    max_steps: int = 2_000_000
) -> np.ndarray:
    """
    findContours-style border tracing that matches OpenCV ordering (Suzuki-style start tests + tracing).
    Returns list of contours, each an (N,1,2) int array of (x,y) coordinates.
    Roughly equivalent to cv2.findContours(img, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE).

    Parameters
    ----------
    img : array-like
        Grayscale or 2D array-like image (or already a boolean mask). Values > threshold are foreground.
    threshold : int
        Threshold to create binary mask.
    """
    NEI = _NEIGH
    NEI_MAP = _NEI_MAP

    p_i = start_i; p_j = start_j
    b_i = prev_i; b_j = prev_j

    # store coords in separate lists (faster than repeatedly creating tuples)
    xs = [p_j - 1]
    ys = [p_i - 1]

    # find first neighbor q
    di = b_i - p_i; dj = b_j - p_j
    # bounds safe because di,dj in {-1,0,1}
    b_idx = int(NEI_MAP[di + 1, dj + 1]) if (0 <= di + 1 < 3 and 0 <= dj + 1 < 3) else 7
    search_start = (b_idx + 1) & 7

    found = False
    for k in range(8):
        idx = (search_start + k) & 7
        ndi, ndj = NEI[idx]
        ni = p_i + ndi; nj = p_j + ndj
        if pad_mask[ni, nj]:
            q_i, q_j = ni, nj
            found = True
            break
    if not found:
        return np.vstack((np.array(xs, dtype=int), np.array(ys, dtype=int))).T

    xs.append(q_j - 1); ys.append(q_i - 1)
    b_i, b_j = p_i, p_j
    p_i, p_j = q_i, q_j
    first_next_i, first_next_j = p_i, p_j

    steps = 0
    while True:
        steps += 1
        if steps > max_steps:
            break

        di = b_i - p_i; dj = b_j - p_j
        b_idx = int(NEI_MAP[di + 1, dj + 1]) if (0 <= di + 1 < 3 and 0 <= dj + 1 < 3) else 7
        search_start = (b_idx + 1) & 7

        found_q = False
        for k in range(8):
            idx = (search_start + k) & 7
            ndi, ndj = NEI[idx]
            ni = p_i + ndi; nj = p_j + ndj
            if pad_mask[ni, nj]:
                q_i, q_j = ni, nj
                found_q = True
                break
        if not found_q:
            break

        # termination
        if (p_i == start_i and p_j == start_j and q_i == first_next_i and q_j == first_next_j):
            break

        # append if different from last appended
        if q_j - 1 != xs[-1] or q_i - 1 != ys[-1]:
            xs.append(q_j - 1); ys.append(q_i - 1)

        b_i, b_j = p_i, p_j
        p_i, p_j = q_i, q_j

    return np.vstack((np.array(xs, dtype=int), np.array(ys, dtype=int))).T


def find_contours(img, threshold: int = 0):
    mask = _as_mask(img, threshold)
    # pad once to avoid bounds checks
    p = np.pad(mask, 1, mode='constant', constant_values=0).astype(np.uint8)
    visited = np.zeros_like(p, dtype=bool)
    contours = []

    # vectorized start detection on the inner region (avoids scanning every pixel in Python)
    center = p[1:-1, 1:-1]
    left = p[1:-1, :-2]
    right = p[1:-1, 2:]
    outer = (center == 1) & (left == 0)
    hole  = (center == 1) & (right == 0)
    start_mask = outer | hole
    starts = np.column_stack(np.nonzero(start_mask))  # row, col in inner coords
    if starts.size == 0:
        return [], None
    # convert to padded coordinates
    starts[:, 0] += 1
    starts[:, 1] += 1

    for i, j in starts:
        if visited[i, j]:
            continue
        if p[i, j] != 1:
            continue
        if p[i, j - 1] == 0:
            prev_i, prev_j = i, j - 1
        elif p[i, j + 1] == 0:
            prev_i, prev_j = i, j + 1
        else:
            continue

        contour = _trace_border_fast(p, int(i), int(j), int(prev_i), int(prev_j))
        if contour.size == 0:
            continue

        # vectorized marking of visited
        xs = contour[:, 0].astype(np.intp)
        ys = contour[:, 1].astype(np.intp)
        visited[ys + 1, xs + 1] = True

        contours.append(contour.reshape(-1, 1, 2))

    return contours, None


def bounding_rect(contour: np.ndarray) -> tuple[int, int, int, int]:
    """OpenCV-style boundingRect replacement.

    Args:
        contour: np.ndarray shape (N,1,2) or (N,2) of integer point coords.
    Returns:
        (x, y, w, h) with +1 pixel width/height to match cv2.boundingRect behavior.
    """
    if contour.ndim == 3 and contour.shape[1] == 1:
        pts = contour.reshape(-1, 2)
    else:
        pts = contour.reshape(-1, 2)
    xs = pts[:, 0]
    ys = pts[:, 1]
    x_min = int(xs.min())
    y_min = int(ys.min())
    x_max = int(xs.max())
    y_max = int(ys.max())
    return x_min, y_min, x_max - x_min + 1, y_max - y_min + 1


def contour_area(contour: np.ndarray):
    """
    Calculates the area of a polygon defined by a contour using the Shoelace formula.
    
    Args:
        contour (np.ndarray): A NumPy array of shape (N, 1, 2) or (N, 2)
                              containing the (x, y) coordinates of the contour's vertices.
    
    Returns:
        float: The absolute area of the polygon.
    """
    # Reshape the contour array to (N, 2) if it has the OpenCV (N, 1, 2) shape
    if contour.ndim == 3 and contour.shape[1] == 1:
        contour = contour.squeeze(axis=1)

    x = contour[:, 0]
    y = contour[:, 1]
    
    # Use np.roll to implement the cyclic sum required by the formula
    area = 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    return area


def draw_contours(
    image: np.ndarray, 
    contours: list, 
    contour_idx: int, 
    color: tuple, 
    thickness: int = 1
) -> np.ndarray:
    """
    Emulates cv2.drawContours using Pillow and Numpy.

    Args:
        image (np.ndarray): The target image (numpy array, e.g., (H, W, 3) for RGB).
        contours (list): A list of contours, where each contour is a numpy array
                         of (x, y) coordinates, e.g., [[[x1, y1]], [[x2, y2]], ...].
        contour_idx (int): Index of the contour to draw (-1 for all).
        color (tuple): The fill or line color in RGB format, e.g., (255, 0, 0).
        thickness (int): Line thickness. Use -1 for a filled contour.

    Returns:
        np.ndarray: The image with contours drawn on it.
    """
    # Convert numpy array to PIL Image for drawing
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)
    
    pil_image = Image.fromarray(image.copy())
    draw = ImageDraw.Draw(pil_image)

    # Determine which contours to draw
    contours_to_draw = []
    if contour_idx == -1:
        contours_to_draw = contours
    elif 0 <= contour_idx < len(contours):
        contours_to_draw = [contours[contour_idx]]
    
    # Process and draw each contour
    for contour in contours_to_draw:
        # Reformat the numpy contour array for PIL
        # Example: from [[[x1, y1]], [[x2, y2]], ...] to [(x1, y1), (x2, y2), ...]
        if contour.size > 0:
            points = tuple(map(tuple, contour.reshape(-1, 2)))
            
            if thickness == -1:
                # Use ImageDraw.polygon for filled contours
                draw.polygon(points, fill=color)
            else:
                # Approximate a thick line by drawing multiple thin lines
                draw.line(points, fill=color, width=thickness, joint="curve")

    # Convert the PIL image back to a numpy array
    return np.array(pil_image)


def get_perspective_transform(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """
    Calculates the 3x3 perspective transform matrix using a vectorized
    NumPy implementation.
    """
    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError("Source and destination must be 4x2 arrays.")

    # A is the 8x8 matrix
    A = np.zeros((8, 8))
    
    # Unpack source and destination points
    xs, ys = src[:, 0], src[:, 1]
    xd, yd = dst[:, 0], dst[:, 1]

    # Fill the even rows of A
    A[::2, 0] = xs
    A[::2, 1] = ys
    A[::2, 2] = 1
    A[::2, 6] = -xs * xd
    A[::2, 7] = -ys * xd

    # Fill the odd rows of A
    A[1::2, 3] = xs
    A[1::2, 4] = ys
    A[1::2, 5] = 1
    A[1::2, 6] = -xs * yd
    A[1::2, 7] = -ys * yd
    
    # b is the 8x1 vector, which is just the destination points flattened
    b = dst.ravel()

    # Solve for the 8 unknowns
    try:
        # Use solve, which is generally faster and more stable for this
        h = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        raise ValueError("Matrix is singular, cannot compute perspective transform.")

    # Reshape h into the 3x3 matrix H (the last element is 1)
    H = np.append(h, 1).reshape((3, 3))
    return H


def warp_perspective(
    image: np.ndarray, 
    matrix: np.ndarray, 
    output_size: tuple
) -> np.ndarray:
    """
    Performs a perspective warp using PIL/Pillow.
    
    Args:
        image (np.ndarray): The input image.
        matrix (np.ndarray): The 3x3 perspective transformation matrix.
        output_size (tuple): The (width, height) of the output image.

    Returns:
        np.ndarray: The warped image as a numpy array.
    """
    # Pillow's transform method also requires the inverse matrix.
    H_inv = np.linalg.inv(matrix)
    
    # The `data` argument for PERSPECTIVE is a tuple of the first 8
    # elements of the inverse matrix, divided by the last element.
    coeffs = H_inv.flatten() / H_inv.flatten()[-1]
    pil_img = Image.fromarray(image)
    transformed = pil_img.transform(
        output_size,
        Image.Transform.PERSPECTIVE,
        data=coeffs,
        resample=Image.Resampling.BILINEAR  # High-quality resampling
    )

    return np.array(transformed)


def mean(src: np.ndarray, mask: np.ndarray | None = None) -> tuple:
    """
    Compute mean value similar to cv2.mean(), returning a 4-element tuple.

    Args:
        src (np.ndarray): The input array (image).
        mask (np.ndarray, optional): An optional 8-bit, single-channel mask.
                                     Pixels corresponding to non-zero mask values
                                     are included in the mean calculation.

    Returns:
        tuple: A 4-element tuple containing the mean of each channel, or zeros
               for channels not present in the input.
    """
    a = np.asarray(src)
    num_channels = a.shape[2] if a.ndim == 3 else 1
    mean_values = np.zeros(4, dtype=np.float64)

    if mask is None:
        if a.ndim == 2:
            mean_values[0] = a.mean()
        else:
            mean_values[:num_channels] = a.mean(axis=(0, 1))
    else:
        m = (np.asarray(mask) > 0)
        
        # If no pixels are masked, return all zeros
        if not m.any():
            return tuple(mean_values)

        if a.ndim == 2:
            mean_values[0] = a[m].mean()
        else:
            # Reshape the mask to broadcast across all channels
            m_3d = m[..., np.newaxis]
            # Use boolean indexing on the 3D array
            masked_pixels = a[m_3d.repeat(num_channels, axis=2)]
            # Reshape back and calculate the mean for each channel
            masked_pixels = masked_pixels.reshape(-1, num_channels)
            mean_values[:num_channels] = masked_pixels.mean(axis=0)

    return tuple(mean_values)