from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from modules.ocr.ppocr.preprocessing import det_preprocess
from modules.ocr.ppocr.postprocessing import DBPostProcessor
from modules.utils.download import ModelDownloader, ModelID
from modules.utils.device import get_providers
from modules.utils.onnx import make_session, make_session_options
from modules.utils.textblock import TextBlock
from .backend import resolve_detection_backend


class PPOCRLineDetector:
    def __init__(self):
        self.session: Any | None = None
        self.device = "cpu"
        self.backend = "onnx"
        self.det_model = "mobile"
        self.post = DBPostProcessor(
            thresh=0.3,
            box_thresh=0.5,
            unclip_ratio=2.0,
            use_dilation=False,
        )

    def initialize(self, device: str = "cpu", backend: str = "onnx", det_model: str = "mobile") -> None:
        backend = resolve_detection_backend(backend)
        if self.session is not None and self.device == device and self.backend == backend and self.det_model == det_model:
            return
        self.device = device
        self.backend = backend
        self.det_model = det_model

        if backend == "torch":
            from modules.ocr.ppocr.torch.inference_engine.torch_session import TorchInferSession

            det_id = ModelID.PPOCR_V5_DET_MOBILE_TORCH
            ModelDownloader.ensure([det_id])
            model_path = ModelDownloader.primary_path(det_id)
            arch_cfg_path = Path(__file__).parents[1] / "ocr" / "ppocr" / "torch" / "arch_config.yaml"
            self.session = TorchInferSession(model_path, arch_cfg_path, device)
            return

        det_id = ModelID.PPOCR_V5_DET_MOBILE if det_model == "mobile" else ModelID.PPOCR_V5_DET_SERVER
        ModelDownloader.ensure([det_id])
        model_path = ModelDownloader.primary_path(det_id)
        providers = get_providers(device)
        sess_opt = make_session_options(log_severity_level=3)
        self.session = make_session(model_path, sess_options=sess_opt, providers=providers)

    def detect_lines(self, image: np.ndarray) -> list[list[int]]:
        if self.session is None:
            self.initialize(self.device)
        if self.session is None:
            return []

        inp = det_preprocess(image, limit_side_len=960, limit_type="min")
        if self.backend == "torch":
            pred = self.session(inp)
        else:
            input_name = self.session.get_inputs()[0].name
            output_name = self.session.get_outputs()[0].name
            pred = self.session.run([output_name], {input_name: inp})[0]
        quads, _ = self.post(pred, (image.shape[0], image.shape[1]))
        boxes = [_axis_box(quad) for quad in quads]
        return _merge_line_boxes(boxes, image.shape[1], image.shape[0])


_DETECTOR_CACHE: dict[str, PPOCRLineDetector] = {}


def annotate_blocks_with_ppocr_lines(
    image: np.ndarray,
    blocks: list[TextBlock],
    device: str = "cpu",
    backend: str = "onnx",
    det_model: str = "mobile",
) -> list[TextBlock]:
    if not blocks:
        return blocks

    backend = resolve_detection_backend(backend)
    cache_key = f"{backend}:{device}:{det_model}"
    detector = _DETECTOR_CACHE.get(cache_key)
    if detector is None:
        detector = PPOCRLineDetector()
        detector.initialize(device=device, backend=backend, det_model=det_model)
        _DETECTOR_CACHE[cache_key] = detector

    lines = detector.detect_lines(image)
    groups: list[list[list[int]]] = [[] for _ in blocks]
    usable_lines = [line for line in lines if _is_usable_line(line, image.shape[1], image.shape[0])]

    for line in usable_lines:
        index = _best_block_for_line(line, blocks, image.shape[1], image.shape[0])
        if index >= 0:
            groups[index].append(line)

    for block, block_lines in zip(blocks, groups):
        direction = _infer_direction(block_lines, block.xyxy)
        block.lines = _sort_lines(block_lines, direction)
        block.direction = direction

    return blocks


def _axis_box(item: np.ndarray) -> list[int]:
    arr = np.asarray(item)
    if arr.ndim == 1 and arr.size == 4:
        x1, y1, x2, y2 = arr.tolist()
        return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]
    pts = arr.reshape(-1, 2)
    return [
        int(round(float(pts[:, 0].min()))),
        int(round(float(pts[:, 1].min()))),
        int(round(float(pts[:, 0].max()))),
        int(round(float(pts[:, 1].max()))),
    ]


def _merge_line_boxes(lines: list[list[int]], width: int, height: int) -> list[list[int]]:
    groups: list[dict] = []
    for line in sorted(lines, key=lambda box: (box[1], box[0])):
        match = next((group for group in groups if _should_merge(group["box"], line, width)), None)
        if match is None:
            groups.append({"box": line.copy(), "score_area": _box_area(line)})
            continue
        match["box"] = [
            min(match["box"][0], line[0]),
            min(match["box"][1], line[1]),
            max(match["box"][2], line[2]),
            max(match["box"][3], line[3]),
        ]
        match["score_area"] += _box_area(line)

    out = []
    for group in groups:
        box = _clamp_box(group["box"], width, height)
        if box[2] - box[0] > 3 and box[3] - box[1] > 3:
            out.append(box)
    return sorted(out, key=lambda box: (box[1], box[0]))


def _should_merge(a: list[int], b: list[int], image_width: int) -> bool:
    width_a = a[2] - a[0]
    height_a = a[3] - a[1]
    width_b = b[2] - b[0]
    height_b = b[3] - b[1]
    a_vertical = height_a > width_a * 1.25
    b_vertical = height_b > width_b * 1.25
    a_horizontal = width_a > height_a * 1.25
    b_horizontal = width_b > height_b * 1.25

    overlap_y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    min_height = max(1, min(height_a, height_b))
    center_delta = abs(((a[1] + a[3]) / 2) - ((b[1] + b[3]) / 2))
    gap_x = max(0, max(a[0], b[0]) - min(a[2], b[2]))
    same_horizontal = overlap_y / min_height >= 0.55 or center_delta <= min_height * 0.35
    horizontal_merge = same_horizontal and gap_x <= max(image_width * 0.08, min_height * 2)
    if not a_vertical and not b_vertical and (a_horizontal or b_horizontal or horizontal_merge):
        return horizontal_merge

    overlap_x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    min_width = max(1, min(width_a, width_b))
    x_center_delta = abs(((a[0] + a[2]) / 2) - ((b[0] + b[2]) / 2))
    gap_y = max(0, max(a[1], b[1]) - min(a[3], b[3]))
    same_vertical = overlap_x / min_width >= 0.55 or x_center_delta <= min_width * 0.35
    vertical_merge = same_vertical and gap_y <= max(min_width * 2, 8)
    if not a_horizontal and not b_horizontal:
        return vertical_merge

    return False


def _best_block_for_line(line: list[int], blocks: list[TextBlock], width: int, height: int) -> int:
    best_index = -1
    best_score = 0.0
    line_center_x = (line[0] + line[2]) / 2
    line_center_y = (line[1] + line[3]) / 2
    line_area = max(1, _box_area(line))

    for i, block in enumerate(blocks):
        container = _expand_box([int(v) for v in block.xyxy], 8, 8, width, height)
        overlap = _intersection_area(container, line) / line_area
        center_bonus = 0.15 if _point_in_box(line_center_x, line_center_y, container) else 0.0
        score = overlap + center_bonus
        if score > best_score:
            best_index = i
            best_score = score

    return best_index if best_score >= 0.35 else -1


def _infer_direction(lines: list[list[int]], block_box) -> str:
    if lines:
        horizontal = 0.0
        vertical = 0.0
        for line in lines:
            width = max(1, line[2] - line[0])
            height = max(1, line[3] - line[1])
            horizontal += max(0.0, width / height - 1)
            vertical += max(0.0, height / width - 1)
        if vertical > horizontal * 1.15 + 0.2:
            return "vertical"
        if horizontal > vertical * 1.15 + 0.2:
            return "horizontal"

    x1, y1, x2, y2 = [int(v) for v in block_box]
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    return "vertical" if height > width * 1.25 else "horizontal"


def _sort_lines(lines: list[list[int]], direction: str) -> list[list[int]]:
    if direction == "vertical":
        return sorted((list(map(int, line)) for line in lines), key=lambda box: (-box[0], box[1]))
    return sorted((list(map(int, line)) for line in lines), key=lambda box: (box[1], box[0]))


def _is_usable_line(line: list[int], width: int, height: int) -> bool:
    box = _clamp_box(line, width, height)
    area = _box_area(box)
    return box[2] - box[0] > 3 and box[3] - box[1] > 3 and area < width * height * 0.75


def _clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width, int(round(box[0]))))
    y1 = max(0, min(height, int(round(box[1]))))
    x2 = max(0, min(width, int(round(box[2]))))
    y2 = max(0, min(height, int(round(box[3]))))
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _expand_box(box: list[int], width_percent: float, height_percent: float, image_width: int, image_height: int) -> list[int]:
    width = box[2] - box[0]
    height = box[3] - box[1]
    dx = width * width_percent / 100
    dy = height * height_percent / 100
    return _clamp_box([box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy], image_width, image_height)


def _box_area(box: list[int]) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def _intersection_area(a: list[int], b: list[int]) -> int:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _point_in_box(x: float, y: float, box: list[int]) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]
