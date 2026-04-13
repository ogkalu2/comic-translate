import hashlib
import logging
from copy import deepcopy
from modules.utils.translator_utils import sanitize_translation_result_text

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages OCR and translation caching for the pipeline."""

    def __init__(self):
        self.ocr_cache = {}  # OCR results cache: {(image_hash, model_key, device): {block_id: text}}
        self.translation_cache = {}  # Translation results cache: {(image_hash, translator_key, target_lang, extra_context): {block_id: {source_text: str, translation: str}}}
        self.inpaint_cache = {}  # Inpainting results cache: {(image_hash, inpainter_key): inpainted_image}

    def clear_ocr_cache(self):
        """Clear the OCR cache. Note: Cache now persists across image and model changes automatically."""
        self.ocr_cache = {}
        logger.info("OCR cache manually cleared")

    def clear_translation_cache(self):
        """Clear the translation cache. Note: Cache now persists across image and model changes automatically."""
        self.translation_cache = {}
        logger.info("Translation cache manually cleared")

    def clear_cache_for_images(self, images) -> int:
        """Clear all cache entries (OCR, translation, inpaint) for the provided images."""
        image_hashes = {
            self._generate_image_hash(image)
            for image in images
            if image is not None
        }
        if not image_hashes:
            return 0

        cleared = 0
        # OCR cache: keys are (image_hash, model, lang, device)
        keys_to_remove = [k for k in self.ocr_cache if k and k[0] in image_hashes]
        for k in keys_to_remove:
            self.ocr_cache.pop(k, None)
            cleared += 1

        # Translation cache: keys are (image_hash, translator, src, trg, ctx)
        keys_to_remove = [k for k in self.translation_cache if k and k[0] in image_hashes]
        for k in keys_to_remove:
            self.translation_cache.pop(k, None)
            cleared += 1

        # Inpaint cache: keys are (image_hash, inpainter_key)
        keys_to_remove = [k for k in self.inpaint_cache if k and k[0] in image_hashes]
        for k in keys_to_remove:
            self.inpaint_cache.pop(k, None)
            cleared += 1

        if cleared:
            logger.info(
                "Cleared %d cache entries across all caches for %d image hashes",
                cleared,
                len(image_hashes),
            )
        return cleared

    def export_state(self) -> dict:
        """Export cache contents in a project-serializable form."""
        return {
            "version": 1,
            "ocr_cache": [
                {
                    "cache_key": cache_key,
                    "blocks": deepcopy(blocks),
                }
                for cache_key, blocks in self.ocr_cache.items()
            ],
            "translation_cache": [
                {
                    "cache_key": cache_key,
                    "blocks": deepcopy(blocks),
                }
                for cache_key, blocks in self.translation_cache.items()
            ],
        }

    def import_state(self, state: dict | None) -> None:
        """Restore cache contents from a project-serialized form."""
        self.clear_all_caches()
        if not state:
            return

        for entry in state.get("ocr_cache", []) or []:
            cache_key = entry.get("cache_key")
            blocks = entry.get("blocks") or {}
            if cache_key is not None:
                normalized_key = self._normalize_ocr_cache_key(cache_key)
                self.ocr_cache[normalized_key] = dict(blocks)

        for entry in state.get("translation_cache", []) or []:
            cache_key = entry.get("cache_key")
            blocks = entry.get("blocks") or {}
            if cache_key is not None:
                normalized_key = self._normalize_translation_cache_key(cache_key)
                self.translation_cache[normalized_key] = dict(blocks)

        logger.info(
            "Restored cache state: %d OCR entries, %d translation entries",
            len(self.ocr_cache),
            len(self.translation_cache),
        )

    def clear_translation_cache_for_images(self, images) -> int:
        """Clear translation cache entries for the provided images, regardless of translator settings."""
        image_hashes = {
            self._generate_image_hash(image)
            for image in images
            if image is not None
        }
        if not image_hashes:
            return 0

        keys_to_remove = [
            cache_key
            for cache_key in list(self.translation_cache.keys())
            if cache_key and cache_key[0] in image_hashes
        ]
        for cache_key in keys_to_remove:
            self.translation_cache.pop(cache_key, None)

        if keys_to_remove:
            logger.info(
                "Cleared %d translation cache entries for %d image hashes",
                len(keys_to_remove),
                len(image_hashes),
            )
        return len(keys_to_remove)

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

    def _normalize_ocr_cache_key(self, cache_key):
        if isinstance(cache_key, list):
            cache_key = tuple(cache_key)
        if not isinstance(cache_key, tuple):
            return cache_key
        if len(cache_key) == 4:
            image_hash, ocr_model, _source_lang, device = cache_key
            return (image_hash, ocr_model, device)
        return cache_key

    def _normalize_translation_cache_key(self, cache_key):
        if isinstance(cache_key, list):
            cache_key = tuple(cache_key)
        if not isinstance(cache_key, tuple):
            return cache_key
        if len(cache_key) == 5:
            image_hash, translator_key, _source_lang, target_lang, context_hash = cache_key
            return (image_hash, translator_key, target_lang, context_hash)
        return cache_key

    def _get_ocr_cache_key(self, image, source_lang, ocr_model, device=None):
        """Generate cache key for OCR results"""
        image_hash = self._generate_image_hash(image)
        if device is None:
            device = "unknown"
        # `source_lang` is kept in the signature for backward compatibility,
        # but it no longer participates in the cache identity.
        return (image_hash, ocr_model, device)

    def _get_block_id(self, block):
        """Generate a unique identifier for a text block."""
        block_uid = getattr(block, "block_uid", None)
        if block_uid:
            return str(block_uid)
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
                    block_results[block_id] = text
            else:
                # Standard case: use the same blocks for both ID and text
                for blk in blk_list:
                    block_id = self._get_block_id(blk)
                    text = getattr(blk, 'text', '') or ''
                    block_results[block_id] = text
            if block_results:
                self.ocr_cache[cache_key] = block_results
                logger.info(f"Cached OCR results for {len(block_results)} blocks")
            else:
                logger.debug("No OCR blocks found; skipping OCR cache creation")
        except Exception as e:
            logger.warning(f"Failed to cache OCR results: {e}")
            # Don't raise exception, just skip caching
            
    def update_ocr_cache_for_block(self, cache_key, block):
        """Update or add a single block's OCR result to the cache."""
        block_id = self._get_block_id(block)
        text = getattr(block, 'text', '') or ''

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
        # `source_lang` is kept for compatibility only. Translation caches are
        # now target-specific and reuse the same shared OCR/segmentation caches.
        return (image_hash, translator_key, target_lang, context_hash)

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
                    block_results[block_id] = {
                        'source_text': source_text,
                        'translation': translation
                    }
            if block_results:
                self.translation_cache[cache_key] = block_results
                logger.info(f"Cached translation results for {len(block_results)} blocks")
            else:
                logger.debug("No translation blocks found; skipping translation cache creation")
        except Exception as e:
            logger.warning(f"Failed to cache translation results: {e}")

    def update_translation_cache_for_block(self, cache_key, block):
        """Update or add a single block's translation result to the cache."""
        block_id = self._get_block_id(block)
        translation = getattr(block, 'translation', '') or ''
        source_text = getattr(block, 'text', '') or ''

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
                    return sanitize_translation_result_text(result.get('translation', ''))
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

    def _get_missing_ocr_blocks(self, cache_key, block_list):
        """Return OCR blocks that are not already satisfied by cache."""
        return [
            block
            for block in block_list or []
            if self._get_cached_text_for_block(cache_key, block) is None
        ]

    def _can_serve_all_blocks_from_translation_cache(self, cache_key, block_list):
        """Check if all blocks in the list can be served from translation cache with matching source text"""
        if not self._is_translation_cached(cache_key):
            return False
        
        for block in block_list:
            cached_translation = self._get_cached_translation_for_block(cache_key, block)
            if cached_translation is None:  # Block not found in cache or source text changed
                return False
        
        return True

    def _get_missing_translation_blocks(self, cache_key, block_list):
        """Return translation blocks that are not already satisfied by cache."""
        return [
            block
            for block in block_list or []
            if self._get_cached_translation_for_block(cache_key, block) is None
        ]

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
                block.translation = sanitize_translation_result_text(cached_translation)

    def _get_inpaint_cache_key(self, image, inpainter_key):
        """Generate cache key for inpainting results"""
        image_hash = self._generate_image_hash(image)
        return (image_hash, inpainter_key)

    def _is_inpaint_cached(self, cache_key):
        """Check if inpainting results are cached"""
        return cache_key in self.inpaint_cache

    def _get_cached_inpaint(self, cache_key):
        """Retrieve cached inpainted image"""
        return self.inpaint_cache.get(cache_key)

    def _cache_inpaint_result(self, cache_key, inpainted_image):
        """Cache inpainting result"""
        if inpainted_image is not None:
            self.inpaint_cache[cache_key] = inpainted_image
            logger.info(f"Cached inpainting result for key {cache_key}")

    def clear_inpaint_cache(self):
        """Clear the inpainting cache"""
        self.inpaint_cache = {}
        logger.info("Inpaint cache manually cleared")

    def clear_all_caches(self):
        """Clear OCR, translation, and inpaint caches."""
        self.clear_ocr_cache()
        self.clear_translation_cache()
        self.clear_inpaint_cache()
