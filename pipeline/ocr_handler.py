import logging
from modules.ocr.processor import OCRProcessor
from pipeline.webtoon_utils import filter_and_convert_visible_blocks, restore_original_block_coordinates

logger = logging.getLogger(__name__)


class OCRHandler:
    """Handles OCR processing with caching support."""
    
    def __init__(self, main_page, cache_manager, pipeline):
        self.main_page = main_page
        self.cache_manager = cache_manager
        self.pipeline = pipeline
        self.ocr = OCRProcessor()

    def OCR_image(self, single_block: bool = False):
        source_lang = self.main_page.s_combo.currentText()
        if self.main_page.image_viewer.hasPhoto() and self.main_page.image_viewer.rectangles:
            image = self.main_page.image_viewer.get_cv2_image()
            ocr_model = self.main_page.settings_page.get_tool_selection('ocr')
            cache_key = self.cache_manager._get_ocr_cache_key(image, source_lang, ocr_model)
            
            if single_block:
                blk = self.pipeline.get_selected_block()
                if blk is None:
                    return
                
                # Check if block already has text to avoid redundant processing
                if hasattr(blk, 'text') and blk.text and blk.text.strip():
                    return
                
                # Check if we have cached results for this image/model/language
                if self.cache_manager._is_ocr_cached(cache_key):
                    # Check if block exists in cache (even if text is empty)
                    cached_text = self.cache_manager._get_cached_text_for_block(cache_key, blk)
                    if cached_text is not None:  # Block was processed before (even if text is empty)
                        blk.text = cached_text
                        logger.info(f"Using cached OCR result for block: '{cached_text}'")
                        return
                    else:
                        logger.info("Block not found in cache, processing single block...")
                        # Process just this single block
                        self.ocr.initialize(self.main_page, source_lang)
                        single_block_list = [blk]
                        self.ocr.process(image, single_block_list)
                        
                        # Update the cache with this new result using the cache manager's method
                        self.cache_manager.update_ocr_cache_for_block(cache_key, blk)
                        
                        logger.info(f"Processed single block and updated cache: '{blk.text}'")
                else:
                    # Run OCR on all blocks and cache the results
                    logger.info("No cached OCR results found, running OCR on entire page...")
                    self.ocr.initialize(self.main_page, source_lang)
                    # Create a mapping between original blocks and their copies
                    original_to_copy = {}
                    all_blocks_copy = []
                    
                    for original_blk in self.main_page.blk_list:
                        copy_blk = original_blk.deep_copy()
                        all_blocks_copy.append(copy_blk)
                        # Use the original block's ID as the key for mapping
                        original_id = self.cache_manager._get_block_id(original_blk)
                        original_to_copy[original_id] = copy_blk
                    
                    if all_blocks_copy:  
                        self.ocr.process(image, all_blocks_copy)
                        # Cache using the original blocks to maintain consistent IDs
                        self.cache_manager._cache_ocr_results(cache_key, self.main_page.blk_list, all_blocks_copy)
                        cached_text = self.cache_manager._get_cached_text_for_block(cache_key, blk)
                        blk.text = cached_text
                        logger.info(f"Cached OCR results and extracted text for block: {cached_text}")
            else:
                # For full page OCR, check if we can use cached results
                if self.cache_manager._can_serve_all_blocks_from_ocr_cache(cache_key, self.main_page.blk_list):
                    # All blocks can be served from cache
                    self.cache_manager._apply_cached_ocr_to_blocks(cache_key, self.main_page.blk_list)
                    logger.info(f"Using cached OCR results for all {len(self.main_page.blk_list)} blocks")
                else:
                    # Need to run OCR and cache results
                    self.ocr.initialize(self.main_page, source_lang)
                    if self.main_page.blk_list:  
                        self.ocr.process(image, self.main_page.blk_list)
                        self.cache_manager._cache_ocr_results(cache_key, self.main_page.blk_list)
                        logger.info("OCR completed and cached for %d blocks", len(self.main_page.blk_list))

    def OCR_webtoon_visible_area(self, single_block: bool = False):
        """Perform OCR on the visible area in webtoon mode."""
        source_lang = self.main_page.s_combo.currentText()
        
        if not (self.main_page.image_viewer.hasPhoto() and 
                self.main_page.webtoon_mode):
            logger.warning("OCR_webtoon_visible_area called but not in webtoon mode")
            return
        
        # Get the visible area image and mapping data
        visible_image, mappings = self.main_page.image_viewer.get_visible_area_image()
        if visible_image is None or not mappings:
            logger.warning("No visible area found for OCR")
            return
        
        # Filter blocks to only those in the visible area and convert coordinates
        visible_blocks = filter_and_convert_visible_blocks(
            self.main_page, self.pipeline, mappings, single_block
        )
        if not visible_blocks:
            logger.info("No blocks found in visible area")
            return
        
        # Perform OCR on the visible image with filtered blocks
        self.ocr.initialize(self.main_page, source_lang)
        self.ocr.process(visible_image, visible_blocks)
        
        # The OCR text is already set on the blocks, just restore coordinates
        restore_original_block_coordinates(visible_blocks)
        
        logger.info(f"OCR completed for {len(visible_blocks)} blocks in visible area")
