from __future__ import annotations

import copy
from dataclasses import dataclass


@dataclass(slots=True)
class StageViewModel:
    viewer_state: dict
    brush_strokes: list[dict]
    load_patches: bool


def build_stage_view_model(
    ui_stage: str,
    *,
    rectangles: list[dict] | None = None,
    text_items_state: list[dict] | None = None,
    brush_strokes: list[dict] | None = None,
    metadata: dict | None = None,
) -> StageViewModel:
    viewer_state = {
        "rectangles": copy.deepcopy(rectangles or []),
        "text_items_state": copy.deepcopy(text_items_state or []),
    }
    if metadata:
        for key in ("transform", "center", "scene_rect"):
            if key in metadata:
                viewer_state[key] = metadata.get(key)

    return StageViewModel(
        viewer_state=viewer_state,
        brush_strokes=copy.deepcopy(brush_strokes or []),
        load_patches=ui_stage in {"clean", "render"},
    )
