"""Helpers for image enhancement.

This module defines a registry of simple image enhancement functions that can
improve comic scan quality prior to text detection.  Enhancements include
denoising, sharpening and optional super‑resolution.  Functions operate on
``numpy`` arrays in HxWxC format and return arrays of the same shape.

The default enhancer implemented here performs a two‑step upsample/denoise/
sharpen/downsample procedure using Pillow.  Upsampling and downsampling with
Lanczos resampling tends to preserve edges while smoothing out compression
artifacts.  Median filtering removes isolated noise pixels and the built‑in
sharpen filter accentuates line art.  This approach does not depend on any
external machine learning models and thus works out of the box.

If more sophisticated enhancers are available (e.g. via waifu2x, nunif or
Real‑ESRGAN), they can be added here and registered in ``get_enhancer`` by
name.  Each enhancer should accept and return a NumPy array.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)


def enhance_basic(img: np.ndarray) -> np.ndarray:
    """
    Basic image enhancement routine.

    This function performs a simple quality enhancement by:

    * Converting the input ``numpy`` array into a Pillow image.
    * Upscaling the image by 2× using the Lanczos filter.
    * Applying a median filter to reduce salt‑and‑pepper noise.
    * Sharpening the image to accentuate edges.
    * Downscaling back to the original resolution.

    The final output has the same dimensions as the input but with reduced
    noise and crisper line art.  This is a computationally inexpensive
    operation that avoids altering aspect ratio or coordinate mapping.

    Parameters
    ----------
    img :
        A NumPy array of shape (H, W, C) representing an RGB image.

    Returns
    -------
    np.ndarray
        An enhanced version of the input image.
    """
    # Ensure we have an unsigned integer type image.  Most upstream callers
    # supply uint8 arrays; if not, cast accordingly.
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)

    # Convert to PIL image; assume RGB ordering
    pil_img = Image.fromarray(img, mode="RGB")
    width, height = pil_img.size

    # Upscale with Lanczos interpolation.  Doubling resolution helps the
    # subsequent filters operate in a finer space, which improves denoising.
    upscaled = pil_img.resize((width * 2, height * 2), Image.LANCZOS)

    # Apply a median filter to reduce isolated noise.  A 3×3 kernel is a good
    # compromise between smoothing and edge preservation.
    denoised = upscaled.filter(ImageFilter.MedianFilter(size=3))

    # Sharpen the image.  Pillow's built‑in sharpen filter subtly enhances edges
    # without introducing strong halos.
    sharpened = denoised.filter(ImageFilter.SHARPEN)

    # Downscale back to the original resolution to keep coordinate mappings
    # consistent with the rest of the pipeline.
    final = sharpened.resize((width, height), Image.LANCZOS)

    # Convert back to NumPy array
    return np.array(final)


def enhance_waifu2x(img: np.ndarray) -> np.ndarray:
    """
    Attempt to enhance an image using waifu2x or a compatible library.

    This is a placeholder implementation.  If a waifu2x Python binding is
    installed in the environment, this function will invoke it to upscale and
    denoise the input.  If waifu2x is unavailable, it falls back to the basic
    enhancer defined above.

    Parameters
    ----------
    img :
        A NumPy array of shape (H, W, C) representing an RGB image.

    Returns
    -------
    np.ndarray
        An enhanced version of the input image.  If waifu2x cannot be used,
        the result will be produced by :func:`enhance_basic`.
    """
    try:
        # Attempt to import a hypothetical waifu2x binding.  The actual API may
        # differ; adjust accordingly if a real library is installed.
        from waifu2x import Waifu2x

        model = Waifu2x(scale=2, noise=2, mode="photo")
        enhanced = model.process(img)
        # Downscale back to original resolution to preserve coordinate space
        if enhanced.shape[0] != img.shape[0] or enhanced.shape[1] != img.shape[1]:
            pil_enhanced = Image.fromarray(enhanced.astype(np.uint8), mode="RGB")
            pil_resized = pil_enhanced.resize(
                (img.shape[1], img.shape[0]), Image.LANCZOS
            )
            return np.array(pil_resized)
        return enhanced
    except Exception as exc:
        # If anything goes wrong (e.g. waifu2x not installed), log and fallback.
        logger.warning("Waifu2x enhancement failed: %s", exc)
        return enhance_basic(img)


def get_enhancer(name: Optional[str]) -> Optional[Callable[[np.ndarray], np.ndarray]]:
    """
    Retrieve an enhancer function by name.

    Parameters
    ----------
    name :
        The name of the enhancer as selected in the settings.  Case‑insensitive.

    Returns
    -------
    Callable or None
        A function that accepts and returns a NumPy array, or ``None`` if no
        enhancement should be applied.
    """
    if not name:
        return None
    normalized = name.lower()
    if normalized in {"none", "off", "disable", "disabled"}:
        return None
    if normalized in {"basic", "simple", "default"}:
        return enhance_basic
    if normalized in {"waifu2x", "waifu2x-cunet", "waifu2xphoto"}:
        return enhance_waifu2x
    # Unknown enhancer names result in no enhancement
    logger.warning("Unknown enhancer '%s'; no enhancement will be applied.", name)
    return None
