from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from modules.translation.processor import Translator
from modules.utils.translator_utils import set_upper_case
from pipeline.webtoon_utils import filter_and_convert_visible_blocks, restore_original_block_coordinates
from .cache_manager import CacheManager

if TYPE_CHECKING:
    from controller import ComicTranslate
    from .main_pipeline import ComicTranslatePipeline

logger = logging.getLogger(__name__)


class TranslationHandler:
    """Handles translation processing with caching support."""
    
    def __init__(
            self, 
            main_page: ComicTranslate, 
            cache_manager: CacheManager, 
            pipeline: ComicTranslatePipeline,
        ):
        
        self.main_page = main_page
        self.cache_manager = cache_manager
        self.pipeline = pipeline

    def translate_image(self, single_block=False):
        source_lang = self.main_page.s_combo.currentText()
        target_lang = self.main_page.t_combo.currentText()
        if self.main_page.image_viewer.hasPhoto() and self.main_page.blk_list:
            settings_page = self.main_page.settings_page
            image = self.main_page.image_viewer.get_image_array()
            extra_context = settings_page.get_llm_settings()['extra_context']
            translator_key = settings_page.get_tool_selection('translator')

            upper_case = settings_page.ui.uppercase_checkbox.isChecked()

            translator = Translator(self.main_page, source_lang, target_lang)
            
            # Get translation cache key
            translation_cache_key = self.cache_manager._get_translation_cache_key(
                image, source_lang, target_lang, translator_key, extra_context
            )
            
            if single_block:
                blk = self.pipeline.get_selected_block()
                if blk is None:
                    return
                
                # Check if block already has translation to avoid redundant processing
                if hasattr(blk, 'translation') and blk.translation and blk.translation.strip():
                    return
                
                # Check if we have cached translation results for this image/translator/language combination
                if self.cache_manager._is_translation_cached(translation_cache_key):
                    # Check if block exists in cache and source text matches
                    cached_translation = self.cache_manager._get_cached_translation_for_block(translation_cache_key, blk)
                    if cached_translation is not None:  # Block was processed and source text matches
                        blk.translation = cached_translation
                        logger.info(f"Using cached translation result for block: '{cached_translation}'")
                        set_upper_case([blk], upper_case)
                        return
                    else:
                        logger.info("Block not found in cache or source text changed, processing single block...")
                    
                    # If we reach here, need to process the block
                    single_block_list = [blk]
                    translator.translate(single_block_list, image, extra_context)
                    
                    # Update the cache with this new result using the cache manager's method
                    self.cache_manager.update_translation_cache_for_block(translation_cache_key, blk)
                    
                    logger.info(f"Processed single block and updated cache: '{blk.translation}'")
                    set_upper_case([blk], upper_case)
                else:
                    # Run translation on all blocks and cache the results
                    logger.info("No cached translation results found, running translation on entire page...")
                    # Create a mapping between original blocks and their copies
                    all_blocks_copy = []
                    
                    for original_blk in self.main_page.blk_list:
                        copy_blk = original_blk.deep_copy()
                        all_blocks_copy.append(copy_blk)
                    
                    if all_blocks_copy:  
                        translator.translate(all_blocks_copy, image, extra_context)
                        # Cache using the original blocks to maintain consistent IDs
                        self.cache_manager._cache_translation_results(translation_cache_key, self.main_page.blk_list, all_blocks_copy)
                        cached_translation = self.cache_manager._get_cached_translation_for_block(translation_cache_key, blk)
                        blk.translation = cached_translation
                        logger.info(f"Cached translation results and extracted translation for block: {cached_translation}")
                    
                    set_upper_case([blk], upper_case)
            else:
                # For full page translation, check if we can use cached results
                if self.cache_manager._can_serve_all_blocks_from_translation_cache(translation_cache_key, self.main_page.blk_list):
                    # All blocks can be served from cache with matching source text
                    self.cache_manager._apply_cached_translations_to_blocks(translation_cache_key, self.main_page.blk_list)
                    logger.info(f"Using cached translation results for all {len(self.main_page.blk_list)} blocks")
                else:
                    # Need to run translation and cache results
                    translator.translate(self.main_page.blk_list, image, extra_context)
                    self.cache_manager._cache_translation_results(translation_cache_key, self.main_page.blk_list)
                    logger.info("Translation completed and cached for %d blocks", len(self.main_page.blk_list))
                
                set_upper_case(self.main_page.blk_list, upper_case)

    def translate_webtoon_visible_area(self, single_block=False):
        """Perform translation on the visible area in webtoon mode."""
        source_lang = self.main_page.s_combo.currentText()
        target_lang = self.main_page.t_combo.currentText()
        
        if not (self.main_page.image_viewer.hasPhoto() and 
                self.main_page.webtoon_mode):
            logger.warning("translate_webtoon_visible_area called but not in webtoon mode")
            return
        
        # Get the visible area image and mapping data
        visible_image, mappings = self.main_page.image_viewer.get_visible_area_image()
        if visible_image is None or not mappings:
            logger.warning("No visible area found for translation")
            return
        
        # Filter blocks to only those in the visible area and convert coordinates
        visible_blocks = filter_and_convert_visible_blocks(
            self.main_page, self.pipeline, mappings, single_block
        )
        if not visible_blocks:
            logger.info("No blocks found in visible area")
            return
        
        # Perform translation on the visible image with filtered blocks
        settings_page = self.main_page.settings_page
        extra_context = settings_page.get_llm_settings()['extra_context']
        upper_case = settings_page.ui.uppercase_checkbox.isChecked()
        
        translator = Translator(self.main_page, source_lang, target_lang)
        translator.translate(visible_blocks, visible_image, extra_context)
        
        # Translation is set, now restore original coordinates
        restore_original_block_coordinates(visible_blocks)
        
        # Apply upper case if needed
        set_upper_case(visible_blocks, upper_case)
        
        logger.info(f"Translation completed for {len(visible_blocks)} blocks in visible area")
