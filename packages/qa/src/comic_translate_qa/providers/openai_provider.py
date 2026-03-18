import json
from typing import List

from comic_translate_core.interfaces import ILLMProvider
from comic_translate_core.models import QAChunk, QAPatch, PatchCategory


try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI provider requires: pip install openai")


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


class OpenAIQAProvider(ILLMProvider):

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def review_chunk(
        self,
        chunk: QAChunk,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> List[QAPatch]:
        prompt = self._build_prompt(chunk)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content.strip()
        return self._parse_response(content)

    def get_model_name(self) -> str:
        return self.model

    @staticmethod
    def _build_prompt(chunk: QAChunk) -> str:
        glossary_lines = [
            f'- "{src}" → "{entry["translated"]}" ({entry["category"]})'
            for src, entry in chunk.glossary_snapshot.items()
            if entry.get("locked", False)
        ]
        glossary_block = "\n".join(glossary_lines) if glossary_lines else "(No locked terms)"

        context_lines = [
            f'[{b.block_id}] {b.original} → {b.translated}'
            for b in chunk.context_blocks
        ]
        context_blocks_text = "\n".join(context_lines) if context_lines else "(No previous context)"

        review_lines = []
        for b in chunk.blocks:
            speaker = b.context.speaker or ""
            speaker_tag = f" (Speaker: {speaker})" if speaker else ""
            review_lines.append(
                f'[{b.block_id}] Type: {b.type.value}{speaker_tag}\n'
                f'  Original: {b.original}\n'
                f'  Translated: {b.translated}'
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
        content = content.strip()
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
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nContent: {content}")

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
