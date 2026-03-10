import pytest
from unittest.mock import MagicMock
from pipeline.discovery_pass import DiscoveryPass

def _make_blk(text):
    blk = MagicMock()
    blk.text = text
    return blk

def test_accumulates_ocr_text():
    dp = DiscoveryPass(comic_id="c1", source_lang="en", target_lang="zh-hk")
    dp.add_page_ocr_results([_make_blk("Hello"), _make_blk("World")])
    dp.add_page_ocr_results([_make_blk("Eren attacked.")])
    text = dp.get_all_ocr_text()
    assert "Hello" in text
    assert "Eren attacked." in text

def test_discovery_prompt_built():
    dp = DiscoveryPass(comic_id="c1", source_lang="en", target_lang="zh-hk")
    dp.add_page_ocr_results([_make_blk("Eren ran.")])
    prompt = dp.build_discovery_prompt()
    assert "character names" in prompt.lower() or "proper noun" in prompt.lower()
    assert "Eren ran." in prompt

def test_apply_discovered_terms_to_glossary():
    dp = DiscoveryPass(comic_id="c1", source_lang="en", target_lang="zh-hk")
    from pipeline.comic_session import ComicSession
    session = ComicSession("c1", "en", "zh-hk")
    terms = [
        {"text": "Eren", "category": "character_name", "confidence": 0.95},
        {"text": "Titan", "category": "story_term", "confidence": 0.88},
    ]
    dp.apply_discovered_terms(session, terms)
    assert session.glossary.get("Eren") is not None
    assert session.glossary.get("Titan") is not None
