from __future__ import annotations
import math
import numpy as np

def _is_polygon_line(line) -> bool:
    if isinstance(line, list):
        if len(line) >= 4 and isinstance(line[0], list):
            return True
        return False
    if isinstance(line, tuple):
        if len(line) >= 4 and isinstance(line[0], (list, tuple)):
            return True
        return False
    if isinstance(line, np.ndarray):
        return line.ndim == 2 and line.shape[0] >= 4 and line.shape[1] == 2
    arr = np.asarray(line)
    return arr.ndim == 2 and arr.shape[0] >= 4 and arr.shape[1] == 2

def _line_axis_box(line) -> list[int]:
    if _is_polygon_line(line):
        arr = np.asarray(line, dtype=float)
        return [
            int(math.floor(float(arr[:, 0].min()))),
            int(math.floor(float(arr[:, 1].min()))),
            int(math.ceil(float(arr[:, 0].max()))),
            int(math.ceil(float(arr[:, 1].max()))),
        ]
    return [int(round(float(v))) for v in np.asarray(line).reshape(-1)[:4]]

def _offset_line(line, offset_x: int, offset_y: int):
    if _is_polygon_line(line):
        return [[int(point[0]) + offset_x, int(point[1]) + offset_y] for point in line]
    return [int(line[0]) + offset_x, int(line[1]) + offset_y, int(line[2]) + offset_x, int(line[3]) + offset_y]

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
    boxes = [_line_axis_box(line) for line in lines]
    xs1 = [box[0] for box in boxes]
    ys1 = [box[1] for box in boxes]
    xs2 = [box[2] for box in boxes]
    ys2 = [box[3] for box in boxes]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]

def _normalize_line(line):
    if _is_polygon_line(line):
        return [[int(round(float(point[0]))), int(round(float(point[1])))] for point in line]
    return [int(round(float(v))) for v in np.asarray(line).reshape(-1)[:4]]

def _pad_polygon_line(line, direction: str, width: int, height: int) -> list[list[int]]:
    points = np.asarray(line, dtype=float)
    center = points.mean(axis=0)
    edge_width = max(1.0, float(np.linalg.norm(points[1] - points[0])))
    edge_height = max(1.0, float(np.linalg.norm(points[3] - points[0])))
    local_x = (points[1] - points[0]) / edge_width
    local_y = (points[3] - points[0]) / edge_height

    if direction == "horizontal":
        x_scale = (edge_width + max(2.0, edge_height * 0.20)) / edge_width
        y_scale = (edge_height + max(6.0, edge_height * 0.40)) / edge_height
    else:
        x_scale = (edge_width + max(2.0, edge_width * 0.24)) / edge_width
        y_scale = (edge_height + max(2.0, edge_width * 0.20)) / edge_height

    padded: list[list[int]] = []
    for point in points:
        delta = point - center
        expanded = center + local_x * np.dot(delta, local_x) * x_scale + local_y * np.dot(delta, local_y) * y_scale
        padded.append([
            max(0, min(width, int(round(float(expanded[0]))))),
            max(0, min(height, int(round(float(expanded[1]))))),
        ])
    return padded

def _pad_line_boxes(lines: list[list[int]], direction: str, width: int, height: int) -> list[list[int]]:
    padded: list[list[int]] = []
    for line in lines:
        if _is_polygon_line(line):
            padded.append(_pad_polygon_line(line, direction, width, height))
            continue

        x1, y1, x2, y2 = [int(v) for v in line]
        line_width = max(1, x2 - x1 + 1)
        line_height = max(1, y2 - y1 + 1)
        if direction == "horizontal":
            dx = max(1, int(round(line_height * 0.10)))
            dy = max(3, int(round(line_height * 0.20)))
        else:
            dx = max(1, int(round(line_width * 0.12)))
            dy = max(1, int(round(line_width * 0.10)))
        padded.append(_clamp_box([x1 - dx, y1 - dy, x2 + dx, y2 + dy], width, height))
    return padded
