"""Data structures representing rendering style options for text blocks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional, Tuple

ColorTuple = Tuple[int, int, int]


@dataclass
class StyleState:
    """User and engine controlled styling for a translated text block."""

    font_family: str = "WildWords"
    font_size: int = 32
    text_align: str = "left"
    auto_color: bool = True
    fill: Optional[ColorTuple] = None
    stroke: Optional[ColorTuple] = None
    stroke_size: Optional[int] = None
    stroke_enabled: bool = False
    bg_enabled: bool = False
    bg_color: ColorTuple = (255, 255, 255)
    bg_alpha: int = 0
    border_enabled: bool = False
    border_radius: int = 0
    border_padding: int = 0
    font_weight: str = "normal"
    italic: bool = False
    underline: bool = False
    no_stroke_on_plain: bool = True
    analysis_cache_key: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def copy(self) -> "StyleState":
        """Return a shallow copy of the state suitable for per-block tweaks."""

        return StyleState(
            font_family=self.font_family,
            font_size=self.font_size,
            text_align=self.text_align,
            auto_color=self.auto_color,
            fill=None if self.fill is None else tuple(self.fill),
            stroke=None if self.stroke is None else tuple(self.stroke),
            stroke_size=self.stroke_size,
            stroke_enabled=self.stroke_enabled,
            bg_enabled=self.bg_enabled,
            bg_color=tuple(self.bg_color),
            bg_alpha=self.bg_alpha,
            border_enabled=self.border_enabled,
            border_radius=self.border_radius,
            border_padding=self.border_padding,
            font_weight=self.font_weight,
            italic=self.italic,
            underline=self.underline,
            no_stroke_on_plain=self.no_stroke_on_plain,
            analysis_cache_key=self.analysis_cache_key,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict:
        """Serialise the style state into basic Python types."""

        data = asdict(self)
        # Dataclasses converts tuples to lists; convert back for stability.
        if data.get("fill") is not None:
            data["fill"] = tuple(data["fill"])
        if data.get("stroke") is not None:
            data["stroke"] = tuple(data["stroke"])
        if data.get("bg_color") is not None:
            data["bg_color"] = tuple(data["bg_color"])
        return data

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "StyleState":
        """Recreate a :class:`StyleState` from serialised data."""

        if not data:
            return cls()

        kwargs = dict(data)
        for key in ("fill", "stroke", "bg_color"):
            if key in kwargs and kwargs[key] is not None:
                kwargs[key] = tuple(kwargs[key])
        return cls(**kwargs)


__all__ = ["StyleState", "ColorTuple"]
