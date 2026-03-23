import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

from comic_translate_core.models import PatchCategory, QAPatch, QAChunk
from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from comic_translate_qa.applicator import NoopApplicator
from comic_translate_qa.chunking import PageBasedChunking


def _stub_provider(patches: List[QAPatch]):
    """Create a mock LLM provider that returns fixed patches."""
    provider = MagicMock()
    provider.review_chunk.return_value = patches
    provider.get_model_name.return_value = "stub-model"
    return provider


class TestQAOrchestrator:
    def test_export_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = str(Path(tmpdir) / "script.json")
            orchestrator = QAOrchestrator(
                exporter=MockExporter(),
                storage=JsonFileStorage(),
                chunking=PageBasedChunking(),
                llm_provider=_stub_provider([]),
                applicator=NoopApplicator(),
            )
            script = orchestrator.export_script(
                comic_id="test",
                base_fp="fp",
                source_lang="ja",
                target_lang="zh-hk",
                output_path=script_path,
            )
            assert Path(script_path).exists()
            assert script.comic_id == "test"
            assert len(script.blocks) > 0

    def test_qa_script_no_patches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = str(Path(tmpdir) / "script.json")
            patch_path = str(Path(tmpdir) / "patches.json")
            orchestrator = QAOrchestrator(
                exporter=MockExporter(),
                storage=JsonFileStorage(),
                chunking=PageBasedChunking(),
                llm_provider=_stub_provider([]),
                applicator=NoopApplicator(),
            )
            orchestrator.export_script(
                comic_id="test", base_fp="fp",
                source_lang="ja", target_lang="zh-hk",
                output_path=script_path,
            )
            patch_set = orchestrator.qa_script(
                script_path=script_path,
                output_patch_path=patch_path,
            )
            assert Path(patch_path).exists()
            assert patch_set.patches == []
            assert patch_set.summary["total_patched"] == 0

    def test_qa_script_with_patches(self):
        patch = QAPatch(
            block_id="b0",
            original="x",
            old_translated="y",
            new_translated="z",
            reason="better",
            category=PatchCategory.TONE,
            confidence=0.9,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = str(Path(tmpdir) / "script.json")
            patch_path = str(Path(tmpdir) / "patches.json")
            orchestrator = QAOrchestrator(
                exporter=MockExporter(),
                storage=JsonFileStorage(),
                chunking=PageBasedChunking(),
                llm_provider=_stub_provider([patch]),
                applicator=NoopApplicator(),
            )
            orchestrator.export_script(
                comic_id="test", base_fp="fp",
                source_lang="ja", target_lang="zh-hk",
                output_path=script_path,
            )
            patch_set = orchestrator.qa_script(
                script_path=script_path,
                output_patch_path=patch_path,
            )
            assert len(patch_set.patches) >= 1
            assert patch_set.qa_model == "stub-model"

    def test_apply_patches(self):
        patch = QAPatch(
            block_id="b0",
            original="x",
            old_translated="y",
            new_translated="z",
            reason="better",
            category=PatchCategory.TONE,
            confidence=0.9,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = str(Path(tmpdir) / "script.json")
            patch_path = str(Path(tmpdir) / "patches.json")
            orchestrator = QAOrchestrator(
                exporter=MockExporter(),
                storage=JsonFileStorage(),
                chunking=PageBasedChunking(),
                llm_provider=_stub_provider([patch]),
                applicator=NoopApplicator(),
            )
            orchestrator.export_script(
                comic_id="test", base_fp="fp",
                source_lang="ja", target_lang="zh-hk",
                output_path=script_path,
            )
            orchestrator.qa_script(
                script_path=script_path,
                output_patch_path=patch_path,
            )
            result = orchestrator.apply_patches(patch_path=patch_path)
            assert result["total"] >= 1
            assert "applied" in result
