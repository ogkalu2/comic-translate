from comic_translate_core.models import (
    BlockContext,
    BlockType,
    QAChunk,
    ScriptBlock,
    ScriptExport,
)
from comic_translate_qa.chunking import PageBasedChunking


def _make_script(num_blocks: int, include_sfx: bool = False) -> ScriptExport:
    blocks = []
    for i in range(num_blocks):
        btype = BlockType.SFX if (include_sfx and i % 5 == 0) else BlockType.DIALOGUE
        blocks.append(
            ScriptBlock(
                block_id=f"b{i}",
                page=i // 3 + 1,
                type=btype,
                bbox=[0, 0, 100, 50],
                original=f"text {i}",
                translated=f"trans {i}",
                original_variant="default",
                context=BlockContext(),
            )
        )
    return ScriptExport(
        version="1.0",
        comic_id="test",
        base_fp="fp",
        script_id="test:fp:en",
        source_lang="ja",
        target_lang="en",
        exported_at=0.0,
        page_range=[1, num_blocks // 3 + 1],
        active_variant="default",
        variants={},
        glossary_snapshot={},
        blocks=blocks,
    )


class TestPageBasedChunking:
    def test_single_chunk(self):
        script = _make_script(10)
        chunks = list(PageBasedChunking().chunk(script, chunk_size=80))
        assert len(chunks) == 1
        assert len(chunks[0].blocks) == 10
        assert chunks[0].context_blocks == []

    def test_multiple_chunks(self):
        script = _make_script(10)
        chunks = list(PageBasedChunking().chunk(script, chunk_size=4, overlap=2))
        assert len(chunks) == 3
        assert len(chunks[0].blocks) == 4
        assert len(chunks[0].context_blocks) == 0
        assert len(chunks[1].context_blocks) == 2
        assert chunks[1].chunk_id == 1

    def test_skips_sfx(self):
        script = _make_script(10, include_sfx=True)
        chunks = list(PageBasedChunking().chunk(script, chunk_size=80))
        for chunk in chunks:
            for block in chunk.blocks:
                assert block.type != BlockType.SFX

    def test_empty_script(self):
        script = _make_script(0)
        chunks = list(PageBasedChunking().chunk(script))
        assert len(chunks) == 0
