from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from .textblock import TextBlock


def visualize_textblocks(canvas, blk_list: list[TextBlock]):
    """Visualize text blocks using PIL."""
    # Convert numpy array to PIL Image
    if isinstance(canvas, np.ndarray):
        if canvas.dtype != np.uint8:
            canvas = canvas.astype(np.uint8)
        if len(canvas.shape) == 3:
            pil_image = Image.fromarray(canvas)
        else:
            pil_image = Image.fromarray(canvas, mode='L').convert('RGB')
    else:
        pil_image = canvas

    draw = ImageDraw.Draw(pil_image)
    lw = max(round(sum(canvas.shape) / 2 * 0.003), 2)  # line width

    for i, blk in enumerate(blk_list):
        bx1, by1, bx2, by2 = blk.xyxy
        draw.rectangle([bx1, by1, bx2, by2], outline=(127, 255, 127), width=lw)

        for j, line in enumerate(blk.lines):
            if len(line) > 0:
                draw.text(line[0], str(j), fill=(255, 127, 0))
                if len(line) > 1:
                    for k in range(len(line)):
                        start_point = tuple(line[k])
                        end_point = tuple(line[(k + 1) % len(line)])
                        draw.line([start_point, end_point], fill=(0, 127, 255), width=2)

        draw.text((bx1, by1 + lw), str(i), fill=(255, 127, 127))

    return np.array(pil_image)


def visualize_speech_bubbles(canvas, blk_list: list[TextBlock]):
    """Visualize speech bubbles using PIL."""
    if isinstance(canvas, np.ndarray):
        if canvas.dtype != np.uint8:
            canvas = canvas.astype(np.uint8)
        if len(canvas.shape) == 3:
            pil_image = Image.fromarray(canvas)
        else:
            pil_image = Image.fromarray(canvas, mode='L').convert('RGB')
    else:
        pil_image = canvas

    draw = ImageDraw.Draw(pil_image)
    lw = max(round(sum(canvas.shape) / 2 * 0.003), 2)

    class_colors = {
        'text_free': (255, 0, 0),
        'text_bubble': (0, 255, 0),
    }

    for blk in blk_list:
        if blk.bubble_xyxy is not None:
            bx1, by1, bx2, by2 = blk.bubble_xyxy
            color = class_colors.get(blk.text_class, (127, 255, 127))
            draw.rectangle([bx1, by1, bx2, by2], outline=color, width=lw)

    return np.array(pil_image)
