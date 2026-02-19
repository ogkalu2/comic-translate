import pytest
from pipeline.comic_glossary import ComicGlossary, GlossaryEntry, GlossaryCategory

def test_empty_glossary():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    assert g.get("Eren") is None

def test_add_and_retrieve_locked_entry():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    g.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, first_seen_page=1, locked=True)
    assert g.get("Eren") == "艾倫"

def test_locked_entry_not_overwritten():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    g.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, locked=True)
    g.add("Eren", "愛倫", GlossaryCategory.CHARACTER_NAME, locked=False)
    assert g.get("Eren") == "艾倫"

def test_enforce_glossary_replaces_violations():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    g.add("Titan", "巨人", GlossaryCategory.STORY_TERM, locked=True)
    fixed = g.enforce("The 巨人 attacked the village.")
    assert "巨人" in fixed

def test_to_dict_and_from_dict_roundtrip():
    g = ComicGlossary(comic_id="c1", source_lang="en", target_lang="zh-hk")
    g.add("Mikasa", "三笠", GlossaryCategory.CHARACTER_NAME, locked=True)
    data = g.to_dict()
    g2 = ComicGlossary.from_dict(data)
    assert g2.get("Mikasa") == "三笠"

def test_locked_entries_list():
    g = ComicGlossary(comic_id="c1", source_lang="en", target_lang="zh-hk")
    g.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, locked=True)
    g.add("village", "村莊", GlossaryCategory.STORY_TERM, locked=False)
    locked = g.locked_entries()
    assert len(locked) == 1
    assert locked[0].source == "Eren"
