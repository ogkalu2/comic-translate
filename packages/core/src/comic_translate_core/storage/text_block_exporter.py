"""TextBlockExporter: Convert upstream TextBlock[] to ScriptExport."""

import time
from typing import Dict, List, Optional

from ..interfaces.exporter import IScriptExporter
from ..models import BlockContext, BlockType, ScriptBlock, ScriptExport


class TextBlockExporter(IScriptExporter):
    """Export comic translations from TextBlock objects to ScriptExport.

    Converts the upstream TextBlock representation (from modules/utils/textblock.py)
    into the standardized ScriptExport format for QA processing.
    """

    def __init__(self, text_blocks: Optional[List] = None):
        """Initialize with optional text blocks.

        Args:
            text_blocks: List of TextBlock objects to export. If None, must be
                        provided via set_blocks() before calling export().
        """
        self._text_blocks = text_blocks or []

    def set_blocks(self, text_blocks: List) -> None:
        """Set the text blocks to export.

        Args:
            text_blocks: List of TextBlock objects.
        """
        self._text_blocks = text_blocks

    def export(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        """Convert TextBlock objects to ScriptExport.

        Args:
            comic_id: Unique identifier for the comic.
            base_fp: Perceptual hash fingerprint.
            source_lang: Source language code.
            target_lang: Target language code.
            page_range: Optional page range filter.
            variant: Variant identifier (e.g., "pixiv_free", "tankobon").

        Returns:
            ScriptExport containing all converted blocks.
        """
        script_blocks = []

        for idx, tb in enumerate(self._text_blocks):
            # Determine block type from text_class
            block_type = self._map_text_class(tb.text_class, tb.is_sfx)

            # Extract bbox as list
            bbox = self._extract_bbox(tb)

            # Build context
            context = BlockContext(
                speaker=None,  # TextBlock doesn't have speaker info
                prev_block=f"p{idx - 1}" if idx > 0 else None,
                next_block=f"p{idx + 1}" if idx < len(self._text_blocks) - 1 else None,
            )

            # Create ScriptBlock
            script_block = ScriptBlock(
                block_id=f"p{idx}",
                page=1,  # TextBlock doesn't have page info; default to 1
                type=block_type,
                bbox=bbox,
                original=tb.text or "",
                translated=tb.translation or "",
                original_variant=variant,
                context=context,
                qa_metadata={
                    "source_lang": tb.source_lang or source_lang,
                    "target_lang": tb.target_lang or target_lang,
                    "direction": tb.direction,
                    "alignment": tb.alignment,
                    "line_spacing": tb.line_spacing,
                    "font_color": tb.font_color,
                },
            )
            script_blocks.append(script_block)

        # Apply page range filter if specified
        if page_range is not None:
            script_blocks = [b for b in script_blocks if b.page in page_range]

        return ScriptExport(
            version="1.0",
            comic_id=comic_id,
            base_fp=base_fp,
            script_id=f"{comic_id}:{base_fp}:{target_lang}",
            source_lang=source_lang,
            target_lang=target_lang,
            exported_at=time.time(),
            page_range=page_range or [1],
            active_variant=variant,
            variants={variant: {}},
            glossary_snapshot={},
            blocks=script_blocks,
        )

    @staticmethod
    def _map_text_class(text_class: str, is_sfx: bool) -> BlockType:
        """Map TextBlock text_class to BlockType.

        Args:
            text_class: The text classification from TextBlock.
            is_sfx: Whether this is a sound effect.

        Returns:
            Corresponding BlockType.
        """
        if is_sfx:
            return BlockType.SFX

        text_class_lower = (text_class or "").lower()
        if "narration" in text_class_lower or "caption" in text_class_lower:
            return BlockType.NARRATION
        elif "credit" in text_class_lower:
            return BlockType.CREDIT
        else:
            return BlockType.DIALOGUE

    @staticmethod
    def _extract_bbox(tb) -> List[int]:
        """Extract bounding box from TextBlock.

        Args:
            tb: TextBlock object.

        Returns:
            Bounding box as [x1, y1, x2, y2].
        """
        if hasattr(tb, "xyxy") and tb.xyxy is not None:
            bbox = tb.xyxy
            if hasattr(bbox, "tolist"):
                return bbox.tolist()
            return list(bbox)
        return [0, 0, 0, 0]
