import json
import logging
from pathlib import Path
from typing import List, Iterator
from ..models.block_v2 import (
    Block, BlockType, OriginalText, TranslationVersion, TranslationHistory,
    SemanticRouting, TranslationStatus, TranslationSource
)

logger = logging.getLogger(__name__)

# Current schema version for forward-compatibility migrations
SCHEMA_VERSION = 1

class BlockStorage:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_block(self, block: Block) -> None:
        """Save block to JSON file."""
        # Extract base_fp from block_uid
        base_fp = block.block_uid.split(':')[0]
        blocks_dir = self.base_path / base_fp / "blocks"
        blocks_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = blocks_dir / f"{block.block_uid.replace(':', '_')}.json"
        
        data = self._block_to_dict(block)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_block(self, block_uid: str) -> Block:
        """Load block from JSON file."""
        base_fp = block_uid.split(':')[0]
        file_path = self.base_path / base_fp / "blocks" / f"{block_uid.replace(':', '_')}.json"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return self._dict_to_block(data)
    
    def list_block_uids(self, base_fp: str) -> List[str]:
        """List all block UIDs for a given base_fp.
        
        Returns UIDs only - use iter_blocks() for lazy-loaded Block objects.
        """
        blocks_dir = self.base_path / base_fp / "blocks"
        if not blocks_dir.exists():
            return []
        
        return [f.stem.replace('_', ':') for f in blocks_dir.glob("*.json")]
    
    def list_blocks(self, base_fp: str) -> List[str]:
        """Alias for list_block_uids() - deprecated, use list_block_uids() instead."""
        return self.list_block_uids(base_fp)
    
    def iter_blocks(self, base_fp: str) -> Iterator[Block]:
        """Iterate over all blocks for a given base_fp with lazy loading.
        
        Yields Block objects one at a time, suitable for large datasets
        and future Postgres migration.
        """
        for uid in self.list_block_uids(base_fp):
            try:
                yield self.load_block(uid)
            except Exception as e:
                logger.warning(f"Failed to load block {uid}: {e}")
                continue
    
    @staticmethod
    def _block_to_dict(block: Block) -> dict:
        """Serialize Block to dict with schema_version for forward-compat."""
        return {
            "schema_version": SCHEMA_VERSION,
            "block_uid": block.block_uid,
            "nsfw_flag": block.nsfw_flag,
            "type": block.type.value,
            "bbox": block.bbox,
            "original_texts": [
                {"variant_id": ot.variant_id, "lang": ot.lang, "text": ot.text}
                for ot in block.original_texts
            ],
            "translations": {
                lang: {
                    version: {
                        "text": tv.text,
                        "status": tv.status.value if isinstance(tv.status, TranslationStatus) else tv.status,
                        "weight": tv.weight,
                        "history": [
                            {
                                "action": h.action,
                                "source": h.source.value if isinstance(h.source, TranslationSource) else h.source,
                                "timestamp": h.timestamp
                            }
                            for h in tv.history
                        ],
                        "source": tv.source.value if isinstance(tv.source, TranslationSource) else tv.source
                    }
                    for version, tv in versions.items()
                }
                for lang, versions in block.translations.items()
            },
            "semantic_routing": {
                "ner_entities": block.semantic_routing.ner_entities,
                "sfx_detected": block.semantic_routing.sfx_detected,
                "route": block.semantic_routing.route
            } if block.semantic_routing else None,
            "embedding": block.embedding
        }
    
    @staticmethod
    def _dict_to_block(data: dict) -> Block:
        """Deserialize dict to Block, handling schema_version and enum migration."""
        # Handle schema version - default to 1 if missing (legacy format)
        schema_version = data.get("schema_version", 1)
        
        # Helper to convert string to enum, with fallback for unknown values
        def _to_status(val) -> TranslationStatus:
            if isinstance(val, TranslationStatus):
                return val
            try:
                return TranslationStatus(val)
            except ValueError:
                logger.warning(f"Unknown translation status '{val}', defaulting to PENDING_REVIEW")
                return TranslationStatus.PENDING_REVIEW
        
        def _to_source(val) -> TranslationSource:
            if val is None:
                return None
            if isinstance(val, TranslationSource):
                return val
            try:
                return TranslationSource(val)
            except ValueError:
                logger.warning(f"Unknown translation source '{val}', defaulting to PIPELINE")
                return TranslationSource.PIPELINE
        
        # Handle translations - gracefully handle empty dicts
        translations = {}
        for lang, versions in data.get("translations", {}).items():
            if not versions:  # Empty dict is OK
                translations[lang] = {}
                continue
            translations[lang] = {
                version: TranslationVersion(
                    text=tv["text"],
                    status=_to_status(tv["status"]),
                    weight=tv["weight"],
                    history=[
                        TranslationHistory(
                            action=h["action"],
                            source=_to_source(h["source"]),
                            timestamp=h.get("timestamp")
                        )
                        for h in tv.get("history", [])
                    ],
                    source=_to_source(tv.get("source"))
                )
                for version, tv in versions.items()
            }
        
        return Block(
            block_uid=data["block_uid"],
            nsfw_flag=data["nsfw_flag"],
            type=BlockType(data["type"]),
            bbox=data["bbox"],
            original_texts=[
                OriginalText(ot["variant_id"], ot["lang"], ot["text"])
                for ot in data["original_texts"]
            ],
            translations=translations,
            semantic_routing=SemanticRouting(**data["semantic_routing"]) if data.get("semantic_routing") else None,
            embedding=data.get("embedding")
        )
