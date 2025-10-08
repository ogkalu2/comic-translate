"""High level interface for Torii-style auto text rendering decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np

from modules.layout.grouping import TextGroup, group_text_blocks
from schemas.style_state import StyleState

from .color_analysis import ColorAnalysis, analyse_group_colors
from .decisions import AutoStyleConfig, decide_style


@dataclass
class AutoStyleResult:
    group: TextGroup
    analysis: Optional[ColorAnalysis]
    style: StyleState


class AutoStyleEngine:
    """Analyse text groups and produce rendering styles."""

    def __init__(self, config: Optional[AutoStyleConfig] = None, ring_radius: int = 6):
        self.config = config or AutoStyleConfig()
        self.ring_radius = ring_radius

    def analyse_image(self, image: np.ndarray, blocks: Iterable, base_state: StyleState) -> List[AutoStyleResult]:
        groups = group_text_blocks(list(blocks))
        results: List[AutoStyleResult] = []
        for group in groups:
            analysis = analyse_group_colors(image, group, ring_radius=self.ring_radius)
            style = decide_style(analysis, base_state, self.config)
            results.append(AutoStyleResult(group=group, analysis=analysis, style=style))
        return results

    def style_for_block(self, image: np.ndarray, block, base_state: StyleState) -> StyleState:
        groups = group_text_blocks([block])
        if not groups:
            return decide_style(None, base_state, self.config)
        analysis = analyse_group_colors(image, groups[0], ring_radius=self.ring_radius)
        return decide_style(analysis, base_state, self.config)


__all__ = ["AutoStyleEngine", "AutoStyleResult"]
