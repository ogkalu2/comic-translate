"""
PipelineOrchestrator for full comic translation pipeline coordination.

Coordinates the complete pipeline: detect → OCR → route → translate → inpaint → render
"""

import time
from typing import Dict, List, Optional

from ..interfaces import (
    IPanelDetector,
    IBubbleDetector,
    IOCREngine,
    ITranslator,
    ISemanticRouter,
    IInpainter,
    IRenderer,
)
from ..models.block_v2 import (
    Block,
    BlockType as BlockTypeV2,
    OriginalText,
    SemanticRouting,
    TranslationVersion,
)
from ..models.routing import RoutingDecision, TranslatorType
from ..models.script import ScriptExport
from ..models.block import ScriptBlock, BlockContext, BlockType


class PipelineOrchestrator:
    """
    Coordinates the full comic translation pipeline.
    
    Pipeline stages:
    1. Detect panels and bubbles in comic pages
    2. OCR text from detected regions
    3. Route blocks to appropriate translators
    4. Translate text based on routing decisions
    5. Inpaint (remove) original text
    6. Render translated text onto images
    
    Uses dependency injection for all components.
    """

    def __init__(
        self,
        panel_detector: IPanelDetector,
        bubble_detector: IBubbleDetector,
        ocr_engine: IOCREngine,
        translator: ITranslator,
        router: ISemanticRouter,
        inpainter: IInpainter,
        renderer: IRenderer,
    ):
        """
        Initialize the PipelineOrchestrator with all required components.

        Args:
            panel_detector: Panel detection component
            bubble_detector: Bubble detection component
            ocr_engine: OCR engine for text extraction
            translator: Translation service
            router: Semantic router for translation decisions
            inpainter: Inpainting component for text removal
            renderer: Rendering component for text placement
        """
        self.panel_detector = panel_detector
        self.bubble_detector = bubble_detector
        self.ocr_engine = ocr_engine
        self.translator = translator
        self.router = router
        self.inpainter = inpainter
        self.renderer = renderer

    def process_comic(
        self,
        images: List[str],
        comic_id: str,
        source_lang: str,
        target_lang: str,
        base_fp: str = "",
        variant: str = "default",
    ) -> ScriptExport:
        """
        Process a complete comic through the translation pipeline.

        Args:
            images: List of image paths for comic pages
            comic_id: Unique identifier for the comic
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            base_fp: Base fingerprint for versioning
            variant: Variant identifier

        Returns:
            ScriptExport containing all processed blocks and translations
        """
        all_blocks: List[ScriptBlock] = []
        page_range = list(range(1, len(images) + 1))

        for page_num, image_path in zip(page_range, images):
            page_blocks = self.process_page(image_path, page_num)
            
            # Convert Block objects to ScriptBlock for export
            for block in page_blocks:
                script_block = self._block_to_script_block(
                    block, page_num, source_lang, target_lang
                )
                all_blocks.append(script_block)

        script_export = ScriptExport(
            version="2.0",
            comic_id=comic_id,
            base_fp=base_fp,
            script_id=f"{comic_id}_{variant}_{int(time.time())}",
            source_lang=source_lang,
            target_lang=target_lang,
            exported_at=time.time(),
            page_range=page_range,
            active_variant=variant,
            variants={variant: {"created_at": time.time()}},
            glossary_snapshot={},
            blocks=all_blocks,
        )

        return script_export

    def process_page(self, image_path: str, page_number: int) -> List[Block]:
        """
        Process a single comic page through the pipeline.

        Args:
            image_path: Path to the comic page image
            page_number: Page number (1-indexed)

        Returns:
            List of processed Block objects
        """
        # Stage 1: Detect panels and bubbles
        panels = self.panel_detector.detect(image_path)
        bubbles = self.bubble_detector.detect(image_path)

        blocks: List[Block] = []

        # Stage 2-6: Process each bubble
        for idx, (bbox, bubble_type) in enumerate(bubbles):
            block = self._process_bubble(
                image_path, bbox, bubble_type, idx, page_number
            )
            blocks.append(block)

        return blocks

    def _process_bubble(
        self,
        image_path: str,
        bbox: List[int],
        bubble_type: str,
        index: int,
        page_number: int,
    ) -> Block:
        """
        Process a single bubble through OCR, routing, and translation.

        Args:
            image_path: Path to the comic page image
            bbox: Bounding box [x1, y1, x2, y2]
            bubble_type: Type of bubble ("speech", "thought", "narration", "sfx")
            index: Bubble index on the page
            page_number: Page number

        Returns:
            Processed Block with translations
        """
        # Stage 2: OCR
        text, confidence = self.ocr_engine.recognize_with_confidence(image_path, bbox)

        # Determine block type from bubble type
        block_type = self._bubble_type_to_block_type(bubble_type)

        # Create block UID
        block_uid = f"p{page_number}_b{index}"

        # Create original text
        original_text = OriginalText(
            variant_id="default",
            lang="auto",  # Will be detected or specified
            text=text,
        )

        # Create initial block
        block = Block(
            block_uid=block_uid,
            nsfw_flag=False,
            type=block_type,
            bbox=bbox,
            original_texts=[original_text],
            translations={},
            semantic_routing=None,
            embedding=None,
        )

        # Stage 3: Route
        routing_decision = self.router.route(block)
        block.semantic_routing = SemanticRouting(
            ner_entities=[],
            sfx_detected=(routing_decision.translator_type == TranslatorType.LOCAL_SFX),
            route=routing_decision.translator_type.value,
        )

        # Stage 4: Translate (if not skipped)
        if not routing_decision.skip_flag and text:
            translated_text = self._translate_block(text, routing_decision)
            
            # Add translation to block
            translation_version = TranslationVersion(
                text=translated_text,
                status="pending_review",
                weight=1.0,
                source=routing_decision.translator_type.value,
            )
            
            if "default" not in block.translations:
                block.translations["default"] = {}
            block.translations["default"]["default"] = translation_version

        return block

    def _translate_block(self, text: str, routing_decision: RoutingDecision) -> str:
        """
        Translate text based on routing decision.

        Args:
            text: Text to translate
            routing_decision: Routing decision with translator type

        Returns:
            Translated text
        """
        # For now, use the translator directly
        # In a full implementation, this would dispatch to different translators
        # based on routing_decision.translator_type
        try:
            return self.translator.translate(
                text,
                source_lang="auto",
                target_lang="en",  # Default target, should be configurable
            )
        except Exception:
            # Fallback to original text if translation fails
            return text

    def _bubble_type_to_block_type(self, bubble_type: str) -> BlockTypeV2:
        """
        Convert bubble type string to BlockType enum.

        Args:
            bubble_type: Bubble type string

        Returns:
            Corresponding BlockType
        """
        mapping = {
            "speech": BlockTypeV2.DIALOGUE,
            "thought": BlockTypeV2.DIALOGUE,
            "narration": BlockTypeV2.NARRATION,
            "sfx": BlockTypeV2.SFX,
        }
        return mapping.get(bubble_type.lower(), BlockTypeV2.DIALOGUE)

    def _block_to_script_block(
        self,
        block: Block,
        page_number: int,
        source_lang: str,
        target_lang: str,
    ) -> ScriptBlock:
        """
        Convert a Block to a ScriptBlock for export.

        Args:
            block: Block object
            page_number: Page number
            source_lang: Source language
            target_lang: Target language

        Returns:
            ScriptBlock for export
        """
        # Get original text
        original = ""
        if block.original_texts:
            original = block.original_texts[0].text

        # Get translated text
        translated = ""
        if block.translations and "default" in block.translations:
            default_translations = block.translations["default"]
            if "default" in default_translations:
                translated = default_translations["default"].text

        # Map BlockTypeV2 to BlockType for ScriptBlock
        block_type_mapping = {
            BlockTypeV2.DIALOGUE: BlockType.DIALOGUE,
            BlockTypeV2.NARRATION: BlockType.NARRATION,
            BlockTypeV2.SFX: BlockType.SFX,
            BlockTypeV2.CREDIT: BlockType.CREDIT,
        }

        return ScriptBlock(
            block_id=block.block_uid,
            page=page_number,
            type=block_type_mapping.get(block.type, BlockType.DIALOGUE),
            bbox=block.bbox,
            original=original,
            translated=translated,
            original_variant="default",
            context=BlockContext(),
            qa_metadata={
                "nsfw_flag": block.nsfw_flag,
                "semantic_route": block.semantic_routing.route if block.semantic_routing else "",
            },
        )

    def inpaint_and_render(
        self,
        image_path: str,
        blocks: List[Block],
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Inpaint original text and render translations on an image.

        Args:
            image_path: Path to the comic page image
            blocks: List of processed blocks with translations
            output_path: Optional path to save the result

        Returns:
            Processed image as bytes
        """
        import numpy as np
        from PIL import Image

        # Load image
        img = np.array(Image.open(image_path))

        # Collect bboxes and texts for rendering
        bboxes = []
        texts = []

        for block in blocks:
            if block.semantic_routing and block.semantic_routing.route == "skip":
                continue

            if block.translations and "default" in block.translations:
                default_trans = block.translations["default"]
                if "default" in default_trans:
                    bboxes.append(block.bbox)
                    texts.append(default_trans["default"].text)

        # Inpaint original text regions
        if bboxes:
            img = self.inpainter.inpaint_batch(image_path, bboxes)

        # Render translated text
        if texts and bboxes:
            img = self.renderer.render_batch(img, texts, bboxes)

        # Save if output path provided
        if output_path:
            Image.fromarray(img).save(output_path)

        # Convert to bytes
        from io import BytesIO
        buffer = BytesIO()
        Image.fromarray(img).save(buffer, format="PNG")
        return buffer.getvalue()
