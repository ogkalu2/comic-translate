from typing import Dict

from comic_translate_core.interfaces.applicator import IPatchApplicator
from comic_translate_core.models import QAPatchSet


class NoopApplicator(IPatchApplicator):
    """Dry-run applicator that only prints stats.

    Does not modify any source data.
    """

    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        total = len(patch_set.patches)
        applied = sum(1 for p in patch_set.patches if p.confidence >= confidence_threshold)
        skipped = total - applied

        details = []
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
            "applied": applied,
            "skipped": skipped,
            "failed": 0,
            "details": details,
        }
