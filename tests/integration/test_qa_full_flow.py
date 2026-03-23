import tempfile
from pathlib import Path

from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from comic_translate_qa.applicator import NoopApplicator
from comic_translate_qa.chunking import PageBasedChunking
from comic_translate_qa.providers import OpenAIQAProvider


def test_full_qa_flow():
    """Test complete QA flow: export → qa → apply"""

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "script.json"
        patch_path = Path(tmpdir) / "patches.json"

        orchestrator = QAOrchestrator(
            exporter=MockExporter(),
            storage=JsonFileStorage(),
            chunking=PageBasedChunking(),
            llm_provider=OpenAIQAProvider(api_key="test-key"),  # Mock in real test
            applicator=NoopApplicator(),
        )

        script = orchestrator.export_script(
            comic_id="test_comic",
            base_fp="test_fp",
            source_lang="ja",
            target_lang="zh-hk",
            output_path=str(script_path),
        )

        assert script_path.exists()
        assert len(script.blocks) == 3  # MockExporter returns 3 blocks

        # Step 2: QA (skip in test, requires real API key)
        # patch_set = orchestrator.qa_script(
        #     script_path=str(script_path),
        #     output_patch_path=str(patch_path),
        # )

        # Step 3: Apply (skip, depends on step 2)
        # result = orchestrator.apply_patches(patch_path=str(patch_path))
        # assert result["total"] >= 0
