import time
from enum import Enum
from typing import Optional

class TranslationStatus(Enum):
    SUCCESS = "success"
    API_FAILED = "api_failed"
    UNTRANSLATABLE = "untranslatable"
    PENDING_REVIEW = "pending_review"

def _make_key(src: str, tgt: str, text: str) -> str:
    return f"{src}:{tgt}:{text}"

def _empty_store() -> dict:
    return {
        "version": "2.0",
        "saved_at": time.time(),
        "stats": {
            "total_entries": 0,
            "total_hits": 0,
            "total_misses": 0,
            "total_updates": 0,
            "failed_api_fallbacks": 0,
        },
        "entries": {},
    }

class TranslationCacheV2:
    def __init__(self, data: Optional[dict] = None):
        self.data = data if data and data.get("version") == "2.0" else _empty_store()

    def store(
        self,
        src: str,
        tgt: str,
        source_text: str,
        translated_text: str,
        model: str = "",
        status: Optional[TranslationStatus] = None,
        quality_score: float = 1.0,
    ) -> None:
        if status is None:
            status = (
                TranslationStatus.UNTRANSLATABLE
                if source_text == translated_text
                else TranslationStatus.SUCCESS
            )
        key = _make_key(src, tgt, source_text)
        now = time.time()
        existing = self.data["entries"].get(key)
        if existing:
            existing.update({
                "translated_text": translated_text,
                "updated_at": now,
                "model": model,
                "translation_status": status.value,
                "quality_score": quality_score,
                "version": existing["version"] + 1,
                "previous_translation": existing["translated_text"],
            })
            self.data["stats"]["total_updates"] += 1
        else:
            self.data["entries"][key] = {
                "source_text": source_text,
                "translated_text": translated_text,
                "source_lang": src,
                "target_lang": tgt,
                "created_at": now,
                "updated_at": now,
                "model": model,
                "confidence": quality_score,
                "usage_count": 0,
                "last_used": now,
                "quality_score": quality_score,
                "verified": False,
                "translation_status": status.value,
                "version": 1,
                "previous_translation": None,
            }
            self.data["stats"]["total_entries"] += 1

    def get(self, src: str, tgt: str, source_text: str) -> Optional[str]:
        key = _make_key(src, tgt, source_text)
        entry = self.data["entries"].get(key)
        if not entry:
            self.data["stats"]["total_misses"] += 1
            return None
        status = entry["translation_status"]
        if status in (TranslationStatus.SUCCESS.value, TranslationStatus.UNTRANSLATABLE.value):
            entry["usage_count"] += 1
            entry["last_used"] = time.time()
            self.data["stats"]["total_hits"] += 1
            return entry["translated_text"]
        self.data["stats"]["total_misses"] += 1
        return None

    def _get_entry(self, src: str, tgt: str, source_text: str) -> Optional[dict]:
        return self.data["entries"].get(_make_key(src, tgt, source_text))


def migrate_v1_to_v2(old: dict, src: str = "en", tgt: str = "en") -> dict:
    """Migrate flat KV cache to v2 schema."""
    cache = TranslationCacheV2()
    for source_text, translated_text in old.items():
        if isinstance(source_text, str) and isinstance(translated_text, str):
            status = (
                TranslationStatus.UNTRANSLATABLE
                if source_text == translated_text
                else TranslationStatus.SUCCESS
            )
            cache.store(src, tgt, source_text, translated_text,
                        status=status, quality_score=0.5)
    return cache.data
