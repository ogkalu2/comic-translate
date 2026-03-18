import json

from comic_translate_core.models import (
    BlockContext,
    BlockType,
    PatchCategory,
    QAChunk,
    ScriptBlock,
)
from comic_translate_qa.providers.openai_provider import OpenAIQAProvider


def _make_chunk() -> QAChunk:
    return QAChunk(
        chunk_id=0,
        comic_id="test_comic",
        base_fp="fp",
        source_lang="ja",
        target_lang="zh-hk",
        glossary_snapshot={
            "Hero": {"translated": "英雄", "category": "character_name", "locked": True},
            "unlocked": {"translated": "x", "category": "term", "locked": False},
        },
        context_blocks=[
            ScriptBlock(
                block_id="ctx_0",
                page=1,
                type=BlockType.DIALOGUE,
                bbox=[0, 0, 1, 1],
                original="prev",
                translated="前",
                original_variant="default",
                context=BlockContext(),
            )
        ],
        blocks=[
            ScriptBlock(
                block_id="b0",
                page=1,
                type=BlockType.DIALOGUE,
                bbox=[0, 0, 100, 50],
                original="こんにちは",
                translated="你好",
                original_variant="default",
                context=BlockContext(speaker="Hero"),
            )
        ],
    )


class TestBuildPrompt:
    def test_includes_glossary(self):
        prompt = OpenAIQAProvider._build_prompt(_make_chunk())
        assert '"Hero"' in prompt
        assert '"英雄"' in prompt
        # unlocked terms should NOT appear
        assert '"unlocked"' not in prompt

    def test_includes_context(self):
        prompt = OpenAIQAProvider._build_prompt(_make_chunk())
        assert "[ctx_0]" in prompt

    def test_includes_blocks(self):
        prompt = OpenAIQAProvider._build_prompt(_make_chunk())
        assert "[b0]" in prompt
        assert "Speaker: Hero" in prompt


class TestParseResponse:
    def test_empty_array(self):
        assert OpenAIQAProvider._parse_response("[]") == []

    def test_valid_patches(self):
        data = [
            {
                "block_id": "b0",
                "original": "x",
                "old_translated": "y",
                "new_translated": "z",
                "reason": "better",
                "category": "tone",
                "confidence": 0.9,
            }
        ]
        patches = OpenAIQAProvider._parse_response(json.dumps(data))
        assert len(patches) == 1
        assert patches[0].category == PatchCategory.TONE

    def test_strips_markdown_fences(self):
        data = [
            {
                "block_id": "b0",
                "original": "x",
                "old_translated": "y",
                "new_translated": "z",
                "reason": "r",
                "category": "grammar",
                "confidence": 0.8,
            }
        ]
        wrapped = f"```json\n{json.dumps(data)}\n```"
        patches = OpenAIQAProvider._parse_response(wrapped)
        assert len(patches) == 1

    def test_invalid_json_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Failed to parse"):
            OpenAIQAProvider._parse_response("not json")
