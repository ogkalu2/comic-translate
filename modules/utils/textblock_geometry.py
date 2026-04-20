from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .textblock import TextBlock


def sort_blk_list(blk_list: list[TextBlock], right_to_left=True) -> list[TextBlock]:
    # Sort blk_list from right to left, top to bottom
    sorted_blk_list = []
    for blk in sorted(blk_list, key=lambda blk: blk.center[1]):
        for i, sorted_blk in enumerate(sorted_blk_list):
            if blk.center[1] > sorted_blk.xyxy[3]:
                continue
            if blk.center[1] < sorted_blk.xyxy[1]:
                sorted_blk_list.insert(i + 1, blk)
                break

            # y center of blk inside sorted_blk so sort by x instead
            if right_to_left and blk.center[0] > sorted_blk.center[0]:
                sorted_blk_list.insert(i, blk)
                break
            if not right_to_left and blk.center[0] < sorted_blk.center[0]:
                sorted_blk_list.insert(i, blk)
                break
        else:
            sorted_blk_list.append(blk)
    return sorted_blk_list


def adjust_text_line_coordinates(coords, width_expansion_percentage: int, height_expansion_percentage: int, img: np.ndarray):
    top_left_x, top_left_y, bottom_right_x, bottom_right_y = coords
    im_h, im_w, _ = img.shape

    # Calculate width, height, and respective expansion offsets
    width = bottom_right_x - top_left_x
    height = bottom_right_y - top_left_y
    width_expansion_offset = int(((width * width_expansion_percentage) / 100) / 2)
    height_expansion_offset = int(((height * height_expansion_percentage) / 100) / 2)

    # Define the rectangle origin points (bottom left, top right) with expansion/contraction
    new_x1 = max(top_left_x - width_expansion_offset, 0)
    new_y1 = max(top_left_y - height_expansion_offset, 0)
    new_x2 = min(bottom_right_x + width_expansion_offset, im_w)
    new_y2 = min(bottom_right_y + height_expansion_offset, im_h)

    return new_x1, new_y1, new_x2, new_y2


def adjust_blks_size(blk_list: list[TextBlock], img: np.ndarray, w_expan: int = 0, h_expan: int = 0):
    for blk in blk_list:
        coords = blk.xyxy
        expanded_coords = adjust_text_line_coordinates(coords, w_expan, h_expan, img)
        blk.xyxy[:] = expanded_coords
