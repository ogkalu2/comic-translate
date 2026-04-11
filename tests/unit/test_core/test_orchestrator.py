"""
Unit tests for the PipelineOrchestrator.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch

from comic_translate_core.pipeline.orchestrator import PipelineOrchestrator
from comic_translate_core.stubs import (
    StubPanelDetector,
    StubBubbleDetector,
    StubOCREngine,
    StubTranslator,
    StubInpainter,
    StubRenderer,
)
from comic_translate_core.models.block_v2 import Block, BlockType, OriginalText
from comic_translate_core.models.routing import RoutingDecision, TranslatorType
from comic_translate_core.routing import SemanticRouter


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator class."""

    def _create_orchestrator(self, **kwargs):
        """Helper to create an orchestrator with stub components."""
        defaults = {
            "panel_detector": StubPanelDetector(),
            "bubble_detector": StubBubbleDetector(),
            "ocr_engine": StubOCREngine(),
            "translator": StubTranslator(),
            "router": SemanticRouter(),
            "inpainter": StubInpainter(),
            "renderer": StubRenderer(),
        }
        defaults.update(kwargs)
        return PipelineOrchestrator(**defaults)

    def test_init(self):
        """Test orchestrator initialization with dependency injection."""
        panel_detector = StubPanelDetector()
        bubble_detector = StubBubbleDetector()
        ocr_engine = StubOCREngine()
        translator = StubTranslator()
        router = SemanticRouter()
        inpainter = StubInpainter()
        renderer = StubRenderer()

        orchestrator = PipelineOrchestrator(
            panel_detector=panel_detector,
            bubble_detector=bubble_detector,
            ocr_engine=ocr_engine,
            translator=translator,
            router=router,
            inpainter=inpainter,
            renderer=renderer,
        )

        assert orchestrator.panel_detector is panel_detector
        assert orchestrator.bubble_detector is bubble_detector
        assert orchestrator.ocr_engine is ocr_engine
        assert orchestrator.translator is translator
        assert orchestrator.router is router
        assert orchestrator.inpainter is inpainter
        assert orchestrator.renderer is renderer

    def test_process_page(self):
        """Test processing a single page."""
        orchestrator = self._create_orchestrator()

        # Create a temporary test image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Create a simple test image
            from PIL import Image
            import numpy as np
            img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
            img.save(f.name)
            temp_path = f.name

        try:
            blocks = orchestrator.process_page(temp_path, page_number=1)

            # Should return blocks based on stub bubble detector
            assert isinstance(blocks, list)
            assert len(blocks) > 0

            # Check block structure
            for block in blocks:
                assert isinstance(block, Block)
                assert block.block_uid.startswith("p1_b")
                assert block.type in [
                    BlockType.DIALOGUE,
                    BlockType.NARRATION,
                    BlockType.SFX,
                ]
                assert len(block.original_texts) > 0
        finally:
            os.unlink(temp_path)

    def test_process_comic(self):
        """Test processing a complete comic."""
        orchestrator = self._create_orchestrator()

        # Create temporary test images
        temp_paths = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                from PIL import Image
                import numpy as np
                img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
                img.save(f.name)
                temp_paths.append(f.name)

        try:
            script_export = orchestrator.process_comic(
                images=temp_paths,
                comic_id="test_comic",
                source_lang="ja",
                target_lang="en",
            )

            # Check script export structure
            assert script_export.version == "2.0"
            assert script_export.comic_id == "test_comic"
            assert script_export.source_lang == "ja"
            assert script_export.target_lang == "en"
            assert script_export.page_range == [1, 2]
            assert len(script_export.blocks) > 0

            # Check blocks
            for block in script_export.blocks:
                assert block.page in [1, 2]
                assert block.block_id.startswith("p")
        finally:
            for path in temp_paths:
                os.unlink(path)

    def test_bubble_type_to_block_type(self):
        """Test bubble type conversion."""
        orchestrator = self._create_orchestrator()

        assert orchestrator._bubble_type_to_block_type("speech") == BlockType.DIALOGUE
        assert orchestrator._bubble_type_to_block_type("thought") == BlockType.DIALOGUE
        assert orchestrator._bubble_type_to_block_type("narration") == BlockType.NARRATION
        assert orchestrator._bubble_type_to_block_type("sfx") == BlockType.SFX
        assert orchestrator._bubble_type_to_block_type("unknown") == BlockType.DIALOGUE

    def test_block_to_script_block(self):
        """Test Block to ScriptBlock conversion."""
        orchestrator = self._create_orchestrator()

        block = Block(
            block_uid="test_uid",
            nsfw_flag=False,
            type=BlockType.DIALOGUE,
            bbox=[10, 20, 100, 200],
            original_texts=[OriginalText(variant_id="default", lang="ja", text="こんにちは")],
            translations={
                "default": {
                    "default": MagicMock(text="Hello", status="pending_review")
                }
            },
            semantic_routing=None,
            embedding=None,
        )

        script_block = orchestrator._block_to_script_block(
            block, page_number=1, source_lang="ja", target_lang="en"
        )

        assert script_block.block_id == "test_uid"
        assert script_block.page == 1
        assert script_block.type == BlockType.DIALOGUE
        assert script_block.bbox == [10, 20, 100, 200]
        assert script_block.original == "こんにちは"
        assert script_block.translated == "Hello"

    def test_translate_block(self):
        """Test block translation."""
        translator = StubTranslator(translation_map={"こんにちは": "Hello"})
        orchestrator = self._create_orchestrator(translator=translator)

        routing_decision = RoutingDecision(
            translator_type=TranslatorType.DEEPL,
            skip_flag=False,
            nsfw_flag=False,
        )

        translated = orchestrator._translate_block("こんにちは", routing_decision)
        assert translated == "Hello"

    def test_translate_block_fallback(self):
        """Test block translation fallback on error."""
        # Create a translator that raises an exception
        translator = MagicMock()
        translator.translate.side_effect = Exception("Translation failed")
        
        orchestrator = self._create_orchestrator(translator=translator)

        routing_decision = RoutingDecision(
            translator_type=TranslatorType.DEEPL,
            skip_flag=False,
            nsfw_flag=False,
        )

        # Should fallback to original text
        translated = orchestrator._translate_block("こんにちは", routing_decision)
        assert translated == "こんにちは"

    def test_process_bubble_skip(self):
        """Test processing a bubble that should be skipped."""
        # Create a router that always skips
        router = MagicMock()
        router.route.return_value = RoutingDecision(
            translator_type=TranslatorType.SKIP,
            skip_flag=True,
            nsfw_flag=False,
        )

        orchestrator = self._create_orchestrator(router=router)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            from PIL import Image
            import numpy as np
            img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
            img.save(f.name)
            temp_path = f.name

        try:
            block = orchestrator._process_bubble(
                temp_path, [10, 20, 100, 200], "speech", 0, 1
            )

            # Should not have translations since it was skipped
            assert block.translations == {}
        finally:
            os.unlink(temp_path)

    def test_process_bubble_nsfw(self):
        """Test processing an NSFW bubble."""
        # Create a router that routes to NSFW
        router = MagicMock()
        router.route.return_value = RoutingDecision(
            translator_type=TranslatorType.LOCAL_NSFW,
            skip_flag=False,
            nsfw_flag=True,
        )

        orchestrator = self._create_orchestrator(router=router)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            from PIL import Image
            import numpy as np
            img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
            img.save(f.name)
            temp_path = f.name

        try:
            block = orchestrator._process_bubble(
                temp_path, [10, 20, 100, 200], "speech", 0, 1
            )

            # Should have translations
            assert "default" in block.translations
            # Check that the route indicates NSFW
            assert block.semantic_routing.route == "local_nsfw"
        finally:
            os.unlink(temp_path)


class TestStubComponents:
    """Tests for stub components."""

    def test_stub_panel_detector(self):
        """Test StubPanelDetector."""
        detector = StubPanelDetector(panels=[[0, 0, 100, 100], [100, 0, 200, 100]])
        
        panels = detector.detect("test.png")
        assert len(panels) == 2
        assert panels[0] == [0, 0, 100, 100]
        assert panels[1] == [100, 0, 200, 100]

        # Test from image
        panels = detector.detect_from_image(b"test_data")
        assert len(panels) == 2

    def test_stub_bubble_detector(self):
        """Test StubBubbleDetector."""
        bubbles = [([10, 10, 50, 50], "speech"), ([60, 60, 100, 100], "sfx")]
        detector = StubBubbleDetector(bubbles=bubbles)
        
        detected = detector.detect("test.png")
        assert len(detected) == 2
        assert detected[0] == ([10, 10, 50, 50], "speech")
        assert detected[1] == ([60, 60, 100, 100], "sfx")

        # Test classify
        assert detector.classify_bubble([10, 10, 50, 50], "test.png") == "speech"
        assert detector.classify_bubble([60, 60, 100, 100], "test.png") == "sfx"
        assert detector.classify_bubble([0, 0, 10, 10], "test.png") == "speech"

    def test_stub_ocr_engine(self):
        """Test StubOCREngine."""
        text_map = {
            (10, 20, 100, 200): ("こんにちは", 0.98),
        }
        engine = StubOCREngine(text_map=text_map, default_text="Default", default_confidence=0.9)

        # Test mapped region
        text, confidence = engine.recognize_with_confidence("test.png", [10, 20, 100, 200])
        assert text == "こんにちは"
        assert confidence == 0.98

        # Test unmapped region
        text, confidence = engine.recognize_with_confidence("test.png", [0, 0, 10, 10])
        assert text == "Default"
        assert confidence == 0.9

        # Test recognize
        assert engine.recognize("test.png", [10, 20, 100, 200]) == "こんにちは"

        # Test batch
        results = engine.recognize_batch("test.png", [[10, 20, 100, 200], [0, 0, 10, 10]])
        assert len(results) == 2
        assert results[0] == ("こんにちは", 0.98)
        assert results[1] == ("Default", 0.9)

        # Test language
        assert "en" in engine.get_supported_languages()
        engine.set_language("ja")
        with pytest.raises(ValueError):
            engine.set_language("invalid")

    def test_stub_translator(self):
        """Test StubTranslator."""
        translation_map = {"こんにちは": "Hello", "さようなら": "Goodbye"}
        translator = StubTranslator(translation_map=translation_map, default_translation="Translated")

        # Test mapped translation
        assert translator.translate("こんにちは", "ja", "en") == "Hello"
        assert translator.translate("さようなら", "ja", "en") == "Goodbye"

        # Test unmapped translation
        assert translator.translate("Unknown", "ja", "en") == "Translated"

        # Test batch
        results = translator.translate_batch(["こんにちは", "Unknown"], "ja", "en")
        assert results == ["Hello", "Translated"]

        # Test glossary
        glossary = {"Hello": "Hi"}
        result = translator.translate_with_glossary("こんにちは", "ja", "en", glossary)
        assert result == "Hi"

        # Test supported pairs
        pairs = translator.get_supported_pairs()
        assert ("ja", "en") in pairs

        # Test name
        assert translator.get_translator_name() == "stub"

    def test_stub_inpainter(self):
        """Test StubInpainter."""
        inpainter = StubInpainter(fill_color=(255, 255, 255))

        # Create a test image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            from PIL import Image
            import numpy as np
            img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
            img.save(f.name)
            temp_path = f.name

        try:
            # Test inpaint
            result = inpainter.inpaint(temp_path, [10, 10, 50, 50])
            assert result.shape == (100, 100, 3)
            # Check that the region was filled with white
            assert (result[10:50, 10:50] == (255, 255, 255)).all()

            # Test batch
            result = inpainter.inpaint_batch(temp_path, [[10, 10, 50, 50], [60, 60, 90, 90]])
            assert result.shape == (100, 100, 3)

            # Test mask creation
            mask = inpainter.create_mask(temp_path, [10, 10, 50, 50], [20, 20, 40, 40])
            assert mask.shape == (100, 100)
            assert mask[20:40, 20:40].max() == 255

            # Test model name
            assert inpainter.get_model_name() == "stub"
        finally:
            os.unlink(temp_path)

    def test_stub_renderer(self):
        """Test StubRenderer."""
        renderer = StubRenderer(default_font_size=24, default_font_color=(0, 0, 0))

        # Create a test image
        import numpy as np
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        # Test render
        result = renderer.render(img, "Hello", [10, 10, 50, 50])
        assert result.shape == (100, 100, 3)
        # Check that borders were drawn
        assert (result[10:12, 10:50] == (0, 0, 0)).all()  # Top border

        # Test batch render
        result = renderer.render_batch(img, ["Hello", "World"], [[10, 10, 50, 50], [60, 60, 90, 90]])
        assert result.shape == (100, 100, 3)

        # Test font size calculation
        font_size = renderer.calculate_font_size("Hello", [10, 10, 50, 50])
        assert 12 <= font_size <= 48

        # Test available fonts
        fonts = renderer.get_available_fonts()
        assert "default" in fonts

        # Test set font
        renderer.set_font("stub_font")
        with pytest.raises(ValueError):
            renderer.set_font("invalid_font")
