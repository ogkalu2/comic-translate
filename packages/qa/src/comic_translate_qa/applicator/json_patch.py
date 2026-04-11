"""JsonPatchApplicator: Apply QA patches to script JSON files."""

from typing import Dict

from comic_translate_core.interfaces.applicator import IPatchApplicator
from comic_translate_core.interfaces.storage import IScriptStorage
from comic_translate_core.models import QAPatchSet


class JsonPatchApplicator(IPatchApplicator):
    """Apply QA patches back to script JSON files.

    Loads the original script, applies patches to matching blocks,
    and saves the updated script.
    """

    def __init__(self, storage: IScriptStorage):
        """Initialize with a storage backend.

        Args:
            storage: IScriptStorage implementation for loading/saving scripts.
        """
        self.storage = storage

    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
        script_path: str = None,
        output_path: str = None,
    ) -> Dict:
        """Apply patches to a script JSON file.

        Args:
            patch_set: The QA patches to apply.
            dry_run: If True, only return stats without modifying files.
            confidence_threshold: Minimum confidence to apply a patch.
            script_path: Path to the source script JSON file.
            output_path: Path to save the updated script (defaults to script_path).

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

        if dry_run or not script_path:
            # Dry run: just return stats
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

        # Load the original script
        script = self.storage.load_script(script_path)

        # Build a lookup map for blocks
        block_map = {block.block_id: block for block in script.blocks}

        # Apply patches
        for patch in eligible_patches:
            block = block_map.get(patch.block_id)
            if block is None:
                failed += 1
                details.append({
                    "block_id": patch.block_id,
                    "action": "failed",
                    "category": patch.category.value,
                    "confidence": patch.confidence,
                    "reason": f"Block not found: {patch.block_id}",
                })
                continue

            # Apply the patch
            old_translation = block.translated
            block.translated = patch.new_translated

            # Store patch metadata
            if block.qa_metadata is None:
                block.qa_metadata = {}
            block.qa_metadata["last_qa_patch"] = {
                "old_translated": old_translation,
                "new_translated": patch.new_translated,
                "reason": patch.reason,
                "category": patch.category.value,
                "confidence": patch.confidence,
            }

            applied += 1
            details.append({
                "block_id": patch.block_id,
                "action": "applied",
                "category": patch.category.value,
                "confidence": patch.confidence,
                "reason": patch.reason,
                "old_translated": old_translation,
                "new_translated": patch.new_translated,
            })

        # Save the updated script
        save_path = output_path or script_path
        self.storage.save_script(script, save_path)

        return {
            "total": total,
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "details": details,
        }
