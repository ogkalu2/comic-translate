import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class GlossaryCategory(str, Enum):
    CHARACTER_NAME = "character_name"
    FACTION_NAME = "faction_name"
    LOCATION_NAME = "location_name"
    STORY_TERM = "story_term"
    SFX = "sfx"
    TITLE_HONORIFIC = "title_honorific"

@dataclass
class GlossaryEntry:
    source: str
    translated: str
    category: GlossaryCategory
    first_seen_page: int = 1
    locked: bool = False
    notes: Optional[str] = None
    known_variants: List[str] = field(default_factory=list)

class ComicGlossary:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.version = 1
        self.last_updated = time.time()
        self._entries: Dict[str, GlossaryEntry] = {}

    def add(self, source: str, translated: str, category: GlossaryCategory,
            first_seen_page: int = 1, locked: bool = False,
            notes: Optional[str] = None) -> None:
        existing = self._entries.get(source)
        if existing and existing.locked:
            return
        self._entries[source] = GlossaryEntry(
            source=source, translated=translated, category=category,
            first_seen_page=first_seen_page, locked=locked, notes=notes,
        )
        self.last_updated = time.time()

    def get(self, source: str) -> Optional[str]:
        entry = self._entries.get(source)
        return entry.translated if entry else None

    def locked_entries(self) -> List[GlossaryEntry]:
        return [e for e in self._entries.values() if e.locked]

    def enforce(self, text: str) -> str:
        result = text
        for entry in self.locked_entries():
            for variant in entry.known_variants:
                result = result.replace(variant, entry.translated)
        return result

    def build_prompt_block(self) -> str:
        lines = [
            f'- "{e.source}" -> "{e.translated}" ({e.category.value})'
            for e in self.locked_entries()
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "comic_id": self.comic_id,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "version": self.version,
            "last_updated": self.last_updated,
            "entries": {
                k: {
                    "source": e.source, "translated": e.translated,
                    "category": e.category.value, "first_seen_page": e.first_seen_page,
                    "locked": e.locked, "notes": e.notes,
                    "known_variants": e.known_variants,
                }
                for k, e in self._entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComicGlossary":
        g = cls(data["comic_id"], data["source_lang"], data["target_lang"])
        g.version = data.get("version", 1)
        g.last_updated = data.get("last_updated", time.time())
        for k, v in data.get("entries", {}).items():
            g._entries[k] = GlossaryEntry(
                source=v["source"], translated=v["translated"],
                category=GlossaryCategory(v["category"]),
                first_seen_page=v.get("first_seen_page", 1),
                locked=v.get("locked", False), notes=v.get("notes"),
                known_variants=v.get("known_variants", []),
            )
        return g
