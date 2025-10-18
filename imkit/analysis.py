"""Image analysis operations for the imkit module."""

from __future__ import annotations
import numpy as np
from PIL import Image, ImageDraw



DI_ARR = np.array([-1, -1, 0, 1, 1, 1, 0, -1], dtype=np.int32)
DJ_ARR = np.array([ 0,  1, 1, 1, 0,-1,-1, -1], dtype=np.int32)

def _as_mask(img, threshold: int = 0):
    a = np.asarray(img)
    if a.ndim == 3:
        a = a[..., 0]
    # use uint8 or bool; uint8 keeps parity with many libs
    return (a > threshold).astype(np.uint8)

def _trace_border_fast(
    m: memoryview,
    W: int, 
    start_i: int, 
    start_j: int, 
    max_steps: int = 2_000_000
) -> np.ndarray:
    # Local hoists
    OFF = (-W, -W + 1, 1, W + 1, W, W - 1, -1, -W - 1)
    mv = m; o = OFF

    start_pos = start_i * W + start_j

    # mark "start-candidate consumed" if left neighbor is background
    if mv[start_pos - 1] == 0:
        mv[start_pos] = 2

    # initial backtrack idx for "entered from left" = index of (0, -1) which is 6 in your ordering
    b_idx = 6

    # find first neighbor
    s = (b_idx + 1) & 7
    p = start_pos
    if   mv[p + o[s]]:             q_idx = s
    elif mv[p + o[(s + 1) & 7]]:   q_idx = (s + 1) & 7
    elif mv[p + o[(s + 2) & 7]]:   q_idx = (s + 2) & 7
    elif mv[p + o[(s + 3) & 7]]:   q_idx = (s + 3) & 7
    elif mv[p + o[(s + 4) & 7]]:   q_idx = (s + 4) & 7
    elif mv[p + o[(s + 5) & 7]]:   q_idx = (s + 5) & 7
    elif mv[p + o[(s + 6) & 7]]:   q_idx = (s + 6) & 7
    elif mv[p + o[(s + 7) & 7]]:   q_idx = (s + 7) & 7
    else:
        # isolated pixel
        out = np.empty((1, 2), dtype=np.int32)
        out[0, 0] = start_j - 1
        out[0, 1] = start_i - 1
        return out

    # prepare chain accumulation
    codes = bytearray()
    pos = p + o[q_idx]
    first_next_pos = pos
    codes.append(q_idx)
    b_idx = (q_idx + 4) & 7

    steps = 1
    while True:
        if steps > max_steps: break
        # mark start-candidate if left neighbor is background
        if mv[pos - 1] == 0:
            mv[pos] = 2

        s = (b_idx + 1) & 7
        p = pos
        # neighbor scan (unrolled)
        if   mv[p + o[s]]:             q_idx = s
        elif mv[p + o[(s + 1) & 7]]:   q_idx = (s + 1) & 7
        elif mv[p + o[(s + 2) & 7]]:   q_idx = (s + 2) & 7
        elif mv[p + o[(s + 3) & 7]]:   q_idx = (s + 3) & 7
        elif mv[p + o[(s + 4) & 7]]:   q_idx = (s + 4) & 7
        elif mv[p + o[(s + 5) & 7]]:   q_idx = (s + 5) & 7
        elif mv[p + o[(s + 6) & 7]]:   q_idx = (s + 6) & 7
        elif mv[p + o[(s + 7) & 7]]:   q_idx = (s + 7) & 7
        else:
            break

        next_pos = p + o[q_idx]

        # OpenCV/Suzuki termination: back at start, and next equals first_next
        if p == start_pos and next_pos == first_next_pos:
            break

        codes.append(q_idx)
        pos = next_pos
        b_idx = (q_idx + 4) & 7
        steps += 1

    # reconstruct coordinates
    if not codes:
        out = np.empty((1, 2), dtype=np.int32)
        out[0, 0] = start_j - 1
        out[0, 1] = start_i - 1
        return out

    code_arr = np.frombuffer(codes, dtype=np.uint8)
    # map directions to steps and cumsum
    dx = DJ_ARR[code_arr]
    dy = DI_ARR[code_arr]
    out = np.empty((code_arr.size + 1, 2), dtype=np.int32)
    out[0, 0] = start_j - 1
    out[0, 1] = start_i - 1
    out[1:, 0] = out[0, 0] + np.cumsum(dx, dtype=np.int32)
    out[1:, 1] = out[0, 1] + np.cumsum(dy, dtype=np.int32)
    return out

def find_contours(img, threshold: int = 0):
    m = _as_mask(img, threshold)              # produce 0/1 uint8
    if m.dtype != np.uint8:
        m = m.astype(np.uint8, copy=False)

    p = np.pad(m, 1, mode='constant', constant_values=0)
    p_u8 = p  # already uint8
    H, W = p.shape

    center = p_u8[1:-1, 1:-1]
    left   = p_u8[1:-1, :-2]
    start_mask = center & (1 - left)
    starts_flat = np.flatnonzero(start_mask)

    mv = memoryview(p_u8).cast('B')

    contours = []
    W0 = W - 2
    for k in starts_flat:
        r = k // W0
        c = k - r * W0
        i = 1 + r
        j = 1 + c
        pos = i * W + j

        # still pristine?
        if mv[pos] != 1:
            continue

        contour = _trace_border_fast(mv, W, int(i), int(j))
        if contour.size == 0:
            continue
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
        resample=Image.Resampling.BICUBIC
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