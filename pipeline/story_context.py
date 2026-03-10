from dataclasses import dataclass, field
from typing import List
from collections import deque

@dataclass
class PageSummary:
    page_number: int
    key_events: str
    speakers_on_page: List[str]
    emotional_tone: str

class StoryContextWindow:
    def __init__(self, comic_id: str, max_pages: int = 5, max_chars: int = 2000):
        self.comic_id = comic_id
        self.max_pages = max_pages
        self.max_chars = max_chars
        self._pages: deque = deque(maxlen=max_pages)

    def add_page(self, summary: PageSummary) -> None:
        self._pages.append(summary)

    def build_prompt_block(self) -> str:
        lines = [
            f"Page {p.page_number}: {p.key_events} [Tone: {p.emotional_tone}]"
            for p in list(self._pages)[-3:]
        ]
        result = "\n".join(lines)
        return result[:self.max_chars]

    def build_system_prompt(
        self,
        glossary_block: str,
        target_lang: str,
        free_tier: bool = False,
    ) -> str:
        context = self.build_prompt_block()
        # Cap context for free-tier models to stay within token budgets
        if free_tier and len(context) > 500:
            context = context[:500]
        parts = [f"You are translating a comic into {target_lang}."]
        if glossary_block:
            parts.append(f"\nLOCKED GLOSSARY — use these exactly:\n{glossary_block}")
        if context:
            parts.append(f"\nRECENT STORY CONTEXT:\n{context}")
        parts.append(
            "\nRULES:\n"
            "1. Preserve each character's consistent speech style.\n"
            "2. Never retranslate any term in the locked glossary.\n"
            "3. Keep SFX punchy and short.\n"
            "4. Return only the translated text, no explanation."
        )
        return "\n".join(parts)
