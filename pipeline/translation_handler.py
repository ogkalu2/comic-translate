from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from modules.translation.processor import Translator
from modules.utils.translator_utils import set_upper_case, sanitize_translation_source_blocks
from pipeline.webtoon_utils import filter_and_convert_visible_blocks, restore_original_block_coordinates
from pipeline.translation_context import (
    build_translation_prompt_context,
    store_page_translation_context,
)
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

    def _get_current_file_path(self):
        if 0 <= self.main_page.curr_img_idx < len(self.main_page.image_files):
            return self.main_page.image_files[self.main_page.curr_img_idx]
        return None

    def _get_translation_image(self):
        """Return the stable page image used for translation/cache keying.

        The regular manual path must hash the same underlying page image as the
        batch path, otherwise translation cache keys diverge and manual
        translate reprocesses the page.
        """
        file_path = self._get_current_file_path()
        if file_path:
            try:
                image = self.main_page.image_ctrl.load_original_image(file_path)
                if image is not None:
                    return image
            except Exception:
                logger.debug(
                    "Failed to load stable page image for translation; "
                    "falling back to viewer snapshot.",
                    exc_info=True,
                )
        return self.main_page.image_viewer.get_image_array()

    def _build_translation_context(self, target_lang: str) -> tuple[str, str, str]:
        file_path = self._get_current_file_path()
        prompt_context, cache_signature = build_translation_prompt_context(
            self.main_page,
            file_path,
            target_lang,
            llm_settings=self.main_page.settings_page.get_llm_settings(),
        )
        return prompt_context, cache_signature, file_path or ""

    def _store_current_page_translation_context(self, target_lang: str, scene_memory: str = "") -> None:
        file_path = self._get_current_file_path()
        if not file_path:
            return
        store_page_translation_context(
            self.main_page.image_states,
            file_path,
            target_lang,
            self.main_page.blk_list,
            scene_memory=scene_memory or "",
            llm_settings=self.main_page.settings_page.get_llm_settings(),
        )

    def translate_image(self, single_block=False):
        target_lang = self.main_page.t_combo.currentText()
        if self.main_page.image_viewer.hasPhoto() and self.main_page.blk_list:
            settings_page = self.main_page.settings_page
            image = self._get_translation_image()
            prompt_context, cache_signature, _file_path = self._build_translation_context(target_lang)
            translator_key = settings_page.get_tool_selection('translator')

            upper_case = settings_page.ui.uppercase_checkbox.isChecked()

            translator = Translator(self.main_page, "", target_lang)
            sanitize_translation_source_blocks(self.main_page.blk_list)
            
            # Get translation cache key
            translation_cache_key = self.cache_manager._get_translation_cache_key(
                image, "", target_lang, translator_key, cache_signature
            )
            
            if single_block:
                blk = self.pipeline.get_selected_block()
                if blk is None:
                    return
                sanitize_translation_source_blocks([blk])
                
                # Check if block already has translation to avoid redundant processing
                if hasattr(blk, 'translation') and blk.translation and blk.translation.strip():
                    return
                
                # Check if we have cached translation results for this image/translator/language combination
                if self.cache_manager._is_translation_cached(translation_cache_key):
                    # Check if block exists in cache and source text matches
                    cached_translation = self.cache_manager._get_cached_translation_for_block(translation_cache_key, blk)
                    if cached_translation is not None:  # Block was processed and source text matches
                        blk.translation = cached_translation
                        logger.debug(f"Using cached translation result for block: '{cached_translation}'")
                        set_upper_case([blk], upper_case)
                        return
                    else:
                        logger.debug("Block not found in cache or source text changed, processing single block...")
                    
                    # If we reach here, need to process the block
                    single_block_list = [blk]
                    translator.translate(
                        single_block_list,
                        image,
                        prompt_context,
                    )
                    
                    # Update the cache with this new result using the cache manager's method
                    self.cache_manager.update_translation_cache_for_block(translation_cache_key, blk)
                    if all((getattr(item, 'translation', '') or '').strip() for item in self.main_page.blk_list):
                        self._store_current_page_translation_context(target_lang)
                    
                    logger.debug(f"Processed single block and updated cache: '{blk.translation}'")
                    set_upper_case([blk], upper_case)
                else:
                    # Run translation on all blocks and cache the results
                    logger.debug("No cached translation results found, running translation on entire page...")
                    # Create a mapping between original blocks and their copies
                    all_blocks_copy = []
                    
                    for original_blk in self.main_page.blk_list:
                        sanitize_translation_source_blocks([original_blk])
                        copy_blk = original_blk.deep_copy()
                        all_blocks_copy.append(copy_blk)
                    
                    if all_blocks_copy:  
                        translator.translate(
                            all_blocks_copy,
                            image,
                            prompt_context,
                        )
                        # Cache using the original blocks to maintain consistent IDs
                        self.cache_manager._cache_translation_results(translation_cache_key, self.main_page.blk_list, all_blocks_copy)
                        cached_translation = self.cache_manager._get_cached_translation_for_block(translation_cache_key, blk)
                        blk.translation = cached_translation
                        scene_memory = getattr(getattr(translator, "engine", None), "last_scene_memory", "")
                        self._store_current_page_translation_context(target_lang, scene_memory)
                        logger.debug(f"Cached translation results and extracted translation for block: {cached_translation}")
                    
                    set_upper_case([blk], upper_case)
            else:
                # For full page translation, check if we can use cached results
                self.cache_manager._apply_cached_translations_to_blocks(translation_cache_key, self.main_page.blk_list)
                missing_blocks = self.cache_manager._get_missing_translation_blocks(
                    translation_cache_key,
                    self.main_page.blk_list,
                )
                if not missing_blocks:
                    logger.debug(f"Using cached translation results for all {len(self.main_page.blk_list)} blocks")
                    self._store_current_page_translation_context(target_lang)
                else:
                    translator.translate(
                        self.main_page.blk_list,
                        image,
                        prompt_context,
                    )
                    self.cache_manager._cache_translation_results(
                        translation_cache_key,
                        self.main_page.blk_list,
                    )
                    scene_memory = getattr(getattr(translator, "engine", None), "last_scene_memory", "")
                    self._store_current_page_translation_context(target_lang, scene_memory)
                    logger.debug(
                        "Translation cache incomplete for %d blocks; retranslated full page with %d blocks",
                        len(missing_blocks),
                        len(self.main_page.blk_list),
                    )
                
                set_upper_case(self.main_page.blk_list, upper_case)

    def translate_webtoon_visible_area(self, single_block=False):
        """Perform translation on the visible area in webtoon mode."""
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
        sanitize_translation_source_blocks(visible_blocks)
        
        # Perform translation on the visible image with filtered blocks
        settings_page = self.main_page.settings_page
        prompt_context, _cache_signature, _file_path = self._build_translation_context(target_lang)
        upper_case = settings_page.ui.uppercase_checkbox.isChecked()
        
        translator = Translator(self.main_page, "", target_lang)
        translator.translate(
            visible_blocks,
            visible_image,
            prompt_context,
        )
        
        # Translation is set, now restore original coordinates
        restore_original_block_coordinates(visible_blocks)
        
        # Apply upper case if needed
        set_upper_case(visible_blocks, upper_case)
        
        logger.info(f"Translation completed for {len(visible_blocks)} blocks in visible area")
