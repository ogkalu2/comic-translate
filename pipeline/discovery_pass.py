from typing import List, Any
from pipeline.comic_glossary import GlossaryCategory
from pipeline.comic_session import ComicSession

_CATEGORY_MAP = {
    "character_name": GlossaryCategory.CHARACTER_NAME,
    "faction_name": GlossaryCategory.FACTION_NAME,
    "location_name": GlossaryCategory.LOCATION_NAME,
    "story_term": GlossaryCategory.STORY_TERM,
    "sfx": GlossaryCategory.SFX,
    "title_honorific": GlossaryCategory.TITLE_HONORIFIC,
}

_DISCOVERY_PROMPT_TEMPLATE = """\
You are analyzing raw OCR text from a comic.
Identify ALL of the following without translating them:
- Character names
- Location names
- Organization/faction names
- Special terms, powers, or story-specific vocabulary
- Sound effects (SFX)

Return as JSON: {{"terms": [{{"text": "...", "category": "...", "confidence": 0.0}}]}}
Only return the JSON, no explanation.

OCR Text from all pages:
{all_ocr_text}
"""

class DiscoveryPass:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._page_texts: List[str] = []

    def add_page_ocr_results(self, blk_list: List[Any]) -> None:
        page_text = " ".join(blk.text for blk in blk_list if blk.text)
        self._page_texts.append(page_text)

    def get_all_ocr_text(self) -> str:
        return "\n".join(self._page_texts)

    def build_discovery_prompt(self) -> str:
        return _DISCOVERY_PROMPT_TEMPLATE.format(
            all_ocr_text=self.get_all_ocr_text()
        )

    def apply_discovered_terms(
        self,
        session: ComicSession,
        terms: List[dict],
        confidence_threshold: float = 0.7,
    ) -> None:
        for term in terms:
            text = term.get("text", "").strip()
            category_str = term.get("category", "story_term")
            confidence = term.get("confidence", 0.0)
            if not text:
                continue
            category = _CATEGORY_MAP.get(category_str, GlossaryCategory.STORY_TERM)
            locked = confidence >= confidence_threshold
            session.glossary.add(
                source=text,
                translated=text,
                category=category,
                locked=locked,
            )
