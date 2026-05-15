from __future__ import annotations

import imkit as imk
import numpy as np

from modules.utils.textblock import TextBlock


def annotate_blocks_with_heuristic_lines(
    image: np.ndarray,
    blocks: list[TextBlock],
) -> list[TextBlock]:
    if image is None or image.size == 0 or not blocks:
        return blocks

    height, width = image.shape[:2]
    for block in blocks:
        crop_box = _clamp_box(_expand_box(_to_box(block.xyxy), 4, 4, width, height), width, height)
        x1, y1, x2, y2 = crop_box
        if x2 <= x1 or y2 <= y1:
            block.lines = [crop_box]
            block.direction = _fallback_direction(crop_box, getattr(block, "source_lang", ""))
            continue

        crop = image[y1:y2, x1:x2]
        lines = _detect_lines_in_crop(crop, _projection_hint(_to_box(block.xyxy), getattr(block, "source_lang", "")))
        image_lines = [[line[0] + x1, line[1] + y1, line[2] + x1, line[3] + y1] for line in lines]

        direction = _infer_direction(image_lines, _to_box(block.xyxy), getattr(block, "source_lang", ""))
        block.lines = _sort_lines(image_lines, direction)
        block.direction = direction

    return blocks


def _detect_lines_in_crop(image: np.ndarray, direction_hint: str | None) -> list[list[int]]:
    height, width = image.shape[:2]
    if width <= 1 or height <= 1:
        return [[0, 0, max(0, width), max(0, height)]]

    gray = imk.to_gray(image)
    threshold, _ = imk.otsu_threshold(gray)
    histogram = np.bincount(gray.reshape(-1), minlength=256)
    fg_pixels = int(histogram[: int(threshold)].sum())
    bg_is_light = fg_pixels < (gray.size * 0.5)

    text_mask = gray < threshold if bg_is_light else gray > threshold
    x_sum = text_mask.sum(axis=0)
    y_sum = text_mask.sum(axis=1)
    is_horizontal_fallback = direction_hint == "horizontal" if direction_hint else width > height * 1.5

    tolerance_x = max(1, int(height * 0.02))
    tolerance_y = max(1, int(width * 0.02))

    spans: list[tuple[int, int, int, int]] = []
    if is_horizontal_fallback:
        start_y = -1
        for y in range(height):
            if int(y_sum[y]) > tolerance_y:
                if start_y == -1:
                    start_y = y
            elif start_y != -1:
                spans.append((0, start_y, width, y))
                start_y = -1
        if start_y != -1:
            spans.append((0, start_y, width, height))
    else:
        start_x = -1
        for x in range(width):
            if int(x_sum[x]) > tolerance_x:
                if start_x == -1:
                    start_x = x
            elif start_x != -1:
                spans.append((start_x, 0, x, height))
                start_x = -1
        if start_x != -1:
            spans.append((start_x, 0, width, height))

    boxes: list[list[int]] = []
    for sx1, sy1, sx2, sy2 in spans:
        region = text_mask[sy1:sy2, sx1:sx2]
        ys, xs = np.where(region)
        if xs.size == 0 or ys.size == 0:
            continue

        min_x = sx1 + int(xs.min())
        max_x = sx1 + int(xs.max())
        min_y = sy1 + int(ys.min())
        max_y = sy1 + int(ys.max())
        if (max_x - min_x) < 4 and (max_y - min_y) < 4:
            continue
        boxes.append([min_x, min_y, max_x, max_y])

    if not boxes:
        return [[0, 0, width, height]]
    return boxes


def _infer_direction(lines: list[list[int]], block_box: list[int], source_language: str) -> str:
    if lines:
        horizontal = 0.0
        vertical = 0.0
        for line in lines:
            width = max(1, line[2] - line[0])
            height = max(1, line[3] - line[1])
            horizontal += max(0.0, width / height - 1.0)
            vertical += max(0.0, height / width - 1.0)
        if vertical > horizontal * 1.15 + 0.2:
            return "vertical"
        if horizontal > vertical * 1.15 + 0.2:
            return "horizontal"

    union = _union_box(lines) if lines else block_box
    return _fallback_direction(union, source_language)


def _sort_lines(lines: list[list[int]], direction: str) -> list[list[int]]:
    if direction == "vertical":
        return sorted((list(map(int, line)) for line in lines), key=lambda box: (-box[0], box[1]))
    return sorted((list(map(int, line)) for line in lines), key=lambda box: (box[1], box[0]))


def _projection_hint(block: list[int], source_language: str) -> str | None:
    normalized = _normalize_source_language(source_language)
    if normalized == "ko":
        return "horizontal"
    if normalized not in {"ja", "zh"}:
        return "horizontal"

    width = max(1, block[2] - block[0])
    height = max(1, block[3] - block[1])
    if width > height * 1.25:
        return "horizontal"
    if height > width * 1.25:
        return "vertical"
    return None


def _fallback_direction(box: list[int], source_language: str) -> str:
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    normalized = _normalize_source_language(source_language)
    if normalized == "ko":
        return "horizontal"
    if normalized in {"ja", "zh"}:
        return "vertical" if height >= width * 0.9 else "horizontal"
    return "horizontal"


def _normalize_source_language(source_language: str) -> str:
    value = (source_language or "").strip().lower()
    if value in {"ja", "japanese"}:
        return "ja"
    if value in {"ko", "korean"}:
        return "ko"
    if value in {"zh", "ch"} or "chinese" in value:
        return "zh"
    return "other"


def _to_box(box) -> list[int]:
    return [int(round(float(v))) for v in box]


def _clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width, int(round(box[0]))))
    y1 = max(0, min(height, int(round(box[1]))))
    x2 = max(0, min(width, int(round(box[2]))))
    y2 = max(0, min(height, int(round(box[3]))))
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _expand_box(box: list[int], width_percent: float, height_percent: float, image_width: int, image_height: int) -> list[int]:
    width = box[2] - box[0]
    height = box[3] - box[1]
    dx = width * width_percent / 100.0
    dy = height * height_percent / 100.0
    return _clamp_box([box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy], image_width, image_height)


def _union_box(lines: list[list[int]]) -> list[int] | None:
    if not lines:
        return None
    xs1 = [line[0] for line in lines]
    ys1 = [line[1] for line in lines]
    xs2 = [line[2] for line in lines]
    ys2 = [line[3] for line in lines]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]
