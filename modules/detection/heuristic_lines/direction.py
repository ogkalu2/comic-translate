from __future__ import annotations
import numpy as np

from .geometry import _line_axis_box, _union_box, _normalize_line

def _infer_direction(lines: list[list[int]], block_box: list[int], source_language: str) -> str:
    if lines:
        horizontal = 0.0
        vertical = 0.0
        for line in lines:
            x1, y1, x2, y2 = _line_axis_box(line)
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
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
        return sorted((_normalize_line(line) for line in lines), key=lambda line: (-_line_axis_box(line)[0], _line_axis_box(line)[1]))
    return sorted((_normalize_line(line) for line in lines), key=lambda line: (_line_axis_box(line)[1], _line_axis_box(line)[0]))

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
    aspect_direction = "vertical" if height > width * 1.15 else "horizontal"

    normalized = _normalize_source_language(source_language)
    if normalized == "ko":
        return "horizontal"
    if normalized in {"ja", "zh"} and 0.85 <= height / width <= 1.15:
        return "vertical" if height >= width * 0.9 else "horizontal"
    return aspect_direction

def _normalize_source_language(source_language: str) -> str:
    value = (source_language or "").strip().lower()
    if value in {"ja", "japanese"}:
        return "ja"
    if value in {"ko", "korean"}:
        return "ko"
    if value in {"zh", "ch"} or value.startswith("zh-") or "chinese" in value:
        return "zh"
    return "other"
