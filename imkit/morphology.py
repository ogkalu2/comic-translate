"""Morphological operations for the imkit module."""

from __future__ import annotations
import numpy as np
import mahotas as mh


MORPH_RECT = 0
MORPH_CROSS = 1
MORPH_ELLIPSE = 2

MORPH_OPEN = 'open'
MORPH_CLOSE = 'close'
MORPH_GRADIENT = 'gradient'
MORPH_TOPHAT = 'tophat'
MORPH_BLACKHAT = 'blackhat'


def dilate(mask: np.ndarray, kernel: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Apply dilation morphological operation to a mask.
    
    Args:
        mask: Input mask
        kernel: a 2D numpy array kernel
        iterations: Number of iterations
    """
    se = (kernel > 0).astype(bool)
    out = mask.copy()
    for _ in range(iterations):
        out = mh.dilate(out, se)
    return (out > 0).astype(np.uint8)*255


def erode(mask: np.ndarray, kernel: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Apply erosion morphological operation to a mask.
    
    Args:
        mask: Input mask
        kernel: a 2D numpy array kernel
        iterations: Number of iterations
    """
    se = (kernel > 0).astype(bool)
    out = mask.copy()
    for _ in range(iterations):
        out = mh.erode(out, se)
    return (out > 0).astype(np.uint8)*255


def morphology_ex(image: np.ndarray, op: str, kernel: np.ndarray) -> np.ndarray:
    # Convert OpenCV kernel to Mahotas structuring element
    Bc = kernel.astype(bool)
    
    if op == MORPH_OPEN:  # cv2.MORPH_OPEN
        return mh.open(image, Bc)
    elif op == MORPH_CLOSE:  # cv2.MORPH_CLOSE
        return mh.close(image, Bc)
    elif op == MORPH_GRADIENT:  # cv2.MORPH_GRADIENT
        return mh.dilate(image, Bc) - mh.erode(image, Bc)
    elif op == MORPH_TOPHAT:  # cv2.MORPH_TOPHAT
        return image - mh.open(image, Bc)
    elif op == MORPH_BLACKHAT:  # cv2.MORPH_BLACKHAT
        return mh.close(image, Bc) - image
    else:
        raise ValueError(f"Unsupported operation: {op}")
    

def get_structuring_element(shape: int, ksize: tuple) -> np.ndarray:
    """
    OpenCV-like getStructuringElement using Mahotas.

    Parameters
    ----------
    shape : int
        One of MORPH_RECT, MORPH_CROSS, MORPH_ELLIPSE
    ksize : (h, w) tuple
        Size of the structuring element
    """
    h, w = ksize

    if shape == MORPH_RECT:
        # full ones
        elem = np.ones((h, w), dtype=bool)

    elif shape == MORPH_CROSS:
        elem = np.zeros((h, w), dtype=bool)
        elem[h//2, :] = True
        elem[:, w//2] = True

    elif shape == MORPH_ELLIPSE:
        # use Mahotas' disk
        # we approximate ellipse by a disk with radius = min(h, w)//2
        radius = min(h, w) // 2
        elem = mh.disk(radius, dim=2).astype(bool)

        # ensure output matches requested size
        # pad or crop to (h, w)
        ph = max(0, h - elem.shape[0])
        pw = max(0, w - elem.shape[1])
        elem = np.pad(elem,
                      ((ph//2, ph - ph//2), (pw//2, pw - pw//2)),
                      mode='constant')
        elem = elem[:h, :w]

    else:
        raise ValueError("Unknown shape flag")

    return elem