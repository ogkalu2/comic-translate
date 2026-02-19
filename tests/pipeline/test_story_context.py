import pytest
from pipeline.story_context import StoryContextWindow, PageSummary

def test_empty_window():
    w = StoryContextWindow(comic_id="c1")
    assert w.build_prompt_block() == ""

def test_add_and_retrieve_page():
    w = StoryContextWindow(comic_id="c1", max_pages=3)
    w.add_page(PageSummary(page_number=1, key_events="Hero arrives.", speakers_on_page=["Eren"], emotional_tone="tense"))
    block = w.build_prompt_block()
    assert "Page 1" in block
    assert "Hero arrives" in block

def test_rolling_window_drops_oldest():
    w = StoryContextWindow(comic_id="c1", max_pages=2)
    for i in range(1, 4):
        w.add_page(PageSummary(page_number=i, key_events=f"Event {i}.", speakers_on_page=[], emotional_tone="neutral"))
    block = w.build_prompt_block()
    assert "Page 1" not in block
    assert "Page 3" in block

def test_char_cap_respected():
    w = StoryContextWindow(comic_id="c1", max_pages=5, max_chars=50)
    w.add_page(PageSummary(page_number=1, key_events="A" * 200, speakers_on_page=[], emotional_tone="neutral"))
    block = w.build_prompt_block()
    assert len(block) <= 50
