import json
from pathlib import Path

from ..interfaces.storage import IScriptStorage
from ..models import (
    ScriptExport,
    QAPatchSet,
    ScriptBlock,
    BlockContext,
    BlockType,
    QAPatch,
    PatchCategory,
)


class JsonFileStorage(IScriptStorage):

    def save_script(self, script: ScriptExport, path: str) -> None:
        data = self._script_to_dict(script)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_script(self, path: str) -> ScriptExport:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._dict_to_script(data)

    def save_patch(self, patch_set: QAPatchSet, path: str) -> None:
        data = self._patch_set_to_dict(patch_set)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_patch(self, path: str) -> QAPatchSet:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._dict_to_patch_set(data)

    @staticmethod
    def _script_to_dict(script: ScriptExport) -> dict:
        return {
            "version": script.version,
            "comic_id": script.comic_id,
            "base_fp": script.base_fp,
            "script_id": script.script_id,
            "source_lang": script.source_lang,
            "target_lang": script.target_lang,
            "exported_at": script.exported_at,
            "page_range": script.page_range,
            "active_variant": script.active_variant,
            "variants": script.variants,
            "glossary_snapshot": script.glossary_snapshot,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "page": b.page,
                    "type": b.type.value,
                    "bbox": b.bbox,
                    "original": b.original,
                    "translated": b.translated,
                    "original_variant": b.original_variant,
                    "context": {
                        "speaker": b.context.speaker,
                        "prev_block": b.context.prev_block,
                        "next_block": b.context.next_block,
                    },
                    "qa_metadata": b.qa_metadata,
                }
                for b in script.blocks
            ],
        }

    @staticmethod
    def _dict_to_script(data: dict) -> ScriptExport:
        return ScriptExport(
            version=data["version"],
            comic_id=data["comic_id"],
            base_fp=data["base_fp"],
            script_id=data["script_id"],
            source_lang=data["source_lang"],
            target_lang=data["target_lang"],
            exported_at=data["exported_at"],
            page_range=data["page_range"],
            active_variant=data["active_variant"],
            variants=data["variants"],
            glossary_snapshot=data["glossary_snapshot"],
            blocks=[
                ScriptBlock(
                    block_id=b["block_id"],
                    page=b["page"],
                    type=BlockType(b["type"]),
                    bbox=b["bbox"],
                    original=b["original"],
                    translated=b["translated"],
                    original_variant=b["original_variant"],
                    context=BlockContext(**b["context"]),
                    qa_metadata=b.get("qa_metadata"),
                )
                for b in data["blocks"]
            ],
        )

    @staticmethod
    def _patch_set_to_dict(patch_set: QAPatchSet) -> dict:
        return {
            "version": patch_set.version,
            "comic_id": patch_set.comic_id,
            "base_fp": patch_set.base_fp,
            "created_at": patch_set.created_at,
            "qa_model": patch_set.qa_model,
            "chunk_range": patch_set.chunk_range,
            "summary": patch_set.summary,
            "patches": [
                {
                    "block_id": p.block_id,
                    "original": p.original,
                    "old_translated": p.old_translated,
                    "new_translated": p.new_translated,
                    "reason": p.reason,
                    "category": p.category.value,
                    "confidence": p.confidence,
                }
                for p in patch_set.patches
            ],
        }

    @staticmethod
    def _dict_to_patch_set(data: dict) -> QAPatchSet:
        return QAPatchSet(
            version=data["version"],
            comic_id=data["comic_id"],
            base_fp=data["base_fp"],
            created_at=data["created_at"],
            qa_model=data["qa_model"],
            chunk_range=data["chunk_range"],
            summary=data["summary"],
            patches=[
                QAPatch(
                    block_id=p["block_id"],
                    original=p["original"],
                    old_translated=p["old_translated"],
                    new_translated=p["new_translated"],
                    reason=p["reason"],
                    category=PatchCategory(p["category"]),
                    confidence=p["confidence"],
                )
                for p in data["patches"]
            ],
        )
