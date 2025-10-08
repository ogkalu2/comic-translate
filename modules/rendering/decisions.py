"""Decision rules for converting colour analysis into rendering styles."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Optional

from schemas.style_state import StyleState
from .color_analysis import ColorAnalysis
from modules.utils.wcag import (
    ensure_contrast,
    normalize_rgb,
    pick_higher_contrast,
    relative_luminance,
)


@dataclass
class AutoStyleConfig:
    target_contrast: float = 4.5
    stroke_max_size: int = 6
    stroke_factor: float = 18.0
    brighten_amount: float = 0.08
    stroke_min_distance: float = 18.0
    plain_white_stroke: bool = True
    plain_black_stroke: bool = True


def _distance(rgb_a, rgb_b) -> float:
    ax, ay, az = rgb_a
    bx, by, bz = rgb_b
    return ((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2) ** 0.5


def _brighten(rgb, amount: float) -> tuple[int, int, int]:
    r, g, b = [v / 255.0 for v in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = min(1.0, l + amount)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return tuple(int(round(v * 255.0)) for v in (r2, g2, b2))


def _synth_stroke(fill_rgb, background_rgb=None):
    if background_rgb is not None:
        return pick_higher_contrast((0, 0, 0), (255, 255, 255), fill_rgb)
    fill_lum = relative_luminance(fill_rgb)
    return (0, 0, 0) if fill_lum > 0.5 else (255, 255, 255)


def decide_style(
    analysis: Optional[ColorAnalysis],
    base_state: StyleState,
    config: Optional[AutoStyleConfig] = None,
) -> StyleState:
    config = config or AutoStyleConfig()
    state = base_state.copy()

    if not state.auto_color or analysis is None:
        if state.stroke is not None:
            state.stroke_enabled = True
        return state

    state.stroke_enabled = False

    fill_rgb = analysis.fill_rgb
    stroke_rgb = analysis.stroke_rgb
    background_rgb = analysis.background_rgb
    plain_background = analysis.plain_white or analysis.plain_black

    if analysis.plain_white:
        fill_rgb = (0, 0, 0)
        if state.no_stroke_on_plain:
            stroke_rgb = None
        elif config.plain_white_stroke:
            stroke_rgb = (255, 255, 255)
    elif analysis.plain_black:
        fill_rgb = (255, 255, 255)
        if state.no_stroke_on_plain:
            stroke_rgb = None
        elif config.plain_black_stroke:
            stroke_rgb = (0, 0, 0)
    else:
        if fill_rgb is None and background_rgb is not None:
            fill_rgb = pick_higher_contrast((0, 0, 0), (255, 255, 255), background_rgb)
        if fill_rgb is None:
            fill_rgb = (0, 0, 0)
        else:
            fill_rgb = _brighten(fill_rgb, config.brighten_amount)

    if background_rgb is not None and fill_rgb is not None:
        enforced = ensure_contrast(fill_rgb, background_rgb, config.target_contrast)
        if enforced != fill_rgb:
            fill_rgb = enforced
            if not (plain_background and state.no_stroke_on_plain):
                stroke_rgb = _synth_stroke(fill_rgb, background_rgb)

    if fill_rgb is not None and stroke_rgb is not None:
        if _distance(fill_rgb, stroke_rgb) < config.stroke_min_distance:
            stroke_rgb = _synth_stroke(fill_rgb, background_rgb)

    if stroke_rgb is None and background_rgb is not None and not (plain_background and state.no_stroke_on_plain):
        stroke_rgb = _synth_stroke(fill_rgb, background_rgb)

    state.fill = normalize_rgb(fill_rgb) if fill_rgb is not None else None
    state.stroke = normalize_rgb(stroke_rgb) if stroke_rgb is not None else None
    state.stroke_enabled = state.stroke is not None

    if state.stroke_size is None:
        auto_size = max(1, min(int(round(state.font_size / config.stroke_factor)), config.stroke_max_size))
        state.stroke_size = auto_size

    return state


__all__ = ["AutoStyleConfig", "decide_style"]
