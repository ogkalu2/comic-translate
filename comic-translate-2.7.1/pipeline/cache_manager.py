import hashlib
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages OCR and translation caching for the pipeline."""
    
    def __init__(self):
        self.ocr_cache = {}  # OCR results cache: {(image_hash, model_key, source_lang): {block_id: text}}
        self.translation_cache = {}  # Translation results cache: {(image_hash, translator_key, source_lang, target_lang, extra_context): {block_id: {source_text: str, translation: str}}}

    def clear_ocr_cache(self):
        """Clear the OCR cache. Note: Cache now persists across image and model changes automatically."""
        self.ocr_cache = {}
        logger.info("OCR cache manually cleared")

    def clear_translation_cache(self):
        """Clear the translation cache. Note: Cache now persists across image and model changes automatically."""
        self.translation_cache = {}
        logger.info("Translation cache manually cleared")

    def _generate_image_hash(self, image):
        """Generate a hash for the image to use as cache key"""
        try:
            # Use a small portion of the image data to generate hash for efficiency
            # Take every 10th pixel to reduce computation while maintaining uniqueness
            sample_data = image[::10, ::10].tobytes()
            return hashlib.md5(sample_data).hexdigest()
        except Exception as e:
            # Fallback: use the full image shape and first few bytes if sampling fails
            shape_str = str(image.shape) if hasattr(image, 'shape') else str(type(image))
            fallback_data = shape_str.encode() + str(image.dtype).encode() if hasattr(image, 'dtype') else b'fallback'
            return hashlib.md5(fallback_data).hexdigest()

    def _get_ocr_cache_key(self, image, source_lang, ocr_model, device=None):
        """Generate cache key for OCR results"""
        image_hash = self._generate_image_hash(image)
        if device is None:
            device = "unknown"
        return (image_hash, ocr_model, source_lang, device)

    def _get_block_id(self, block):
        """Generate a unique identifier for a text block based on its position"""
        try:
            x1, y1, x2, y2 = block.xyxy
            angle = block.angle
            return f"{int(x1)}_{int(y1)}_{int(x2)}_{int(y2)}_{int(angle)}"
        except (AttributeError, ValueError, TypeError):
            return str(id(block))

    def _find_matching_block_id(self, cache_key, target_block):
        """Find a matching block ID in cache, allowing for small coordinate differences"""
        target_id = self._get_block_id(target_block)
        cached_results = self.ocr_cache.get(cache_key, {})
        
        # First try exact match
        if target_id in cached_results:
            return target_id, cached_results[target_id]
        
        # If no exact match, try fuzzy matching for coordinates within tolerance
        try:
            target_x1, target_y1, target_x2, target_y2 = target_block.xyxy
            target_angle = getattr(target_block, 'angle', 0)
            
            # Tolerance for coordinate matching (in pixels)
            tolerance = 5.0
            
            for cached_id in cached_results.keys():
                try:
                    # Parse the cached ID to extract coordinates
                    parts = cached_id.split('_')
                    if len(parts) >= 5:
                        cached_x1 = float(parts[0])
                        cached_y1 = float(parts[1])
                        cached_x2 = float(parts[2])
                        cached_y2 = float(parts[3])
                        cached_angle = float(parts[4])
                        
                        # Check if coordinates are within tolerance
                        if (abs(target_x1 - cached_x1) <= tolerance and
                            abs(target_y1 - cached_y1) <= tolerance and
                            abs(target_x2 - cached_x2) <= tolerance and
                            abs(target_y2 - cached_y2) <= tolerance and
                            abs(target_angle - cached_angle) <= 1.0):  # 1 degree tolerance for angle
                            
                            logger.debug(f"Fuzzy match found for OCR: {target_id[:20]}... -> {cached_id[:20]}...")
                            return cached_id, cached_results[cached_id]
                except (ValueError, IndexError):
                    continue
                    
        except (AttributeError, ValueError, TypeError):
            pass
        
        # No match found
        return None, ""

    def _find_matching_translation_block_id(self, cache_key, target_block):
        """Find a matching block ID in translation cache, allowing for small coordinate differences"""
        target_id = self._get_block_id(target_block)
        cached_results = self.translation_cache.get(cache_key, {})
        
        # First try exact match
        if target_id in cached_results:
            return target_id, cached_results[target_id]
        
        # If no exact match, try fuzzy matching for coordinates within tolerance
        try:
            target_x1, target_y1, target_x2, target_y2 = target_block.xyxy
            target_angle = getattr(target_block, 'angle', 0)
            
            # Tolerance for coordinate matching (in pixels)
            tolerance = 5.0
            
            for cached_id in cached_results.keys():
                try:
                    # Parse the cached ID to extract coordinates
                    parts = cached_id.split('_')
                    if len(parts) >= 5:
                        cached_x1 = float(parts[0])
                        cached_y1 = float(parts[1])
                        cached_x2 = float(parts[2])
                        cached_y2 = float(parts[3])
                        cached_angle = float(parts[4])
                        
                        # Check if coordinates are within tolerance
                        if (abs(target_x1 - cached_x1) <= tolerance and
                            abs(target_y1 - cached_y1) <= tolerance and
                            abs(target_x2 - cached_x2) <= tolerance and
                            abs(target_y2 - cached_y2) <= tolerance and
                            abs(target_angle - cached_angle) <= 1.0):  # 1 degree tolerance for angle
                            
                            logger.debug(f"Fuzzy match found for translation: {target_id[:20]}... -> {cached_id[:20]}...")
                            return cached_id, cached_results[cached_id]
                except (ValueError, IndexError):
                    continue
                    
        except (AttributeError, ValueError, TypeError):
            pass
        
        # No match found
        return None, ""

    def _is_ocr_cached(self, cache_key):
        """Check if OCR results are cached for this image/model/language combination"""
        return cache_key in self.ocr_cache

    def _cache_ocr_results(self, cache_key, blk_list, processed_blk_list=None):
        """Cache OCR results for all blocks"""
        try:
            block_results = {}
            # If we have separate processed blocks (with OCR results), use them for text
            # but use original blocks for consistent IDs
            if processed_blk_list is not None:
                for original_blk, processed_blk in zip(blk_list, processed_blk_list):
                    block_id = self._get_block_id(original_blk)  # Use original block for ID
                    text = getattr(processed_blk, 'text', '') or ''  # Get text from processed block
                    # Only include blocks that actually have OCR text
                    if text:
                        block_results[block_id] = text
            else:
                # Standard case: use the same blocks for both ID and text
                for blk in blk_list:
                    block_id = self._get_block_id(blk)
                    text = getattr(blk, 'text', '') or ''
                    # Only include blocks that actually have OCR text
                    if text:
                        block_results[block_id] = text
            # Do not create a cache entry if there are no blocks with OCR text
            if block_results:
                self.ocr_cache[cache_key] = block_results
                logger.info(f"Cached OCR results for {len(block_results)} blocks")
            else:
                logger.debug("No OCR text found in blocks; skipping OCR cache creation")
        except Exception as e:
            logger.warning(f"Failed to cache OCR results: {e}")
            # Don't raise exception, just skip caching
            
    def update_ocr_cache_for_block(self, cache_key, block):
        """Update or add a single block's OCR result to the cache."""
        block_id = self._get_block_id(block)
        text = getattr(block, 'text', '') or ''

        # Don't create/update cache entries for empty OCR text
        if not text:
            logger.debug(f"Skipping OCR cache update for empty text for block ID {block_id}")
            return

        if cache_key not in self.ocr_cache:
            self.ocr_cache[cache_key] = {}

        self.ocr_cache[cache_key][block_id] = text
        logger.debug(f"Updated OCR cache for block ID {block_id}")


    def _get_cached_text_for_block(self, cache_key, block):
        """Retrieve cached text for a specific block"""
        matched_id, result = self._find_matching_block_id(cache_key, block)
        
        if matched_id is not None:  # Block found in cache
            return result  # Return the cached text (could be empty string)
        else:
            # Block not found in cache at all
            # Debug logging to help identify cache issues (only log when block not found in cache)
            block_id = self._get_block_id(block)
            cached_results = self.ocr_cache.get(cache_key, {})
            logger.debug(f"No cached text found for block ID {block_id}")
            logger.debug(f"Available block IDs in cache: {list(cached_results.keys())}")
            return None  # Indicate block needs processing

    def _get_translation_cache_key(self, image, source_lang, target_lang, translator_key, extra_context):
        """Generate cache key for translation results"""
        image_hash = self._generate_image_hash(image)
        # Include extra_context in cache key since it affects translation results
        context_hash = hashlib.md5(extra_context.encode()).hexdigest() if extra_context else "no_context"
        return (image_hash, translator_key, source_lang, target_lang, context_hash)

    def _is_translation_cached(self, cache_key):
        """Check if translation results are cached for this image/translator/language combination"""
        return cache_key in self.translation_cache

    def _cache_translation_results(self, cache_key, blk_list, processed_blk_list=None):
        """Cache translation results for all blocks"""
        try:
            block_results = {}
            # If we have separate processed blocks (with translation results), use them for translation
            # but use original blocks for consistent IDs
            if processed_blk_list is not None:
                for original_blk, processed_blk in zip(blk_list, processed_blk_list):
                    block_id = self._get_block_id(original_blk)  # Use original block for ID
                    translation = getattr(processed_blk, 'translation', '') or ''  # Get translation from processed block
                    source_text = getattr(original_blk, 'text', '') or ''  # Get source text from original block
                    # Only include blocks that actually have a translation
                    if translation:
                        # Store both source text and translation to validate cache validity
                        block_results[block_id] = {
                            'source_text': source_text,
                            'translation': translation
                        }
            else:
                # Standard case: use the same blocks for both ID and translation
                for blk in blk_list:
                    block_id = self._get_block_id(blk)
                    translation = getattr(blk, 'translation', '') or ''
                    source_text = getattr(blk, 'text', '') or ''
                    # Only include blocks that actually have a translation
                    if translation:
                        block_results[block_id] = {
                            'source_text': source_text,
                            'translation': translation
                        }
            # Do not create a translation cache entry if no translations were present
            if block_results:
                self.translation_cache[cache_key] = block_results
                logger.info(f"Cached translation results for {len(block_results)} blocks")
            else:
                logger.debug("No translations found in blocks; skipping translation cache creation")
        except Exception as e:
            logger.warning(f"Failed to cache translation results: {e}")

    def update_translation_cache_for_block(self, cache_key, block):
        """Update or add a single block's translation result to the cache."""
        block_id = self._get_block_id(block)
        translation = getattr(block, 'translation', '') or ''
        source_text = getattr(block, 'text', '') or ''

        # Don't create/update cache entries for empty translations
        if not translation:
            logger.debug(f"Skipping translation cache update for empty translation for block ID {block_id}")
            return

        if cache_key not in self.translation_cache:
            self.translation_cache[cache_key] = {}

        self.translation_cache[cache_key][block_id] = {
            'source_text': source_text,
            'translation': translation
        }
        logger.debug(f"Updated translation cache for block ID {block_id}")


    def _get_cached_translation_for_block(self, cache_key, block):
        """Retrieve cached translation for a specific block, validating source text matches"""
        matched_id, result = self._find_matching_translation_block_id(cache_key, block)

        if matched_id is not None:  
            if result: 
                cached_source_text = result.get('source_text', '')
                current_source_text = getattr(block, 'text', '') or ''
                
                if cached_source_text == current_source_text:
                    return result.get('translation', '')
                else:
                    # Source text has changed, cache is invalid for this block
                    logger.debug(f"Cache invalid: source text changed from '{cached_source_text}' to '{current_source_text}'")
                    return None  # Indicate cache is invalid, needs reprocessing
            else:
                # Block was processed but had no content (empty result)
                return ''
        else:
            # Block not found in cache at all
            # Debug logging to help identify cache issues (only log when not found)
            block_id = self._get_block_id(block)
            cached_results = self.translation_cache.get(cache_key, {})
            logger.debug(f"No cached translation found for block ID {block_id}")
            logger.debug(f"Available block IDs in cache: {list(cached_results.keys())}")
            return None  # Indicate block needs processing

    def _can_serve_all_blocks_from_ocr_cache(self, cache_key, block_list):
        """Check if all blocks in the list can be served from OCR cache"""
        if not self._is_ocr_cached(cache_key):
            return False
        
        for block in block_list:
            cached_text = self._get_cached_text_for_block(cache_key, block)
            if cached_text is None:  
                return False
        
        return True

    def _can_serve_all_blocks_from_translation_cache(self, cache_key, block_list):
        """Check if all blocks in the list can be served from translation cache with matching source text"""
        if not self._is_translation_cached(cache_key):
            return False
        
        for block in block_list:
            cached_translation = self._get_cached_translation_for_block(cache_key, block)
            if cached_translation is None:  # Block not found in cache or source text changed
                return False
        
        return True

    def _apply_cached_ocr_to_blocks(self, cache_key, block_list):
        """Apply cached OCR results to all blocks in the list"""
        for block in block_list:
            cached_text = self._get_cached_text_for_block(cache_key, block)
            if cached_text is not None: 
                block.text = cached_text  

    def _apply_cached_translations_to_blocks(self, cache_key, block_list):
        """Apply cached translation results to all blocks in the list"""
        for block in block_list:
            cached_translation = self._get_cached_translation_for_block(cache_key, block)
            if cached_translation is not None: 
                block.translation = cached_translation  