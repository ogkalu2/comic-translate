from pipeline.comic_glossary import ComicGlossary, GlossaryCategory
from pipeline.story_context import StoryContextWindow, PageSummary

class ComicSession:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.glossary = ComicGlossary(comic_id, source_lang, target_lang)
        self.context = StoryContextWindow(comic_id)

    def build_system_prompt(self) -> str:
        return self.context.build_system_prompt(
            glossary_block=self.glossary.build_prompt_block(),
            target_lang=self.target_lang,
        )

    def enforce_glossary(self, text: str) -> str:
        return self.glossary.enforce(text)

    def add_page_summary(self, summary: PageSummary) -> None:
        self.context.add_page(summary)

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
