"""Base QA Provider with shared prompt building, response parsing, and batch processing."""

import json
import time
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from comic_translate_core.interfaces import ILLMProvider
from comic_translate_core.models import QAChunk, QAPatch, PatchCategory


QA_PROMPT_TEMPLATE = """\
You are a professional comic translator QA reviewer.

## Context

- Source: {source_lang} → Target: {target_lang}
- Comic: {comic_id}

## Locked Glossary (use these translations exactly)

{glossary_block}

## Previous Context (do NOT patch these)

{context_blocks_text}

## Blocks to Review

{blocks_to_review}

## Review Categories (priority order)

1. glossary_consistency — violates locked glossary terms
2. tone — unnatural, wrong register, doesn't match character voice
3. grammar — errors, awkward phrasing, machine translation artifacts

## Target Language Notes

- zh-HK: natural Hong Kong written style (書面語 with 口語 flavor)
- yue: pure Cantonese colloquial (純粵語口語)

## Rules

- Only patch blocks with clear issues (confidence >= 0.7)
- Preserve character personality and speech patterns
- If a translation is already good, skip it

## Output

Return ONLY a JSON array:
[
  {{"block_id": "...", "original": "...", "old_translated": "...", "new_translated": "...",
   "reason": "...", "category": "glossary_consistency|tone|grammar", "confidence": 0.0}}
]

If no issues: []
"""


class BaseQAProvider(ILLMProvider):
    """Base class for LLM-based QA providers with shared functionality.

    Subclasses only need to implement _call_llm() for the actual API call.
    Prompt building, response parsing, and batch processing are shared.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize base QA provider.

        Args:
            model: Model name/identifier.
            temperature: Sampling temperature (0.0-1.0).
            max_tokens: Maximum tokens in response.
            max_retries: Maximum retry attempts for transient errors.
            retry_delay: Base delay between retries (exponential backoff).
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def review_chunk(
        self,
        chunk: QAChunk,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> List[QAPatch]:
        """Review a single QA chunk.

        Args:
            chunk: The QA chunk to review.
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.

        Returns:
            List of QAPatch objects for issues found.
        """
        prompt = self._build_prompt(chunk)
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        content = self._call_with_retry(prompt, temp, tokens)
        return self._parse_response(content)

    def review_chunks_batch(
        self,
        chunks: List[QAChunk],
        max_workers: int = 4,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> List[QAPatch]:
        """Review multiple QA chunks in parallel.

        Args:
            chunks: List of QA chunks to review.
            max_workers: Maximum parallel workers.
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.

        Returns:
            Combined list of QAPatch objects from all chunks.
        """
        if not chunks:
            return []

        if len(chunks) == 1:
            return self.review_chunk(chunks[0], temperature, max_tokens)

        all_patches: List[QAPatch] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(
                    self.review_chunk, chunk, temperature, max_tokens
                ): chunk
                for chunk in chunks
            }

            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    patches = future.result()
                    all_patches.extend(patches)
                except Exception as e:
                    raise RuntimeError(
                        f"QA failed for chunk {chunk.chunk_id}: {e}"
                    ) from e

        return all_patches

    def _call_with_retry(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call LLM with exponential backoff retry.

        Args:
            prompt: The prompt to send.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            Raw response content string.
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._call_llm(prompt, temperature, max_tokens)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)

        raise RuntimeError(
            f"{self.get_model_name()} QA failed after {self.max_retries} attempts: {last_error}"
        )

    @abstractmethod
    def _call_llm(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call the LLM API. Subclasses must implement this.

        Args:
            prompt: The prompt to send.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            Raw response content string.
        """
        ...

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model

    @staticmethod
    def _build_prompt(chunk: QAChunk) -> str:
        """Build the QA prompt from a chunk.

        Args:
            chunk: The QA chunk to build prompt for.

        Returns:
            Formatted prompt string.
        """
        glossary_lines = [
            f'- "{src}" → "{entry["translated"]}" ({entry["category"]})'
            for src, entry in chunk.glossary_snapshot.items()
            if entry.get("locked", False)
        ]
        glossary_block = (
            "\n".join(glossary_lines) if glossary_lines else "(No locked terms)"
        )

        context_lines = [
            f"[{b.block_id}] {b.original} → {b.translated}"
            for b in chunk.context_blocks
        ]
        context_blocks_text = (
            "\n".join(context_lines) if context_lines else "(No previous context)"
        )

        review_lines = []
        for b in chunk.blocks:
            speaker = b.context.speaker or ""
            speaker_tag = f" (Speaker: {speaker})" if speaker else ""
            review_lines.append(
                f"[{b.block_id}] Type: {b.type.value}{speaker_tag}\n"
                f"  Original: {b.original}\n"
                f"  Translated: {b.translated}"
            )
        blocks_to_review = "\n\n".join(review_lines)

        return QA_PROMPT_TEMPLATE.format(
            source_lang=chunk.source_lang,
            target_lang=chunk.target_lang,
            comic_id=chunk.comic_id,
            glossary_block=glossary_block,
            context_blocks_text=context_blocks_text,
            blocks_to_review=blocks_to_review,
        )

    @staticmethod
    def _parse_response(content: str) -> List[QAPatch]:
        """Parse LLM JSON response into QAPatch objects.

        Args:
            content: Raw response content from LLM.

        Returns:
            List of QAPatch objects.

        Raises:
            ValueError: If response cannot be parsed as valid JSON.
        """
        content = content.strip()

        # Strip markdown code fences if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        if not content or content == "[]":
            return []

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse LLM response as JSON: {e}\nContent: {content}"
            )

        patches: List[QAPatch] = []
        for item in data:
            patches.append(
                QAPatch(
                    block_id=item["block_id"],
                    original=item["original"],
                    old_translated=item["old_translated"],
                    new_translated=item["new_translated"],
                    reason=item["reason"],
                    category=PatchCategory(item["category"]),
                    confidence=item["confidence"],
                )
            )

        return patches
