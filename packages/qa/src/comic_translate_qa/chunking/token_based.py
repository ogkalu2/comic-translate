"""TokenBasedChunking: Split script into chunks based on estimated token count."""

from typing import Iterator, List

from comic_translate_core.interfaces.chunking import IChunkingStrategy
from comic_translate_core.models import BlockType, QAChunk, ScriptBlock, ScriptExport


# Approximate tokens per character for different languages
TOKENS_PER_CHAR = {
    "ja": 2.0,    # Japanese: ~2 tokens per character
    "zh": 1.5,    # Chinese: ~1.5 tokens per character
    "zh-hk": 1.5,
    "zh-tw": 1.5,
    "ko": 1.8,    # Korean: ~1.8 tokens per character
    "en": 0.25,   # English: ~0.25 tokens per character (4 chars per token)
    "default": 0.4,
}


class TokenBasedChunking(IChunkingStrategy):
    """Split chunks based on estimated token count.

    Estimates tokens per block using language-specific ratios and groups
    blocks to fit within the target chunk size. This provides tighter
    packing compared to page-based chunking.
    """

    SKIP_TYPES = {BlockType.SFX, BlockType.CREDIT}

    def __init__(self, tokens_per_char: float = None):
        """Initialize with optional custom tokens-per-char ratio.

        Args:
            tokens_per_char: Override the default tokens-per-char ratio.
                           If None, uses language-specific defaults.
        """
        self._custom_ratio = tokens_per_char

    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]:
        """Split script into token-based chunks.

        Args:
            script: The script export to chunk.
            chunk_size: Target number of blocks per chunk (used as fallback).
            overlap: Number of blocks to overlap from previous chunk.

        Yields:
            QAChunk objects with blocks grouped by estimated token count.
        """
        # Filter reviewable blocks
        reviewable = [b for b in script.blocks if b.type not in self.SKIP_TYPES]

        if not reviewable:
            return

        # Get tokens-per-char ratio
        ratio = self._get_ratio(script.target_lang)

        # Estimate tokens per block
        block_tokens = [(b, self._estimate_tokens(b, ratio)) for b in reviewable]

        # Group blocks into chunks
        chunk_id = 0
        i = 0
        while i < len(block_tokens):
            chunk_blocks: List[ScriptBlock] = []
            current_tokens = 0
            target_tokens = chunk_size * 10  # Approximate: ~10 tokens per block average

            # Add blocks until we hit the token limit or block limit
            while i < len(block_tokens) and len(chunk_blocks) < chunk_size:
                block, tokens = block_tokens[i]
                if current_tokens + tokens > target_tokens and chunk_blocks:
                    break
                chunk_blocks.append(block)
                current_tokens += tokens
                i += 1

            # Get context blocks (overlap from previous chunk)
            context_start = max(0, i - len(chunk_blocks) - overlap)
            context_end = i - len(chunk_blocks)
            context_blocks = reviewable[context_start:context_end] if context_end > 0 else []

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

            chunk_id += 1

    def _get_ratio(self, lang: str) -> float:
        """Get tokens-per-char ratio for a language.

        Args:
            lang: Language code.

        Returns:
            Tokens per character ratio.
        """
        if self._custom_ratio is not None:
            return self._custom_ratio
        return TOKENS_PER_CHAR.get(lang.lower(), TOKENS_PER_CHAR["default"])

    @staticmethod
    def _estimate_tokens(block: ScriptBlock, ratio: float) -> int:
        """Estimate token count for a block.

        Args:
            block: The script block.
            ratio: Tokens per character ratio.

        Returns:
            Estimated token count.
        """
        # Count characters in original + translated text
        char_count = len(block.original) + len(block.translated)
        # Add overhead for block metadata (block_id, type, etc.)
        metadata_overhead = 20
        return int(char_count * ratio) + metadata_overhead
