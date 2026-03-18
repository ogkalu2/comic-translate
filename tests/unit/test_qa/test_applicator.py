from comic_translate_core.models import PatchCategory, QAPatch, QAPatchSet
from comic_translate_qa.applicator import NoopApplicator


def _make_patch_set() -> QAPatchSet:
    return QAPatchSet(
        version="1.0",
        comic_id="test",
        base_fp="fp",
        created_at=0.0,
        qa_model="test",
        chunk_range={"from": "b0", "to": "b1"},
        summary={},
        patches=[
            QAPatch(
                block_id="b0",
                original="x",
                old_translated="y",
                new_translated="z",
                reason="better",
                category=PatchCategory.TONE,
                confidence=0.9,
            ),
            QAPatch(
                block_id="b1",
                original="a",
                old_translated="b",
                new_translated="c",
                reason="low conf",
                category=PatchCategory.GRAMMAR,
                confidence=0.5,
            ),
        ],
    )


class TestNoopApplicator:
    def test_counts(self):
        result = NoopApplicator().apply_patches(_make_patch_set())
        assert result["total"] == 2
        assert result["applied"] == 1
        assert result["skipped"] == 1
        assert result["failed"] == 0

    def test_details(self):
        result = NoopApplicator().apply_patches(_make_patch_set())
        assert result["details"][0]["action"] == "would_apply"
        assert result["details"][1]["action"] == "skipped"

    def test_custom_threshold(self):
        result = NoopApplicator().apply_patches(_make_patch_set(), confidence_threshold=0.4)
        assert result["applied"] == 2
        assert result["skipped"] == 0

    def test_empty_patches(self):
        empty = QAPatchSet(
            version="1.0", comic_id="t", base_fp="f", created_at=0.0,
            qa_model="m", chunk_range={}, summary={}, patches=[],
        )
        result = NoopApplicator().apply_patches(empty)
        assert result["total"] == 0
