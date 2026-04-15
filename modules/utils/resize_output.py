"""Post-processing output resize for HD Strategy.

When the user selects HD Strategy "Resize", the final output image should be
resized so that its longer side does not exceed the configured resize_limit.
This is applied *after* all processing (inpainting, text rendering) is complete,
at save/export time.

The existing "Resize Before Inpaint" logic in modules/inpainting/base.py is
NOT affected by this module.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import imkit as imk
from PIL import Image

if TYPE_CHECKING:
    from app.ui.settings.settings_page import SettingsPage

logger = logging.getLogger(__name__)


def apply_output_resize(
    image: np.ndarray,
    settings_page: SettingsPage,
) -> np.ndarray:
    """Apply HD Strategy Resize to a final output image (post-processing).

    If the HD Strategy is set to "Resize" and the image's longer side
    exceeds the configured ``resize_limit``, the image is proportionally
    downscaled using BICUBIC interpolation.

    Args:
        image: RGB numpy array ``[H, W, C]``.
        settings_page: The application's SettingsPage instance used to
            read the current HD Strategy settings.

    Returns:
        The (potentially resized) image as an ``np.ndarray``.  If the
        strategy is not "Resize" or the image is already within the
        limit, the *original* array reference is returned unchanged.
    """
    if image is None:
        logger.debug("apply_output_resize: image is None, skipping.")
        return image

    try:
        strategy_settings = settings_page.get_hd_strategy_settings()
    except Exception:
        logger.debug("Could not read HD strategy settings; skipping output resize.", exc_info=True)
        return image

    strategy = strategy_settings.get("strategy", "")

    # Normalize the (possibly translated) strategy label back to its
    # canonical English key using the UI's value_mappings dict.  This
    # makes the comparison bulletproof regardless of the active locale.
    value_mappings = getattr(settings_page.ui, "value_mappings", {})
    canonical_strategy = value_mappings.get(strategy, strategy)

    is_resize = canonical_strategy == "Resize" or strategy == "Resize"

    logger.info(
        "apply_output_resize: strategy=%r, canonical=%r, is_resize=%s",
        strategy, canonical_strategy, is_resize,
    )

    if not is_resize:
        logger.info("apply_output_resize: strategy is not Resize, skipping.")
        return image

    resize_limit = int(strategy_settings.get("resize_limit", 0))
    if resize_limit <= 0:
        logger.warning(
            "apply_output_resize: resize_limit=%d is invalid, skipping resize.",
            resize_limit,
        )
        return image

    h, w = image.shape[:2]
    longer_side = max(h, w)

    if longer_side <= resize_limit:
        logger.info(
            "apply_output_resize: image (%d, %d) already within limit=%d, no resize needed.",
            w, h, resize_limit,
        )
        return image

    ratio = resize_limit / longer_side
    new_w = int(w * ratio + 0.5)
    new_h = int(h * ratio + 0.5)

    logger.info(
        "apply_output_resize: resizing (%d, %d) -> (%d, %d) [limit=%d, ratio=%.4f]",
        w, h, new_w, new_h, resize_limit, ratio,
    )

    resized = imk.resize(image, (new_w, new_h), mode=Image.Resampling.BICUBIC)
    return resized


def apply_width_limit_resize(
    image: np.ndarray,
    settings_page: SettingsPage,
) -> np.ndarray:
    """Scale the output image so its width matches a configured target value.

    This is **independent** of the HD Strategy Resize feature.  It reads
    the "Limit Output Width" toggle and target width from the Export
    settings and resizes the image proportionally (height adapts to
    maintain the aspect ratio).

    Args:
        image: RGB numpy array ``[H, W, C]``.
        settings_page: The application's SettingsPage instance used to
            read the current Export settings.

    Returns:
        The (potentially resized) image as an ``np.ndarray``.  If the
        feature is disabled or the image already matches the target
        width, the *original* array reference is returned unchanged.
    """
    if image is None:
        return image

    try:
        export_settings = settings_page.get_export_settings()
    except Exception:
        logger.debug(
            "apply_width_limit_resize: could not read export settings; skipping.",
            exc_info=True,
        )
        return image

    if not export_settings.get("limit_output_width", False):
        logger.debug("apply_width_limit_resize: feature disabled, skipping.")
        return image

    target_width = int(export_settings.get("output_width_limit", 0))
    if target_width <= 0:
        logger.warning(
            "apply_width_limit_resize: target_width=%d is invalid, skipping.",
            target_width,
        )
        return image

    h, w = image.shape[:2]
    if w == target_width:
        logger.info(
            "apply_width_limit_resize: image width %d already matches target, no resize needed.",
            w,
        )
        return image

    ratio = target_width / w
    new_w = target_width
    new_h = int(h * ratio + 0.5)

    logger.info(
        "apply_width_limit_resize: resizing (%d, %d) -> (%d, %d) [target_width=%d, ratio=%.4f]",
        w, h, new_w, new_h, target_width, ratio,
    )

    resized = imk.resize(image, (new_w, new_h), mode=Image.Resampling.BICUBIC)
    return resized
