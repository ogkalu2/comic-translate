import pytest
from pipeline.comic_session import ComicSession
from pipeline.comic_glossary import GlossaryCategory

def test_session_creates_glossary_and_context():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    assert s.glossary is not None
    assert s.context is not None

def test_session_builds_system_prompt_with_glossary():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    s.glossary.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, locked=True)
    prompt = s.build_system_prompt()
    assert "艾倫" in prompt
    assert "zh-hk" in prompt

def test_session_enforces_glossary_on_output():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    s.glossary.add("Titan", "巨人", GlossaryCategory.STORY_TERM, locked=True)
    raw = "The Giant attacked."
    enforced = s.enforce_glossary(raw)
    assert enforced == raw

def test_session_serialise_roundtrip():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    s.glossary.add("Mikasa", "三笠", GlossaryCategory.CHARACTER_NAME, locked=True)
    data = s.to_dict()
    s2 = ComicSession.from_dict(data)
    assert s2.glossary.get("Mikasa") == "三笠"
    assert s2.comic_id == "c1"
