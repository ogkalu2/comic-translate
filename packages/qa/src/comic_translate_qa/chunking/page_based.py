from typing import Iterator

from comic_translate_core.interfaces.chunking import IChunkingStrategy
from comic_translate_core.models import ScriptExport, QAChunk, BlockType


class PageBasedChunking(IChunkingStrategy):
    """Cut chunks on page boundaries.

    - Skip SFX/credit blocks (configurable)
    - Overlap last N blocks from previous chunk as read-only context
    """

    SKIP_TYPES = {BlockType.SFX, BlockType.CREDIT}

    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]:
        reviewable = [b for b in script.blocks if b.type not in self.SKIP_TYPES]

        i = 0
        chunk_id = 0
        while i < len(reviewable):
            chunk_blocks = reviewable[i : i + chunk_size]
            context_blocks = reviewable[max(0, i - overlap) : i] if i > 0 else []

            yield QAChunk(
                chunk_id=chunk_id,
                comic_id=script.comic_id,
                base_fp=script.base_fp,
                source_lang=script.source_lang,
                target_lang=script.target_lang,
                glossary_snapshot=script.glossary_snapshot,
                context_blocks=context_blocks,
                blocks=chunk_blocks,
            )

            i += chunk_size
            chunk_id += 1
