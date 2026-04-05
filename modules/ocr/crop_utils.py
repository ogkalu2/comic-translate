from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from modules.utils.textblock import TextBlock, adjust_text_line_coordinates


@dataclass(frozen=True)
class OCRCrop:
    block_index: int
    crop: np.ndarray


def extract_block_crops(
    img: np.ndarray,
    blk_list: list[TextBlock],
    expansion_percentage: int = 5,
) -> tuple[list[OCRCrop], list[int]]:
    crops: list[OCRCrop] = []
    invalid_indices: list[int] = []

    if img is None or getattr(img, "size", 0) == 0:
        return crops, list(range(len(blk_list)))

    for block_index, blk in enumerate(blk_list):
        if getattr(blk, "bubble_xyxy", None) is not None:
            x1, y1, x2, y2 = blk.bubble_xyxy
        else:
            x1, y1, x2, y2 = adjust_text_line_coordinates(
                blk.xyxy,
                expansion_percentage,
                expansion_percentage,
                img,
            )

        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
        if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
            crop = img[y1:y2, x1:x2]
            if crop.size > 0:
                crops.append(OCRCrop(block_index=block_index, crop=crop))
                continue

        invalid_indices.append(block_index)

    return crops, invalid_indices
