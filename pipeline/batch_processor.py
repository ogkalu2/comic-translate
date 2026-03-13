from __future__ import annotations

import os
import json
import requests
import logging
import traceback
import imkit as imk
import time
from typing import TYPE_CHECKING
from datetime import datetime
from typing import List
from PySide6.QtGui import QColor

from modules.detection.processor import TextBlockDetector
from modules.translation.processor import Translator
from modules.utils.textblock import sort_blk_list
from modules.utils.pipeline_config import get_config
from modules.utils.image_utils import generate_mask, get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.translator_utils import get_raw_translation, get_raw_text, format_translations
from modules.rendering.render import get_best_render_area, pyside_word_wrap, is_vertical_block
from modules.utils.device import resolve_device
from modules.utils.exceptions import InsufficientCreditsException
from app.ui.canvas.text_item import OutlineInfo, OutlineType
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.save_renderer import ImageSaveRenderer
from .cache_manager import CacheManager
from .block_detection import BlockDetectionHandler
from .inpainting import InpaintingHandler
from .ocr_handler import OCRHandler
from .discovery_pass import DiscoveryPass
from .comic_session import ComicSession
from .sfx_classifier import classify_sfx_blocks
from .batch_base import BatchProcessorBase

if TYPE_CHECKING:
    from controller import ComicTranslate

logger = logging.getLogger(__name__)


class BatchProcessor(BatchProcessorBase):
    """Handles batch processing of comic translation."""

    def __init__(
            self,
            main_page: ComicTranslate,
            cache_manager: CacheManager,
            block_detection_handler: BlockDetectionHandler,
            inpainting_handler: InpaintingHandler,
            ocr_handler: OCRHandler
        ):
        super().__init__(main_page, cache_manager, block_detection_handler, inpainting_handler, ocr_handler)
        self.comic_session = None

    def emit_progress(self, index, total, step, steps, change_name):
        """Wrapper around main_page.progress_update.emit that logs a human-readable stage."""
        stage_map = {
            0: 'start-image',
            1: 'text-block-detection',
            2: 'ocr-processing',
            3: 'pre-inpaint-setup',
            4: 'generate-mask',
            5: 'inpainting',
            7: 'translation',
            9: 'text-rendering-prepare',
            10: 'save-and-finish',
        }
        stage_name = stage_map.get(step, f'stage-{step}')
        logger.info(f"Progress: image_index={index}/{total} step={step}/{steps} ({stage_name}) change_name={change_name}")
        self.main_page.progress_update.emit(index, total, step, steps, change_name)

    def batch_process(self, selected_paths: List[str] = None):
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        image_list = selected_paths if selected_paths is not None else self.main_page.image_files
        total_images = len(image_list)

        # Pass 1 setup: create ComicSession and DiscoveryPass for this batch
        if image_list:
            first_path = image_list[0]
            first_state = self.main_page.image_states.get(first_path, {})
            src_lang = first_state.get('source_lang', '')
            tgt_lang = first_state.get('target_lang', '')
            comic_id = f"batch_{int(time.time())}"
            self.comic_session = ComicSession(comic_id, src_lang, tgt_lang)
            discovery = DiscoveryPass(comic_id, src_lang, tgt_lang)
            # Wire session into translation handler if available
            if hasattr(self.main_page, 'pipeline') and hasattr(self.main_page.pipeline, 'translation_handler'):
                self.main_page.pipeline.translation_handler.comic_session = self.comic_session

        for index, image_path in enumerate(image_list):
            if self._is_cancelled():
                return

            file_on_display = self.main_page.image_files[self.main_page.curr_img_idx]

            # index, step, total_steps, change_name
            self.emit_progress(index, total_images, 0, 10, True)

            settings_page = self.main_page.settings_page
            source_lang = self.main_page.image_states[image_path]['source_lang']
            target_lang = self.main_page.image_states[image_path]['target_lang']

            target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
            trg_lng_cd = get_language_code(target_lang_en)
            
            base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
            extension = os.path.splitext(image_path)[1]
            directory, archive_bname = self._resolve_archive_info(image_path)

            image = imk.read_image(image_path)

            # skip UI-skipped images
            state = self.main_page.image_states.get(image_path, {})
            if state.get('skip', False):
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.log_skipped_image(directory, timestamp, image_path, "User-skipped")
                continue

            # Text Block Detection
            self.emit_progress(index, total_images, 1, 10, False)
            if self._is_cancelled():
                return

            # Use the shared block detector from the handler
            if self.block_detection.block_detector_cache is None:
                self.block_detection.block_detector_cache = TextBlockDetector(settings_page)
            
            blk_list = self.block_detection.block_detector_cache.detect(image)
            classify_sfx_blocks(blk_list)

            self.emit_progress(index, total_images, 2, 10, False)
            if self._is_cancelled():
                return

            if blk_list:
                # Get ocr cache key for batch processing
                ocr_model = settings_page.get_tool_selection('ocr')
                device = resolve_device(settings_page.is_gpu_enabled())
                cache_key = self.cache_manager._get_ocr_cache_key(image, source_lang, ocr_model, device)
                # Use the shared OCR processor from the handler
                self.ocr_handler.ocr.initialize(self.main_page, source_lang)
                try:
                    self.ocr_handler.ocr.process(image, blk_list)
                    # Cache the OCR results for potential future use
                    self.cache_manager._cache_ocr_results(cache_key, self.main_page.blk_list)
                    # Accumulate OCR text for discovery pass
                    if self.comic_session is not None:
                        discovery.add_page_ocr_results(blk_list)
                    source_lang_english = self.main_page.lang_mapping.get(source_lang, source_lang)
                    rtl = True if source_lang_english == 'Japanese' else False
                    blk_list = sort_blk_list(blk_list, rtl)
                    # Re-run classifier now that OCR text is available
                    classify_sfx_blocks(blk_list)
                    # Glossary-based SFX confirmation (Signal B)
                    if self.comic_session is not None:
                        for blk in blk_list:
                            if not blk.is_sfx and blk.text and self.comic_session.glossary.is_sfx_term(blk.text):
                                blk.is_sfx = True

                except InsufficientCreditsException:
                    raise
                except Exception as e:
                    # if it's an HTTPError, try to pull the "error_description" field
                    if isinstance(e, requests.exceptions.HTTPError):
                        try:
                            err_json = e.response.json()
                            err_msg = err_json.get("error_description", str(e))
                        except Exception:
                            err_msg = str(e)
                    else:
                        err_msg = str(e)

                    logger.exception(f"OCR processing failed: {err_msg}")
                    reason = f"OCR: {err_msg}"
                    full_traceback = traceback.format_exc()
                    self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                    self.main_page.image_skipped.emit(image_path, "OCR", err_msg)
                    self.log_skipped_image(directory, timestamp, image_path, reason, full_traceback)
                    continue
            else:
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.main_page.image_skipped.emit(image_path, "Text Blocks", "")
                self.log_skipped_image(directory, timestamp, image_path, "No text blocks detected")
                continue

            self.emit_progress(index, total_images, 3, 10, False)
            if self._is_cancelled():
                return

            # Clean Image of text
            export_settings = settings_page.get_export_settings()

            self._ensure_inpainter()

            config = get_config(settings_page)
            logger.info("pre-inpaint: generating mask (blk_list=%d blocks)", len(blk_list))
            t0 = time.time()
            mask = generate_mask(image, blk_list)
            t1 = time.time()
            logger.info("pre-inpaint: mask generated in %.2fs (mask shape=%s)", t1 - t0, getattr(mask, 'shape', None))

            self.emit_progress(index, total_images, 4, 10, False)
            if self._is_cancelled():
                return

            inpaint_input_img = self.inpainting.inpainter_cache(image, mask, config)
            inpaint_input_img = imk.convert_scale_abs(inpaint_input_img)

            # Saving cleaned image
            patches = self.inpainting.get_inpainted_patches(mask, inpaint_input_img)
            self.main_page.patches_processed.emit(patches, image_path)

            # inpaint_input_img is already in RGB format

            if export_settings['export_inpainted_image']:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "cleaned_images", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                imk.write_image(os.path.join(path, f"{base_name}_cleaned{extension}"), inpaint_input_img)

            self.emit_progress(index, total_images, 5, 10, False)
            if self._is_cancelled():
                return

            # Get Translations/ Export if selected
            extra_context = settings_page.get_llm_settings()['extra_context']
            # Inject glossary + story context if a ComicSession is active
            if self.comic_session is not None:
                session_prompt = self.comic_session.build_system_prompt()
                extra_context = f"{extra_context}\n{session_prompt}".strip()
            translator_key = settings_page.get_tool_selection('translator')
            translator = Translator(self.main_page, source_lang, target_lang)
            
            # Get translation cache key for batch processing
            translation_cache_key = self.cache_manager._get_translation_cache_key(
                image, source_lang, target_lang, translator_key, extra_context
            )
            
            try:
                translator.translate(blk_list, image, extra_context)
                # Enforce glossary on output to ensure consistent character names across pages
                if self.comic_session is not None:
                    for blk in blk_list:
                        if blk.translation:
                            blk.translation = self.comic_session.enforce_glossary(blk.translation)
                # Cache the translation results for potential future use
                self.cache_manager._cache_translation_results(translation_cache_key, blk_list)
            except InsufficientCreditsException:
                raise
            except Exception as e:
                # if it's an HTTPError, try to pull the "error_description" field
                if isinstance(e, requests.exceptions.HTTPError):
                    try:
                        err_json = e.response.json()
                        err_msg = err_json.get("error_description", str(e))
                    except Exception:
                        err_msg = str(e)
                else:
                    err_msg = str(e)

                logger.exception(f"Translation failed: {err_msg}")
                reason = f"Translator: {err_msg}"
                full_traceback = traceback.format_exc()
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.main_page.image_skipped.emit(image_path, "Translator", err_msg)
                self.log_skipped_image(directory, timestamp, image_path, reason, full_traceback)
                continue

            if self._is_cancelled():
                return

            entire_raw_text = get_raw_text(blk_list)
            entire_translated_text = get_raw_translation(blk_list)

            # Parse JSON strings and check if they're empty objects or invalid
            try:
                raw_text_obj = json.loads(entire_raw_text)
                translated_text_obj = json.loads(entire_translated_text)
                
                if (not raw_text_obj) or (not translated_text_obj):
                    self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                    self.main_page.image_skipped.emit(image_path, "Translator", "")
                    self.log_skipped_image(directory, timestamp, image_path, "Translator: empty JSON")
                    continue
            except json.JSONDecodeError as e:
                # Handle invalid JSON
                error_message = str(e)
                reason = f"Translator: JSONDecodeError: {error_message}"
                logger.exception(reason)
                full_traceback = traceback.format_exc()
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.main_page.image_skipped.emit(image_path, "Translator", error_message)
                self.log_skipped_image(directory, timestamp, image_path, reason, full_traceback)
                continue

            if export_settings['export_raw_text']:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "raw_texts", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_raw.txt"), 'w', encoding='UTF-8')
                file.write(entire_raw_text)

            if export_settings['export_translated_text']:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_texts", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_translated.txt"), 'w', encoding='UTF-8')
                file.write(entire_translated_text)

            self.emit_progress(index, total_images, 7, 10, False)
            if self._is_cancelled():
                return

            # Text Rendering
            render_settings = self.main_page.render_settings()
            upper_case = render_settings.upper_case
            outline = render_settings.outline
            format_translations(blk_list, trg_lng_cd, upper_case=upper_case)
            get_best_render_area(blk_list, image, inpaint_input_img)

            font = render_settings.font_family
            setting_font_color = QColor(render_settings.color)

            max_font_size = render_settings.max_font_size
            min_font_size = render_settings.min_font_size
            line_spacing = float(render_settings.line_spacing) 
            outline_width = float(render_settings.outline_width)
            outline_color = QColor(render_settings.outline_color) if outline else None
            bold = render_settings.bold
            italic = render_settings.italic
            underline = render_settings.underline
            alignment_id = render_settings.alignment_id
            alignment = self.main_page.button_to_alignment[alignment_id]
            direction = render_settings.direction
                
            text_items_state = []
            for blk in blk_list:
                x1, y1, width, height = blk.xywh

                translation = blk.translation
                if not translation or len(translation) == 1:
                    continue
                
                # Determine if this block should use vertical rendering
                vertical = is_vertical_block(blk, trg_lng_cd)

                translation, font_size = pyside_word_wrap(
                    translation, 
                    font, 
                    width, 
                    height,
                    line_spacing, 
                    outline_width, 
                    bold, 
                    italic, 
                    underline,
                    alignment, 
                    direction, 
                    max_font_size, 
                    min_font_size,
                    vertical
                )
                
                # Display text if on current page  
                if image_path == file_on_display:
                    self.main_page.blk_rendered.emit(translation, font_size, blk, image_path)

                # Language-specific formatting for state storage
                if is_no_space_lang(trg_lng_cd):
                    translation = translation.replace(' ', '')

                # Smart Color Override
                font_color = get_smart_text_color(blk.font_color, setting_font_color)

                # SFX blocks render over original artwork — force outline for legibility
                blk_outline_color = outline_color
                blk_outline_width = outline_width
                blk_outline = outline
                if getattr(blk, 'is_sfx', False):
                    blk_outline = True
                    blk_outline_color = QColor(render_settings.outline_color) if render_settings.outline_color else QColor("#000000")
                    if blk_outline_width < 1.0:
                        blk_outline_width = 2.0

                # Use TextItemProperties for consistent text item creation
                text_props = TextItemProperties(
                    text=translation,
                    font_family=font,
                    font_size=font_size,
                    text_color=font_color,
                    alignment=alignment,
                    line_spacing=line_spacing,
                    outline_color=blk_outline_color,
                    outline_width=blk_outline_width,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    position=(x1, y1),
                    rotation=blk.angle,
                    scale=1.0,
                    transform_origin=blk.tr_origin_point,
                    width=width,
                    direction=direction,
                    vertical=vertical,
                    selection_outlines=[
                        OutlineInfo(0, len(translation),
                        blk_outline_color,
                        blk_outline_width,
                        OutlineType.Full_Document)
                    ] if blk_outline else [],
                )
                text_items_state.append(text_props.to_dict())

            self.main_page.image_states[image_path]['viewer_state'].update({
                'text_items_state': text_items_state
                })
            
            self.main_page.image_states[image_path]['viewer_state'].update({
                'push_to_stack': True
                })
            
            self.emit_progress(index, total_images, 9, 10, False)
            if self._is_cancelled():
                return

            # Saving blocks with texts to history
            self.main_page.image_states[image_path].update({
                'blk_list': blk_list                   
            })

            # Notify UI that this page's render state is finalized.
            # This enables a deterministic refresh when the user navigates to this page
            # during processing and misses live blk_rendered events.
            self.main_page.render_state_ready.emit(image_path)

            if image_path == file_on_display:
                self.main_page.blk_list = blk_list
                
            render_save_dir = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
            
            # Conditional Save: Final Rendered Image
            if export_settings['auto_save']:
                if not os.path.exists(render_save_dir):
                    os.makedirs(render_save_dir, exist_ok=True)
                sv_pth = os.path.join(render_save_dir, f"{base_name}_translated{extension}")

                renderer = ImageSaveRenderer(image)
                viewer_state = self.main_page.image_states[image_path]['viewer_state'].copy()
                patches = self.main_page.image_patches.get(image_path, [])
                renderer.apply_patches(patches)
                renderer.add_state_to_image(viewer_state)
                renderer.save_image(sv_pth)
            else:
                # If auto-save is OFF, we still want to apply the state to the image state
                # so the user can verify it in the UI, but we don't write to disk.
                pass

            self.emit_progress(index, total_images, 10, 10, False)

        if self._is_cancelled():
            return
        self._pack_archives(timestamp, total_images, settings_page.get_export_settings())
