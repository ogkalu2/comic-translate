"""Utility functions for the imkit module."""

from __future__ import annotations
import numpy as np


# def ensure_uint8_rgb(arr: np.ndarray) -> np.ndarray:
#     """Ensure array is uint8 RGB format for PIL compatibility."""
#     arr = np.asarray(arr)
#     if arr.dtype != np.uint8:
#         arr = np.clip(arr, 0, 255).astype(np.uint8)
#     if arr.ndim == 2:
#         arr = np.stack([arr]*3, axis=-1)
#     if arr.shape[2] == 4:  # drop alpha
#         arr = arr[:, :, :3]
#     return arr

def ensure_uint8_rgb(arr: np.ndarray) -> np.ndarray:
    """Ensure array is uint8 RGB format for PIL compatibility."""
    arr = np.asarray(arr)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr