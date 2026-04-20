from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np


def clone_state_value(value):
    if isinstance(value, np.ndarray):
        return value.copy()
    return copy.deepcopy(value)


@dataclass
class TextBlockGeometryState:
    xyxy: np.ndarray | list | None = None
    bubble_xyxy: np.ndarray | list | None = None
    inpaint_bboxes: np.ndarray | list | None = None
    segm_pts: np.ndarray | list | None = None
    lines: list | None = None
    angle: float = 0
    tr_origin_point: tuple = ()


@dataclass
class TextBlockContentState:
    text: str = ""
    texts: list[str] = field(default_factory=list)
    translation: str = ""
    target_lang: str = ""


@dataclass
class TextBlockRenderState:
    line_spacing: float = 1
    alignment: str = ""
    min_font_size: int = 0
    max_font_size: int = 0
    font_size_px: float = 0.0
    font_color: tuple = ()
    direction: str = ""
    max_chars: int | None = None


@dataclass
class TextBlockMetadataState:
    text_class: str = ""
    block_uid: str = ""
