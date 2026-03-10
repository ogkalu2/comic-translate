from pipeline.comic_glossary import ComicGlossary, GlossaryCategory
from pipeline.story_context import StoryContextWindow, PageSummary
from typing import List, Any, Optional


class ComicSession:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.glossary = ComicGlossary(comic_id, source_lang, target_lang)
        self.context = StoryContextWindow(comic_id)

    def build_system_prompt(self, free_tier: bool = False) -> str:
        return self.context.build_system_prompt(
            glossary_block=self.glossary.build_prompt_block(),
            target_lang=self.target_lang,
            free_tier=free_tier,
        )

    def enforce_glossary(self, text: str) -> str:
        return self.glossary.enforce(text)

    def add_page_summary(self, summary: PageSummary) -> None:
        self.context.add_page(summary)

    def generate_page_summary(
        self,
        page_number: int,
        blk_list: List[Any],
        emotional_tone: str = "neutral",
    ) -> PageSummary:
        """
        Build a PageSummary from OCR'd text blocks without an LLM call.
        Extracts speaker names from the glossary and concatenates block text
        as key_events. A future version can replace this with an LLM call.
        """
        texts = [blk.text for blk in blk_list if getattr(blk, "text", None)]
        key_events = " ".join(texts)[:300]  # cap at 300 chars

        # Identify speakers: glossary CHARACTER_NAME entries that appear in text
        speakers = [
            entry.source
            for entry in self.glossary._entries.values()
            if entry.category.value == "character_name"
            and entry.source in key_events
        ]

        summary = PageSummary(
            page_number=page_number,
            key_events=key_events,
            speakers_on_page=speakers,
            emotional_tone=emotional_tone,
        )
        self.context.add_page(summary)
        return summary

    def to_dict(self) -> dict:
        return {
            "comic_id": self.comic_id,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "glossary": self.glossary.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComicSession":
        s = cls(data["comic_id"], data["source_lang"], data["target_lang"])
        s.glossary = ComicGlossary.from_dict(data["glossary"])
        return s

