"""Unit tests for core data models."""
import pytest

from comic_translate_core.models import (
    BlockType,
    BlockContext,
    ScriptBlock,
    ScriptExport,
    PatchCategory,
    QAPatch,
    QAPatchSet,
    QAChunk,
)


class TestBlockType:
    def test_enum_values(self):
        assert BlockType.DIALOGUE == "dialogue"
        assert BlockType.NARRATION == "narration"
        assert BlockType.SFX == "sfx"
        assert BlockType.CREDIT == "credit"

    def test_from_string(self):
        assert BlockType("dialogue") is BlockType.DIALOGUE
        assert BlockType("sfx") is BlockType.SFX


class TestBlockContext:
    def test_defaults(self):
        ctx = BlockContext()
        assert ctx.speaker is None
        assert ctx.prev_block is None
        assert ctx.next_block is None

    def test_with_values(self):
        ctx = BlockContext(speaker="Alice", prev_block="p1_b0", next_block="p1_b2")
        assert ctx.speaker == "Alice"
        assert ctx.prev_block == "p1_b0"
        assert ctx.next_block == "p1_b2"


class TestScriptBlock:
    def test_creation(self):
        block = ScriptBlock(
            block_id="p1_b0",
            page=1,
            type=BlockType.DIALOGUE,
            bbox=[10, 20, 100, 80],
            original="Hello",
            translated="你好",
            original_variant="default",
            context=BlockContext(speaker="Alice"),
        )
        assert block.block_id == "p1_b0"
        assert block.page == 1
        assert block.type is BlockType.DIALOGUE
        assert block.bbox == [10, 20, 100, 80]
        assert block.original == "Hello"
        assert block.translated == "你好"
        assert block.qa_metadata is None

    def test_optional_qa_metadata(self):
        block = ScriptBlock(
            block_id="p1_b0",
            page=1,
            type=BlockType.NARRATION,
            bbox=[0, 0, 50, 50],
            original="text",
            translated="翻譯",
            original_variant="default",
            context=BlockContext(),
            qa_metadata={"reviewed": True},
        )
        assert block.qa_metadata == {"reviewed": True}


class TestScriptExport:
    def test_creation(self):
        block = ScriptBlock(
            block_id="p1_b0",
            page=1,
            type=BlockType.DIALOGUE,
            bbox=[10, 20, 100, 80],
            original="Hello",
            translated="你好",
            original_variant="default",
            context=BlockContext(),
        )
        script = ScriptExport(
            version="1.0",
            comic_id="comic_001",
            base_fp="/path/to/comic",
            script_id="comic_001:/path:zh-hk",
            source_lang="ja",
            target_lang="zh-hk",
            exported_at=1700000000.0,
            page_range=[1, 3],
            active_variant="default",
            variants={"default": {"censored": False}},
            glossary_snapshot={"Hero": {"translated": "英雄", "locked": True}},
            blocks=[block],
        )
        assert script.comic_id == "comic_001"
        assert script.source_lang == "ja"
        assert script.target_lang == "zh-hk"
        assert len(script.blocks) == 1
        assert script.blocks[0].block_id == "p1_b0"


class TestPatchCategory:
    def test_enum_values(self):
        assert PatchCategory.GLOSSARY_CONSISTENCY == "glossary_consistency"
        assert PatchCategory.TONE == "tone"
        assert PatchCategory.GRAMMAR == "grammar"
        assert PatchCategory.STYLE == "style"
        assert PatchCategory.LOCALIZATION == "localization"


class TestQAPatch:
    def test_creation(self):
        patch = QAPatch(
            block_id="p1_b0",
            original="Hello",
            old_translated="你好",
            new_translated="嗨",
            reason="More natural greeting",
            category=PatchCategory.TONE,
            confidence=0.85,
        )
        assert patch.block_id == "p1_b0"
        assert patch.category is PatchCategory.TONE
        assert patch.confidence == 0.85


class TestQAPatchSet:
    def test_creation(self):
        patch = QAPatch(
            block_id="p1_b0",
            original="Hello",
            old_translated="你好",
            new_translated="嗨",
            reason="tone",
            category=PatchCategory.TONE,
            confidence=0.9,
        )
        patch_set = QAPatchSet(
            version="1.0",
            comic_id="comic_001",
            base_fp="/path",
            created_at=1700000000.0,
            qa_model="gpt-4o-mini",
            chunk_range={"from": "p1_b0", "to": "p3_b2"},
            summary={"total_reviewed": 9, "total_patched": 1},
            patches=[patch],
        )
        assert patch_set.qa_model == "gpt-4o-mini"
        assert len(patch_set.patches) == 1
        assert patch_set.summary["total_patched"] == 1


class TestQAChunk:
    def test_creation(self):
        block = ScriptBlock(
            block_id="p1_b0",
            page=1,
            type=BlockType.DIALOGUE,
            bbox=[10, 20, 100, 80],
            original="Hello",
            translated="你好",
            original_variant="default",
            context=BlockContext(),
        )
        chunk = QAChunk(
            chunk_id=0,
            comic_id="comic_001",
            base_fp="/path",
            source_lang="ja",
            target_lang="zh-hk",
            glossary_snapshot={},
            context_blocks=[],
            blocks=[block],
        )
        assert chunk.chunk_id == 0
        assert len(chunk.blocks) == 1
        assert chunk.context_blocks == []
