from __future__ import annotations

import uuid

import numpy as np

from .textblock_state import (
    TextBlockContentState,
    TextBlockGeometryState,
    TextBlockMetadataState,
    TextBlockRenderState,
    clone_state_value,
)


class TextBlock(object):
    """
    Object that stores a block of text. Optionally stores the list of lines.

    The instance still exposes the historical flat attributes because the
    project serializes/deserializes `TextBlock` objects through `__dict__`.
    The snapshot helpers below separate geometry/content/render concerns
    without forcing a broad migration of existing call sites.
    """

    def __init__(
        self,
        text_bbox: np.ndarray = None,
        bubble_bbox: np.ndarray = None,
        text_class: str = "",
        inpaint_bboxes=None,
        lines: list = None,
        text_segm_points: np.ndarray = None,
        angle=0,
        text: str = "",
        texts: list[str] = None,
        translation: str = "",
        line_spacing=1,
        alignment: str = '',
        target_lang: str = "",
        min_font_size: int = 0,
        max_font_size: int = 0,
        font_size_px: float = 0.0,
        font_color: tuple = (),
        direction: str = "",
        block_uid: str = "",
        **kwargs,
    ) -> None:
        self.xyxy = text_bbox
        self.segm_pts = text_segm_points
        self.bubble_xyxy = bubble_bbox
        self.text_class = text_class
        self.angle = angle
        self.tr_origin_point = ()

        self.lines = lines
        if isinstance(inpaint_bboxes, np.ndarray):
            self.inpaint_bboxes = inpaint_bboxes
        else:
            self.inpaint_bboxes = np.array(inpaint_bboxes, dtype=np.int32) if inpaint_bboxes else None
        self.texts = texts if texts is not None else []
        self.text = ' '.join(self.texts) if self.texts else text
        self.translation = translation

        self.line_spacing = line_spacing
        self.alignment = alignment

        self.target_lang = target_lang
        self.block_uid = block_uid or uuid.uuid4().hex

        self.min_font_size = min_font_size
        self.max_font_size = max_font_size
        self.font_size_px = font_size_px
        self.font_color = font_color
        self.direction = direction

        for key, value in kwargs.items():
            setattr(self, key, value)

    _NON_PERSISTENT_KEYS = {
        "source_lang",
        "_mapping",
        "_page_index",
        "_original_xyxy",
        "_original_bubble_xyxy",
    }

    _SERIALIZED_KEYS = {
        "xyxy",
        "segm_pts",
        "bubble_xyxy",
        "text_class",
        "angle",
        "tr_origin_point",
        "lines",
        "inpaint_bboxes",
        "texts",
        "text",
        "translation",
        "line_spacing",
        "alignment",
        "target_lang",
        "block_uid",
        "min_font_size",
        "max_font_size",
        "font_size_px",
        "font_color",
        "direction",
        "max_chars",
    }

    @property
    def xywh(self):
        x1, y1, x2, y2 = self.xyxy
        return np.array([x1, y1, x2 - x1, y2 - y1]).astype(np.int32)

    @property
    def center(self) -> np.ndarray:
        xyxy = np.array(self.xyxy)
        return (xyxy[:2] + xyxy[2:]) / 2

    def geometry_state(self) -> TextBlockGeometryState:
        return TextBlockGeometryState(
            xyxy=clone_state_value(self.xyxy),
            bubble_xyxy=clone_state_value(self.bubble_xyxy),
            inpaint_bboxes=clone_state_value(self.inpaint_bboxes),
            segm_pts=clone_state_value(self.segm_pts),
            lines=clone_state_value(self.lines),
            angle=self.angle,
            tr_origin_point=clone_state_value(self.tr_origin_point),
        )

    def apply_geometry_state(self, state: TextBlockGeometryState) -> None:
        self.xyxy = clone_state_value(state.xyxy)
        self.bubble_xyxy = clone_state_value(state.bubble_xyxy)
        self.inpaint_bboxes = clone_state_value(state.inpaint_bboxes)
        self.segm_pts = clone_state_value(state.segm_pts)
        self.lines = clone_state_value(state.lines)
        self.angle = state.angle
        self.tr_origin_point = clone_state_value(state.tr_origin_point)

    def content_state(self) -> TextBlockContentState:
        return TextBlockContentState(
            text=self.text,
            texts=clone_state_value(self.texts) or [],
            translation=self.translation,
            target_lang=self.target_lang,
        )

    def apply_content_state(self, state: TextBlockContentState) -> None:
        self.text = state.text
        self.texts = clone_state_value(state.texts) or []
        self.translation = state.translation
        self.target_lang = state.target_lang

    def render_state(self) -> TextBlockRenderState:
        return TextBlockRenderState(
            line_spacing=self.line_spacing,
            alignment=self.alignment,
            min_font_size=self.min_font_size,
            max_font_size=self.max_font_size,
            font_size_px=self.font_size_px,
            font_color=clone_state_value(self.font_color),
            direction=self.direction,
            max_chars=getattr(self, "max_chars", None),
        )

    def apply_render_state(self, state: TextBlockRenderState) -> None:
        self.line_spacing = state.line_spacing
        self.alignment = state.alignment
        self.min_font_size = state.min_font_size
        self.max_font_size = state.max_font_size
        self.font_size_px = state.font_size_px
        self.font_color = clone_state_value(state.font_color)
        self.direction = state.direction
        if state.max_chars is None:
            self.__dict__.pop("max_chars", None)
        else:
            self.max_chars = state.max_chars

    def metadata_state(self) -> TextBlockMetadataState:
        return TextBlockMetadataState(
            text_class=self.text_class,
            block_uid=self.block_uid,
        )

    def apply_metadata_state(self, state: TextBlockMetadataState) -> None:
        self.text_class = state.text_class
        self.block_uid = state.block_uid

    def to_dict(self, include_extras: bool = True, include_private: bool = False) -> dict:
        data = {
            "xyxy": clone_state_value(self.xyxy),
            "segm_pts": clone_state_value(self.segm_pts),
            "bubble_xyxy": clone_state_value(self.bubble_xyxy),
            "text_class": self.text_class,
            "angle": self.angle,
            "tr_origin_point": clone_state_value(self.tr_origin_point),
            "lines": clone_state_value(self.lines),
            "inpaint_bboxes": clone_state_value(self.inpaint_bboxes),
            "texts": clone_state_value(self.texts),
            "text": self.text,
            "translation": self.translation,
            "line_spacing": self.line_spacing,
            "alignment": self.alignment,
            "target_lang": self.target_lang,
            "block_uid": self.block_uid,
            "min_font_size": self.min_font_size,
            "max_font_size": self.max_font_size,
            "font_size_px": self.font_size_px,
            "font_color": clone_state_value(self.font_color),
            "direction": self.direction,
        }
        max_chars = getattr(self, "max_chars", None)
        if max_chars is not None:
            data["max_chars"] = max_chars

        if not include_extras:
            return data

        for key, value in self.__dict__.items():
            if key in data or key in self._NON_PERSISTENT_KEYS:
                continue
            if key.startswith("_") and not include_private:
                continue
            data[key] = clone_state_value(value)

        return data

    @classmethod
    def from_dict(cls, payload: dict | None):
        data = dict(payload or {})
        for key in cls._NON_PERSISTENT_KEYS:
            data.pop(key, None)

        block = cls(
            text_bbox=data.pop("xyxy", None),
            bubble_bbox=data.pop("bubble_xyxy", None),
            text_class=data.pop("text_class", ""),
            inpaint_bboxes=data.pop("inpaint_bboxes", None),
            lines=data.pop("lines", None),
            text_segm_points=data.pop("segm_pts", None),
            angle=data.pop("angle", 0),
            text=data.pop("text", ""),
            texts=data.pop("texts", None),
            translation=data.pop("translation", ""),
            line_spacing=data.pop("line_spacing", 1),
            alignment=data.pop("alignment", ""),
            target_lang=data.pop("target_lang", ""),
            min_font_size=data.pop("min_font_size", 0),
            max_font_size=data.pop("max_font_size", 0),
            font_size_px=data.pop("font_size_px", 0.0),
            font_color=data.pop("font_color", ()),
            direction=data.pop("direction", ""),
            block_uid=data.pop("block_uid", ""),
        )

        tr_origin_point = data.pop("tr_origin_point", ())
        block.tr_origin_point = clone_state_value(tr_origin_point)

        if "max_chars" in data:
            block.max_chars = data.pop("max_chars")

        for key, value in data.items():
            block.__dict__[key] = clone_state_value(value)

        return block

    def deep_copy(self):
        """
        Create a deep copy of this TextBlock instance.

        Returns:
            TextBlock: A new TextBlock instance with copied data
        """
        new_block = TextBlock()
        new_block.apply_geometry_state(self.geometry_state())
        new_block.apply_content_state(self.content_state())
        new_block.apply_render_state(self.render_state())
        new_block.apply_metadata_state(self.metadata_state())

        for key, value in self.__dict__.items():
            if key in self._SERIALIZED_KEYS:
                continue
            new_block.__dict__[key] = clone_state_value(value)

        return new_block


from .textblock_content import lists_to_blk_list, sort_textblock_rectangles
from .textblock_geometry import adjust_blks_size, adjust_text_line_coordinates, sort_blk_list
from .textblock_visualization import visualize_speech_bubbles, visualize_textblocks
