"""
Unit tests for the routing module.
"""

import pytest
from comic_translate_core.models.block_v2 import Block, BlockType, OriginalText
from comic_translate_core.models.routing import RoutingDecision, TranslatorType
from comic_translate_core.routing import SemanticRouter, NSFWDetector, SFXDetector


class TestNSFWDetector:
    """Tests for NSFWDetector class."""
    
    def test_detect_empty_text(self):
        detector = NSFWDetector()
        assert detector.detect("") is False
        assert detector.detect(None) is False
    
    def test_detect_clean_text(self):
        detector = NSFWDetector()
        assert detector.detect("Hello world") is False
        assert detector.detect("This is a normal sentence") is False
    
    def test_detect_nsfw_keywords(self):
        detector = NSFWDetector()
        assert detector.detect("This is NSFW content") is True
        assert detector.detect("Hentai manga") is True
        assert detector.detect("R18 restricted") is True
    
    def test_detect_custom_keywords(self):
        detector = NSFWDetector(custom_keywords=["custom_nsfw"])
        assert detector.detect("This is custom_nsfw content") is True
    
    def test_detect_from_ehtag_empty(self):
        detector = NSFWDetector()
        assert detector.detect_from_ehtag("", {}) is False
        assert detector.detect_from_ehtag("text", {}) is False
        assert detector.detect_from_ehtag("", {"tag": "nsfw"}) is False
    
    def test_detect_from_ehtag_match(self):
        detector = NSFWDetector()
        ehtag_dict = {"sex": "nsfw", "nudity": "nsfw", "action": "safe"}
        assert detector.detect_from_ehtag("This has sex content", ehtag_dict) is True
        assert detector.detect_from_ehtag("This has nudity", ehtag_dict) is True
        assert detector.detect_from_ehtag("This is action packed", ehtag_dict) is False


class TestSFXDetector:
    """Tests for SFXDetector class."""
    
    def test_detect_empty(self):
        detector = SFXDetector()
        assert detector.detect("", [0, 0, 100, 100]) is False
        assert detector.detect("text", []) is False
    
    def test_detect_url_is_not_sfx(self):
        detector = SFXDetector()
        assert detector.detect("https://example.com", [0, 0, 100, 100]) is False
        assert detector.detect("www.example.com", [0, 0, 100, 100]) is False
    
    def test_detect_sfx_patterns(self):
        detector = SFXDetector()
        assert detector.detect("ドン", [0, 0, 100, 100]) is True
        assert detector.detect("BOOM", [0, 0, 100, 100]) is True
        assert detector.detect("Crash!", [0, 0, 100, 100]) is True
    
    def test_detect_short_text_large_bbox(self):
        detector = SFXDetector(min_bbox_area=5000)
        # Large bbox: 100x100 = 10000 area
        assert detector.detect("AB", [0, 0, 100, 100]) is True
        # Small bbox: 10x10 = 100 area
        assert detector.detect("AB", [0, 0, 10, 10]) is False
    
    def test_detect_very_short_text(self):
        detector = SFXDetector(min_bbox_area=5000)
        # Very short text with large bbox → SFX
        assert detector.detect("A", [0, 0, 100, 100]) is True
        assert detector.detect("AB", [0, 0, 100, 100]) is True
        assert detector.detect("ABC", [0, 0, 100, 100]) is True
        # Very short text with small bbox → not SFX
        assert detector.detect("A", [0, 0, 10, 10]) is False
        assert detector.detect("AB", [0, 0, 10, 10]) is False
        assert detector.detect("ABC", [0, 0, 10, 10]) is False
    
    def test_is_credit_with_url(self):
        detector = SFXDetector()
        assert detector.is_credit("Visit https://example.com", [0, 0, 100, 100]) is True
        assert detector.is_credit("www.manga-artist.jp", [0, 0, 100, 100]) is True
    
    def test_is_credit_corner_position(self):
        detector = SFXDetector()
        # Top-left corner (within 20% of edges)
        assert detector.is_credit("Artist Name", [10, 10, 100, 50]) is True
        # Center position
        assert detector.is_credit("Artist Name", [400, 600, 600, 700]) is False


class TestSemanticRouter:
    """Tests for SemanticRouter class."""
    
    _uid_counter = 0
    
    def _make_block(
        self,
        block_type: BlockType,
        text: str = "test",
        nsfw_flag: bool = False,
        bbox: list = None,
    ) -> Block:
        """Helper to create a test block."""
        if bbox is None:
            bbox = [0, 0, 100, 100]
        TestSemanticRouter._uid_counter += 1
        return Block(
            block_uid=f"test_uid_{TestSemanticRouter._uid_counter}",
            nsfw_flag=nsfw_flag,
            type=block_type,
            bbox=bbox,
            original_texts=[OriginalText(variant_id="test", lang="ja", text=text)],
            translations={},
            semantic_routing=None,
            embedding=None,
        )
    
    def test_route_credit_skip(self):
        router = SemanticRouter()
        block = self._make_block(BlockType.CREDIT, "https://artist.com")
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.SKIP
        assert decision.skip_flag is True
        assert decision.nsfw_flag is False
    
    def test_route_ui_meta_skip(self):
        router = SemanticRouter()
        block = self._make_block(BlockType.UI_META, "Page 1")
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.SKIP
        assert decision.skip_flag is True
        assert decision.nsfw_flag is False
    
    def test_route_sfx(self):
        router = SemanticRouter()
        block = self._make_block(BlockType.SFX, "ドン")
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.LOCAL_SFX
        assert decision.skip_flag is False
        assert decision.nsfw_flag is False
    
    def test_route_sfx_detected_from_text(self):
        router = SemanticRouter()
        # Dialogue block but with SFX-like content
        block = self._make_block(BlockType.DIALOGUE, "BOOM", bbox=[0, 0, 200, 200])
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.LOCAL_SFX
    
    def test_route_nsfw_flagged(self):
        router = SemanticRouter()
        block = self._make_block(BlockType.DIALOGUE, "Some text", nsfw_flag=True)
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.LOCAL_NSFW
        assert decision.nsfw_flag is True
        assert decision.skip_flag is False
    
    def test_route_nsfw_detected_in_text(self):
        router = SemanticRouter()
        block = self._make_block(BlockType.DIALOGUE, "This is NSFW content")
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.LOCAL_NSFW
        assert decision.nsfw_flag is True
    
    def test_route_nsfw_with_ehtag(self):
        router = SemanticRouter(ehtag_dict={"sex": "nsfw"})
        block = self._make_block(BlockType.DIALOGUE, "Contains sex content")
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.LOCAL_NSFW
        assert decision.nsfw_flag is True
    
    def test_route_dialogue_default(self):
        router = SemanticRouter()
        # Use smaller bbox to avoid SFX detection; Japanese routes via language-aware defaults
        block = self._make_block(BlockType.DIALOGUE, "こんにちは", bbox=[0, 0, 50, 50])
        decision = router.route(block)

        assert decision.translator_type == TranslatorType.CLAUDE
        assert decision.skip_flag is False
        assert decision.nsfw_flag is False
    
    def test_route_narration_default(self):
        router = SemanticRouter()
        block = self._make_block(BlockType.NARRATION, "Once upon a time")
        decision = router.route(block)
        
        assert decision.translator_type == TranslatorType.DEEPL
        assert decision.skip_flag is False
        assert decision.nsfw_flag is False
    
    def test_route_batch(self):
        router = SemanticRouter()
        # Use smaller bbox for dialogue to avoid SFX detection
        block1 = self._make_block(BlockType.DIALOGUE, "Hello", bbox=[0, 0, 50, 50])
        block2 = self._make_block(BlockType.SFX, "ドン")
        block3 = self._make_block(BlockType.CREDIT, "artist.com")
        blocks = [block1, block2, block3]
        decisions = router.route_batch(blocks)
        
        assert len(decisions) == 3
        assert decisions[block1.block_uid].translator_type == TranslatorType.DEEPL
        assert decisions[block2.block_uid].translator_type == TranslatorType.LOCAL_SFX
        assert decisions[block3.block_uid].translator_type == TranslatorType.SKIP


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""
    
    def test_creation(self):
        decision = RoutingDecision(
            translator_type=TranslatorType.DEEPL,
            skip_flag=False,
            nsfw_flag=False,
            reason="Test reason",
        )
        assert decision.translator_type == TranslatorType.DEEPL
        assert decision.skip_flag is False
        assert decision.nsfw_flag is False
        assert decision.reason == "Test reason"
    
    def test_defaults(self):
        decision = RoutingDecision(translator_type=TranslatorType.SKIP)
        assert decision.skip_flag is False
        assert decision.nsfw_flag is False
        assert decision.reason is None


class TestTranslatorType:
    """Tests for TranslatorType enum."""
    
    def test_values(self):
        assert TranslatorType.LOCAL_NSFW.value == "local_nsfw"
        assert TranslatorType.LOCAL_SFX.value == "local_sfx"
        assert TranslatorType.DEEPL.value == "deepl"
        assert TranslatorType.GPT.value == "gpt"
        assert TranslatorType.CLAUDE.value == "claude"
        assert TranslatorType.SKIP.value == "skip"
