import time
from collections import Counter
from typing import Dict, List, Optional

from ..interfaces import (
    IChunkingStrategy,
    ILLMProvider,
    IPatchApplicator,
    IScriptExporter,
    IScriptStorage,
)
from ..models import QAPatch, QAPatchSet, ScriptExport


class QAOrchestrator:
    """Coordinates export → chunk → QA → patch → apply.

    Uses dependency injection for all strategies.
    """

    def __init__(
        self,
        exporter: IScriptExporter,
        storage: IScriptStorage,
        chunking: IChunkingStrategy,
        llm_provider: ILLMProvider,
        applicator: IPatchApplicator,
    ):
        self.exporter = exporter
        self.storage = storage
        self.chunking = chunking
        self.llm_provider = llm_provider
        self.applicator = applicator

    def export_script(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        output_path: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        """Export comic to script JSON."""
        script = self.exporter.export(
            comic_id, base_fp, source_lang, target_lang, page_range, variant
        )
        self.storage.save_script(script, output_path)
        return script

    def qa_script(
        self,
        script_path: str,
        output_patch_path: str,
        chunk_size: int = 80,
        overlap: int = 5,
        temperature: float = 0.3,
    ) -> QAPatchSet:
        """Run QA on script and generate patch set."""
        script = self.storage.load_script(script_path)
        all_patches: List[QAPatch] = []
        total_blocks_reviewed = 0

        for chunk in self.chunking.chunk(script, chunk_size, overlap):
            patches = self.llm_provider.review_chunk(chunk, temperature)
            all_patches.extend(patches)
            total_blocks_reviewed += len(chunk.blocks)

        first_id = script.blocks[0].block_id if script.blocks else ""
        last_id = script.blocks[-1].block_id if script.blocks else ""

        patch_set = QAPatchSet(
            version="1.0",
            comic_id=script.comic_id,
            base_fp=script.base_fp,
            created_at=time.time(),
            qa_model=self.llm_provider.get_model_name(),
            chunk_range={"from": first_id, "to": last_id},
            summary=self._build_summary(all_patches, total_blocks_reviewed),
            patches=all_patches,
        )

        self.storage.save_patch(patch_set, output_patch_path)
        return patch_set

    def apply_patches(
        self,
        patch_path: str,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        """Apply patches from file."""
        patch_set = self.storage.load_patch(patch_path)
        return self.applicator.apply_patches(patch_set, dry_run, confidence_threshold)

    @staticmethod
    def _build_summary(patches: List[QAPatch], total_reviewed: int) -> Dict:
        categories = Counter(p.category.value for p in patches)
        return {
            "total_reviewed": total_reviewed,
            "total_patched": len(patches),
            "categories": dict(categories),
        }
