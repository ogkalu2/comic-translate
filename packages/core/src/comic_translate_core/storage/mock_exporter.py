import time
from typing import Dict, List, Optional

from ..interfaces.exporter import IScriptExporter
from ..models import BlockContext, BlockType, ScriptBlock, ScriptExport


class MockExporter(IScriptExporter):
    """Test fixture exporter that returns deterministic ScriptExport data."""

    def __init__(self, blocks: Optional[List[ScriptBlock]] = None):
        self._blocks = blocks

    def export(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        blocks = self._blocks if self._blocks is not None else _default_blocks(variant)
        if page_range is not None:
            blocks = [b for b in blocks if b.page in page_range]

        return ScriptExport(
            version="1.0",
            comic_id=comic_id,
            base_fp=base_fp,
            script_id=f"{comic_id}_mock",
            source_lang=source_lang,
            target_lang=target_lang,
            exported_at=time.time(),
            page_range=page_range or sorted({b.page for b in blocks}),
            active_variant=variant,
            variants={variant: {}},
            glossary_snapshot={
                "Hero": {"translated": "英雄", "category": "character_name", "locked": True},
            },
            blocks=blocks,
        )


def _default_blocks(variant: str = "default") -> List[ScriptBlock]:
    return [
        ScriptBlock(
            block_id="b0",
            page=1,
            type=BlockType.DIALOGUE,
            bbox=[0, 0, 100, 50],
            original="こんにちは",
            translated="你好",
            original_variant=variant,
            context=BlockContext(speaker="Hero"),
        ),
        ScriptBlock(
            block_id="b1",
            page=1,
            type=BlockType.NARRATION,
            bbox=[0, 60, 100, 110],
            original="昔々",
            translated="從前",
            original_variant=variant,
            context=BlockContext(),
        ),
        ScriptBlock(
            block_id="b2",
            page=2,
            type=BlockType.DIALOGUE,
            bbox=[0, 0, 100, 50],
            original="さようなら",
            translated="再見",
            original_variant=variant,
            context=BlockContext(speaker="Hero"),
        ),
    ]
