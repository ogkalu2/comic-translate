"""CacheApplicator: Apply QA patches to TranslationCacheV2."""

import time
from typing import Dict, Optional

from comic_translate_core.interfaces.applicator import IPatchApplicator
from comic_translate_core.models import QAPatchSet


class CacheApplicator(IPatchApplicator):
    """Apply QA patches back to TranslationCacheV2.

    Updates cached translations with QA-approved corrections.
    """

    def __init__(self, cache=None, cache_path: Optional[str] = None):
        """Initialize with a TranslationCacheV2 instance or path.

        Args:
            cache: TranslationCacheV2 instance. If None, will load from cache_path.
            cache_path: Path to cache JSON file. Used if cache is None.
        """
        self._cache = cache
        self._cache_path = cache_path

    def _get_cache(self):
        """Get or load the translation cache.

        Returns:
            TranslationCacheV2 instance.
        """
        if self._cache is None:
            try:
                from pipeline.cache_v2 import TranslationCacheV2
            except ImportError:
                raise ImportError(
                    "CacheApplicator requires pipeline.cache_v2 module"
                )

            if self._cache_path:
                import json
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache = TranslationCacheV2(data)
            else:
                self._cache = TranslationCacheV2()

        return self._cache

    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        """Apply patches to the translation cache.

        Args:
            patch_set: The QA patches to apply.
            dry_run: If True, only return stats without modifying cache.
            confidence_threshold: Minimum confidence to apply a patch.

        Returns:
            Dict with keys: total, applied, skipped, failed, details.
        """
        total = len(patch_set.patches)
        applied = 0
        skipped = 0
        failed = 0
        details = []

        # Filter patches by confidence
        eligible_patches = [
            p for p in patch_set.patches if p.confidence >= confidence_threshold
        ]
        skipped = total - len(eligible_patches)

        if dry_run:
            for patch in patch_set.patches:
                action = "would_apply" if patch.confidence >= confidence_threshold else "skipped"
                details.append({
                    "block_id": patch.block_id,
                    "action": action,
                    "category": patch.category.value,
                    "confidence": patch.confidence,
                    "reason": patch.reason,
                })

            return {
                "total": total,
                "applied": len(eligible_patches),
                "skipped": skipped,
                "failed": 0,
                "details": details,
            }

        cache = self._get_cache()
        src = patch_set.chunk_range.get("source_lang", "")
        tgt = patch_set.chunk_range.get("target_lang", "")

        # If source/target not in chunk_range, try to infer from first patch
        if not src or not tgt:
            # Use comic_id as a fallback key component
            src = patch_set.comic_id
            tgt = "qa_corrected"

        for patch in eligible_patches:
            try:
                # Store the corrected translation in cache
                cache.store(
                    src=src,
                    tgt=tgt,
                    source_text=patch.original,
                    translated_text=patch.new_translated,
                    model=f"qa:{patch_set.qa_model}",
                    quality_score=patch.confidence,
                )

                applied += 1
                details.append({
                    "block_id": patch.block_id,
                    "action": "applied",
                    "category": patch.category.value,
                    "confidence": patch.confidence,
                    "reason": patch.reason,
                    "old_translated": patch.old_translated,
                    "new_translated": patch.new_translated,
                })

            except Exception as e:
                failed += 1
                details.append({
                    "block_id": patch.block_id,
                    "action": "failed",
                    "category": patch.category.value,
                    "confidence": patch.confidence,
                    "reason": f"Cache update failed: {e}",
                })

        # Save cache if path is provided
        if self._cache_path:
            cache.save(self._cache_path)

        return {
            "total": total,
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "details": details,
        }
