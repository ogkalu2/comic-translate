import tempfile
from pathlib import Path

from comic_translate_core.models import (
    BlockContext,
    BlockType,
    PatchCategory,
    QAPatch,
    QAPatchSet,
    ScriptBlock,
    ScriptExport,
)
from comic_translate_core.storage import JsonFileStorage


def _make_script() -> ScriptExport:
    return ScriptExport(
        version="1.0",
        comic_id="test",
        base_fp="fp123",
        script_id="test:fp123:en",
        source_lang="ja",
        target_lang="en",
        exported_at=1000.0,
        page_range=[1, 2],
        active_variant="default",
        variants={"default": {"censored": False}},
        glossary_snapshot={"hero": {"translated": "Hero", "locked": True}},
        blocks=[
            ScriptBlock(
                block_id="p1_b0",
                page=1,
                type=BlockType.DIALOGUE,
                bbox=[0, 0, 100, 50],
                original="こんにちは",
                translated="Hello",
                original_variant="default",
                context=BlockContext(speaker="A"),
            )
        ],
    )


def _make_patch_set() -> QAPatchSet:
    return QAPatchSet(
        version="1.0",
        comic_id="test",
        base_fp="fp123",
        created_at=2000.0,
        qa_model="gpt-4o-mini",
        chunk_range={"from": "p1_b0", "to": "p1_b0"},
        summary={"total_reviewed": 1, "total_patched": 1},
        patches=[
            QAPatch(
                block_id="p1_b0",
                original="こんにちは",
                old_translated="Hello",
                new_translated="Hi there",
                reason="More natural",
                category=PatchCategory.TONE,
                confidence=0.85,
            )
        ],
    )


class TestJsonFileStorage:
    def test_script_roundtrip(self):
        storage = JsonFileStorage()
        script = _make_script()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "script.json")
            storage.save_script(script, path)
            loaded = storage.load_script(path)
            assert loaded.comic_id == script.comic_id
            assert loaded.blocks[0].block_id == "p1_b0"
            assert loaded.blocks[0].type == BlockType.DIALOGUE
            assert loaded.blocks[0].context.speaker == "A"

    def test_patch_roundtrip(self):
        storage = JsonFileStorage()
        patch_set = _make_patch_set()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "patches.json")
            storage.save_patch(patch_set, path)
            loaded = storage.load_patch(path)
            assert loaded.comic_id == patch_set.comic_id
            assert len(loaded.patches) == 1
            assert loaded.patches[0].category == PatchCategory.TONE
            assert loaded.patches[0].confidence == 0.85

    def test_creates_parent_dirs(self):
        storage = JsonFileStorage()
        script = _make_script()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "nested" / "dir" / "script.json")
            storage.save_script(script, path)
            assert Path(path).exists()
