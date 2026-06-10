from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from modules.utils.download import ModelDownloader, ModelID
from modules.utils.textblock import TextBlock
from .heuristic_lines.core import _detect_lines_and_direction_in_crop
from .heuristic_lines.geometry import _line_axis_box

INPUT_HEIGHT = 48
NULL_CHAR = 0   # unicharset index 0 ("NULL")
BLANK_CHAR = 2  # CTC blank = UNICHAR_BROKEN


def _stats_ile(buckets: np.ndarray, frac: float) -> float:
    """Port of tesseract STATS::ile (statistic.cpp). buckets covers values 0..255."""
    total = int(buckets.sum())
    if total == 0:
        return 0.0
    target = frac * total
    target = min(max(target, 1.0), float(total))
    s = 0
    index = 0
    while index <= 255 and s < target:
        s += int(buckets[index])
        index += 1
    if index > 0:
        return index - (s - target) / buckets[index - 1]
    return 0.0


def _black_white(gray: np.ndarray) -> tuple[float, float]:
    """Black/white point estimation matching tesseract networkio.cpp ComputeBlackWhite."""
    h, w = gray.shape[:2]
    mins = np.zeros(256, dtype=np.int64)
    maxes = np.zeros(256, dtype=np.int64)
    if w >= 3:
        row = gray[h // 2, :].astype(np.int64)
        prev = row[0]
        curr = row[1]
        for x in range(1, w - 1):
            nxt = row[x + 1]
            if (curr < prev and curr <= nxt) or (curr <= prev and curr < nxt):
                mins[curr] += 1
            if (curr > prev and curr >= nxt) or (curr >= prev and curr > nxt):
                maxes[curr] += 1
            prev = curr
            curr = nxt
    if mins.sum() == 0:
        mins[0] = 1
    if maxes.sum() == 0:
        maxes[255] = 1
    black = _stats_ile(mins, 0.25)
    white = _stats_ile(maxes, 0.75)
    return black, white


def _preprocess(crop: np.ndarray) -> np.ndarray:
    """crop (H, W[, C]) uint8 -> (1, 1, 48, W) float32 normalized to ~[-1, 1]."""
    image = Image.fromarray(crop)
    ow, oh = image.size
    if ow == 0 or oh == 0:
        raise ValueError("Empty crop")

    scale = INPUT_HEIGHT / oh
    nw = max(1, round(ow * scale))
    scaled = image.resize((nw, INPUT_HEIGHT), Image.BICUBIC)

    if scaled.mode == "RGBA":
        bg = Image.new("RGBA", scaled.size, (255, 255, 255, 255))
        scaled = Image.alpha_composite(bg, scaled)
    if scaled.mode != "L":
        rgb = np.asarray(scaled.convert("RGB"), dtype=np.float64)
        grey = np.floor(0.3 * rgb[..., 0] + 0.5 * rgb[..., 1] + 0.2 * rgb[..., 2] + 0.5).astype(np.uint8)
    else:
        grey = np.asarray(scaled, dtype=np.uint8)

    black, white = _black_white(grey)
    contrast = (white - black) / 2.0
    if contrast <= 0.0:
        contrast = 1.0

    norm = (grey.astype(np.float32) - black) / contrast - 1.0
    return norm.astype(np.float32)[None, None, :, :]  # (1, 1, 48, W)


def _dominant_script(scores: np.ndarray, labels: list[str]) -> str:
    """CTC best-path collapse, then return the most frequent non-blank label."""
    ids = scores.argmax(axis=1)
    counts: dict[int, int] = {}
    prev = BLANK_CHAR
    for raw in ids:
        i = int(raw)
        if i != BLANK_CHAR and i != prev:
            counts[i] = counts.get(i, 0) + 1
        prev = i
    if not counts:
        return ""
    best = max(counts, key=counts.get)
    if best == NULL_CHAR:
        return ""
    return labels[best]


def _make_session_options():
    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.intra_op_num_threads = 4
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.enable_cpu_mem_arena = True
    so.enable_mem_pattern = True
    return so


def _line_area(line) -> int:
    x1, y1, x2, y2 = _line_axis_box(line)
    return max(1, x2 - x1) * max(1, y2 - y1)


def _largest_line_crop(image: np.ndarray, blk: TextBlock) -> tuple[np.ndarray, str] | None:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in blk.xyxy]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None

    crop = image[y1:y2, x1:x2]
    lines, direction = _detect_lines_and_direction_in_crop(crop, getattr(blk, "source_lang", ""))
    if not lines:
        return crop, direction

    best = max(lines, key=_line_area)
    lx1, ly1, lx2, ly2 = _line_axis_box(best)
    ch, cw = crop.shape[:2]
    lx1, ly1 = max(0, lx1), max(0, ly1)
    lx2, ly2 = min(cw, lx2), min(ch, ly2)
    if lx2 <= lx1 or ly2 <= ly1:
        return crop, direction

    return crop[ly1:ly2, lx1:lx2], direction


class ScriptDetector:
    """Runs the OSD LSTM script-detection model to populate TextBlock.language."""

    def __init__(self):
        self.session: ort.InferenceSession | None = None
        self.labels: list[str] | None = None

    def initialize(self) -> None:
        if self.session is not None:
            return

        model_path = ModelDownloader.get_file_path(ModelID.OSD_SCRIPT_DETECTOR_ONNX, "osd_lstm.onnx")
        self.session = ort.InferenceSession(
            model_path,
            sess_options=_make_session_options(),
            providers=["CPUExecutionProvider"],
        )

        labels_path = ModelDownloader.get_file_path(ModelID.OSD_SCRIPT_DETECTOR_ONNX, "osd_labels.json")
        self.labels = json.loads(Path(labels_path).read_text("utf-8"))

    def detect_block_script(self, image: np.ndarray, blk: TextBlock) -> str:
        """Run the OSD LSTM script-detection model on a TextBlock's largest text line.

        Returns an OSD script label (e.g. "Latin", "Japanese_vert", "Cyrillic"),
        or "" if no script could be confidently detected.
        """
        result = _largest_line_crop(image, blk)
        if result is None:
            return ""

        crop, direction = result
        if crop.size == 0 or crop.shape[0] < 3 or crop.shape[1] < 3:
            return ""

        if direction == "vertical":
            crop = np.rot90(crop, k=1)

        pixels = _preprocess(crop)
        if pixels.shape[-1] < 3:
            return ""

        self.initialize()
        scores = self.session.run(None, {"image": pixels})[0]
        return _dominant_script(scores, self.labels)

    def annotate_blocks(self, image: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """Populate blk.language for every block using the OSD script-detection model."""
        for blk in blk_list:
            try:
                blk.language = self.detect_block_script(image, blk)
            except Exception:
                blk.language = ""
        return blk_list
