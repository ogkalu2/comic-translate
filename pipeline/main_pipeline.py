import logging

from pipeline.cache_manager import CacheManager
from pipeline.block_detection import BlockDetectionHandler
from pipeline.inpainting import InpaintingHandler
from pipeline.ocr_handler import OCRHandler
from pipeline.translation_handler import TranslationHandler
from pipeline.segmentation_handler import SegmentationHandler
from pipeline.batch_processor import BatchProcessor
from pipeline.webtoon_batch_processor import WebtoonBatchProcessor

logger = logging.getLogger(__name__)


class ComicTranslatePipeline:
    """Main pipeline orchestrator for comic translation."""
    
    def __init__(self, main_page):
        self.main_page = main_page
        
        # Initialize all components
        self.cache_manager = CacheManager()
        self.block_detection = BlockDetectionHandler(main_page)
        self.inpainting = InpaintingHandler(main_page)
        self.ocr_handler = OCRHandler(main_page, self.cache_manager, self)
        self.translation_handler = TranslationHandler(main_page, self.cache_manager, self)
        self.segmentation_handler = SegmentationHandler(main_page, self)
        
        # Pass shared handlers to the BatchProcessor to ensure state/cache is shared
        self.batch_processor = BatchProcessor(
            main_page, 
            self.cache_manager, 
            self.block_detection, 
            self.inpainting, 
            self.ocr_handler
        )
        
        # Pass shared handlers to the WebtoonBatchProcessor
        self.webtoon_batch_processor = WebtoonBatchProcessor(
            main_page,
            self.cache_manager,
            self.block_detection,
            self.inpainting,
            self.ocr_handler
        )

    # Block detection methods (delegate to block_detection)
    def load_box_coords(self, blk_list):
        """Load bounding box coordinates."""
        self.block_detection.load_box_coords(blk_list)

    def detect_blocks(self, load_rects=True):
        """Detect text blocks in the image."""
        return self.block_detection.detect_blocks(load_rects)

    def on_blk_detect_complete(self, result):
        """Handle completion of block detection."""
        self.block_detection.on_blk_detect_complete(result)

    # Inpainting methods (delegate to inpainting)
    def manual_inpaint(self):
        """Perform manual inpainting."""
        return self.inpainting.manual_inpaint()

    def inpaint_complete(self, patch_list):
        """Handle completion of inpainting."""
        self.inpainting.inpaint_complete(patch_list)

    def get_inpainted_patches(self, mask, inpainted_image):
        """Get inpainted patches from mask and image."""
        return self.inpainting.get_inpainted_patches(mask, inpainted_image)

    def inpaint(self):
        """Perform inpainting and return patches."""
        return self.inpainting.inpaint()

    def get_selected_block(self):
        """Get the currently selected text block."""
        rect = self.main_page.image_viewer.selected_rect
        if not rect:
            return None
        srect = rect.mapRectToScene(rect.rect())
        srect_coords = srect.getCoords()
        blk = self.main_page.rect_item_ctrl.find_corresponding_text_block(srect_coords)
        return blk

    # OCR methods (delegate to ocr_handler)
    def OCR_image(self, single_block=False):
        """Perform OCR on image or single block."""
        self.ocr_handler.OCR_image(single_block)

    def OCR_webtoon_visible_area(self, single_block=False):
        """Perform OCR on visible area in webtoon mode."""
        self.ocr_handler.OCR_webtoon_visible_area(single_block)

    # Translation methods (delegate to translation_handler)
    def translate_image(self, single_block=False):
        """Translate image or single block."""
        self.translation_handler.translate_image(single_block)

    def translate_webtoon_visible_area(self, single_block=False):
        """Translate visible area in webtoon mode."""
        self.translation_handler.translate_webtoon_visible_area(single_block)
    
    # Batch processing methods
    def batch_process(self, selected_paths=None):
        """Regular batch processing."""
        return self.batch_processor.batch_process(selected_paths)
    
    def webtoon_batch_process(self, selected_paths=None):
        """Webtoon batch processing with overlapping sliding windows."""
        return self.webtoon_batch_processor.webtoon_batch_process(selected_paths)

    # Segmentation methods (delegate to segmentation_handler)
    def segment_webtoon_visible_area(self):
        """Perform segmentation on visible area in webtoon mode."""
        return self.segmentation_handler.segment_webtoon_visible_area()
