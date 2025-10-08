"""Shared rendering settings and helpers used across rendering pipelines."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from schemas.style_state import StyleState


@dataclass
class TextRenderingSettings:
    alignment_id: int
    font_family: str
    min_font_size: int
    max_font_size: int
    color: str
    upper_case: bool
    outline: bool
    outline_color: str
    outline_width: str
    bold: bool
    italic: bool
    underline: bool
    line_spacing: str
    direction: Qt.LayoutDirection
    auto_font_color: bool = True


def preferred_stroke_size(
    render_settings: TextRenderingSettings,
    style_state: StyleState,
    stroke_inferred: bool,
) -> int:
    """Resolve the stroke width to apply for detected outlines."""

    if style_state.stroke_size is not None and style_state.stroke_size > 0:
        return int(style_state.stroke_size)

    try:
        configured = float(render_settings.outline_width)
    except (TypeError, ValueError):
        configured = 0.0

    configured_int = int(round(configured))
    if configured_int > 0:
        return configured_int

    return 2 if stroke_inferred else 1


__all__ = ["TextRenderingSettings", "preferred_stroke_size"]
