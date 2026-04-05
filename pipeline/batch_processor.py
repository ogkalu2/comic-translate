from __future__ import annotations

import gc
import json
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List

import imkit as imk
import requests
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor

from app.path_materialization import ensure_path_materialized
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import OutlineInfo, OutlineType
from app.ui.messages import Messages
from modules.detection.processor import TextBlockDetector
from modules.rendering.render import (
    get_best_render_area,
    is_vertical_block,
    pyside_word_wrap,
)
from modules.translation.processor import Translator
from modules.utils.device import resolve_device
from modules.utils.exceptions import InsufficientCreditsException
from modules.utils.image_utils import generate_mask, get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.pipeline_config import get_config
from modules.utils.textblock import sort_blk_list
from modules.utils.translator_utils import (
    format_translations,
    get_raw_text,
    get_raw_translation,
    sanitize_translation_source_blocks,
)

from .block_detection import BlockDetectionHandler
from .cache_manager import CacheManager
from .inpainting import InpaintingHandler
from .ocr_handler import OCRHandler

if TYPE_CHECKING:
    from controller import ComicTranslate

logger = logging.getLogger(__name__)


@dataclass
class PreparedBatchPage:
    index: int
    image_path: str
    directory: str
    timestamp: str
    base_name: str
    extension: str
    archive_bname: str
    source_lang: str
    target_lang: str
    trg_lng_cd: str
    image: object | None = None
    blk_list: list | None = None
    mask: object | None = None
    inpaint_input_img: object | None = None
    ocr_cache_key: object | None = None
    translation_cache_key: object | None = None
    translation_failed: bool = False


class BatchProcessor:
    """Handles batch processing of comic translation."""

    def __init__(
        self,
        main_page: ComicTranslate,
        cache_manager: CacheManager,
        block_detection_handler: BlockDetectionHandler,
        inpainting_handler: InpaintingHandler,
        ocr_handler: OCRHandler,
    ):
        self.main_page = main_page
        self.cache_manager = cache_manager
        self.block_detection = block_detection_handler
        self.inpainting = inpainting_handler
        self.ocr_handler = ocr_handler

    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        logger.info("Skipping fallback translated image save for '%s'.", base_name)

    def emit_progress(self, index, total, step, steps, change_name):
        """Wrapper around main_page.progress_update.emit that logs a human-readable stage."""
        stage_map = {
            0: "start-image",
            1: "text-block-detection",
            2: "ocr-processing",
            3: "pre-inpaint-setup",
            4: "generate-mask",
            5: "inpainting",
            7: "translation",
            9: "text-rendering-prepare",
            10: "save-and-finish",
        }
        stage_name = stage_map.get(step, f"stage-{step}")
        logger.debug(
            "Progress: image_index=%s/%s step=%s/%s (%s) change_name=%s",
            index,
            total,
            step,
            steps,
            stage_name,
            change_name,
        )
        self.main_page.progress_update.emit(index, total, step, steps, change_name)

    def log_skipped_image(self, directory, timestamp, image_path, reason="", full_traceback=""):
        # Deprecated: skip details are captured by batch reporting/UI signals.
        return

    def _is_cancelled(self) -> bool:
        worker = getattr(self.main_page, "current_worker", None)
        return bool(worker and worker.is_cancelled)

    def _get_batch_settings(self) -> dict[str, int]:
        try:
            return self.main_page.settings_page.get_batch_settings()
        except Exception:
            return {"batch_size": 32, "ocr_batch_size": 8}

    def _resolve_output_location(self, image_path: str) -> tuple[str, str]:
        directory = os.path.dirname(image_path)
        archive_bname = ""

        for archive in self.main_page.file_handler.archive_info:
            if image_path in archive.get("extracted_images", []):
                archive_path = archive["archive_path"]
                directory = os.path.dirname(archive_path)
                archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                break

        return directory, archive_bname

    def _current_displayed_file(self) -> str | None:
        idx = getattr(self.main_page, "curr_img_idx", -1)
        if 0 <= idx < len(self.main_page.image_files):
            return self.main_page.image_files[idx]
        return None

    def _iter_chunks(self, items: list, chunk_size: int):
        chunk_size = max(1, int(chunk_size))
        for start in range(0, len(items), chunk_size):
            yield start, items[start:start + chunk_size]

    def _build_page_context(
        self,
        index: int,
        image_path: str,
        timestamp: str,
    ) -> PreparedBatchPage:
        source_lang = self.main_page.image_states[image_path]["source_lang"]
        target_lang = self.main_page.image_states[image_path]["target_lang"]
        target_lang_en = self.main_page.lang_mapping.get(target_lang, target_lang)
        trg_lng_cd = get_language_code(target_lang_en)

        base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
        extension = os.path.splitext(image_path)[1]
        directory, archive_bname = self._resolve_output_location(image_path)

        return PreparedBatchPage(
            index=index,
            image_path=image_path,
            directory=directory,
            timestamp=timestamp,
            base_name=base_name,
            extension=extension,
            archive_bname=archive_bname,
            source_lang=source_lang,
            target_lang=target_lang,
            trg_lng_cd=trg_lng_cd,
        )

    def _ensure_block_detector(self, settings_page):
        if self.block_detection.block_detector_cache is None:
            self.block_detection.block_detector_cache = TextBlockDetector(settings_page)
        return self.block_detection.block_detector_cache

    def _cache_ocr_results_for_page(self, cache_key, page: PreparedBatchPage):
        if page.blk_list:
            self.cache_manager._cache_ocr_results(cache_key, page.blk_list)

    def _sort_page_blocks_after_ocr(self, page: PreparedBatchPage):
        self.ocr_handler.ocr.sanitize_block_texts(page.blk_list)
        source_lang_english = self.main_page.lang_mapping.get(
            page.source_lang,
            page.source_lang,
        )
        rtl = source_lang_english == "Japanese"
        page.blk_list = sort_blk_list(page.blk_list, rtl)

    def _get_ocr_cache_key_for_page(self, page: PreparedBatchPage):
        settings_page = self.main_page.settings_page
        ocr_model = settings_page.get_tool_selection("ocr")
        device = resolve_device(settings_page.is_gpu_enabled())
        return self.cache_manager._get_ocr_cache_key(
            page.image,
            page.source_lang,
            ocr_model,
            device,
        )

    def _handle_ocr_failure(self, page: PreparedBatchPage, exc: Exception):
        lowered_error = str(exc).lower()
        if "timed out" in lowered_error or "timeout" in lowered_error:
            err_msg = QCoreApplication.translate(
                "Messages",
                "OCR request timed out while waiting for the local server response.",
            )
        elif isinstance(exc, requests.exceptions.ConnectionError):
            err_msg = QCoreApplication.translate(
                "Messages",
                "Unable to connect to the server.\nPlease check your internet connection.",
            )
        elif isinstance(exc, requests.exceptions.HTTPError):
            status_code = exc.response.status_code if exc.response is not None else 500
            if status_code >= 500:
                err_msg = Messages.get_server_error_text(status_code, context="ocr")
            else:
                try:
                    err_json = exc.response.json()
                    if "detail" in err_json and isinstance(err_json["detail"], dict):
                        err_msg = err_json["detail"].get("error_description", str(exc))
                    else:
                        err_msg = err_json.get("error_description", str(exc))
                except Exception:
                    err_msg = str(exc)
        else:
            err_msg = str(exc)

        logger.exception("OCR processing failed: %s", err_msg)
        self.skip_save(
            page.directory,
            page.timestamp,
            page.base_name,
            page.extension,
            page.archive_bname,
            page.image,
        )
        self.main_page.image_skipped.emit(page.image_path, "OCR", err_msg)
        self.log_skipped_image(
            page.directory,
            page.timestamp,
            page.image_path,
            f"OCR: {err_msg}",
            traceback.format_exc(),
        )

    def _run_page_ocr_fallback(self, page: PreparedBatchPage) -> bool:
        self.ocr_handler.ocr.initialize(self.main_page, page.source_lang)
        try:
            self.ocr_handler.ocr.process(page.image, page.blk_list)
            self._cache_ocr_results_for_page(page.ocr_cache_key, page)
            self._sort_page_blocks_after_ocr(page)
            return True
        except InsufficientCreditsException:
            raise
        except Exception as exc:
            self._handle_ocr_failure(page, exc)
            return False

    def _run_block_crop_batch_ocr(
        self,
        pages: list[PreparedBatchPage],
        batch_size: int,
    ) -> list[PreparedBatchPage]:
        completed_pages: list[PreparedBatchPage] = []
        try:
            processed_blk_lists = self.ocr_handler.ocr.process_page_block_batches(
                [
                    (page.image, page.blk_list, page.source_lang)
                    for page in pages
                ],
                batch_size=batch_size,
                main_page=self.main_page,
            )
        except InsufficientCreditsException:
            raise
        except Exception:
            logger.debug(
                "Block-crop batch OCR failed for source_lang=%s, falling back to page OCR.",
                pages[0].source_lang,
                exc_info=True,
            )
            for page in pages:
                if self._run_page_ocr_fallback(page):
                    completed_pages.append(page)
            return completed_pages

        for page, blk_list in zip(pages, processed_blk_lists):
            page.blk_list = blk_list
            self._cache_ocr_results_for_page(page.ocr_cache_key, page)
            self._sort_page_blocks_after_ocr(page)
            completed_pages.append(page)

        return completed_pages

    def _run_chunk_ocr(
        self,
        prepared_pages: list[PreparedBatchPage],
        total_images: int,
    ) -> list[PreparedBatchPage]:
        ready_pages: list[PreparedBatchPage] = []
        pending_by_source: dict[str, list[PreparedBatchPage]] = {}

        for page in prepared_pages:
            self.emit_progress(page.index, total_images, 2, 10, False)
            if self._is_cancelled():
                return ready_pages

            page.ocr_cache_key = self._get_ocr_cache_key_for_page(page)
            if self.cache_manager._can_serve_all_blocks_from_ocr_cache(page.ocr_cache_key, page.blk_list):
                self.cache_manager._apply_cached_ocr_to_blocks(page.ocr_cache_key, page.blk_list)
                self._sort_page_blocks_after_ocr(page)
                ready_pages.append(page)
                continue

            pending_by_source.setdefault(page.source_lang, []).append(page)

        ocr_batch_size = self._get_batch_settings()["ocr_batch_size"]
        for source_lang in pending_by_source:
            if self._is_cancelled():
                return ready_pages
            ready_pages.extend(
                self._run_block_crop_batch_ocr(
                    pending_by_source[source_lang],
                    batch_size=ocr_batch_size,
                )
            )

        ready_pages.sort(key=lambda item: item.index)
        return ready_pages

    def _load_page(
        self,
        page: PreparedBatchPage,
        total_images: int,
    ) -> PreparedBatchPage | None:
        self.emit_progress(page.index, total_images, 0, 10, True)
        ensure_path_materialized(page.image_path)
        page.image = imk.read_image(page.image_path)

        state = self.main_page.image_states.get(page.image_path, {})
        if state.get("skip", False):
            self.skip_save(
                page.directory,
                page.timestamp,
                page.base_name,
                page.extension,
                page.archive_bname,
                page.image,
            )
            self.log_skipped_image(
                page.directory,
                page.timestamp,
                page.image_path,
                "User-skipped",
            )
            return None

        return page

    def _reload_page_image(self, page: PreparedBatchPage):
        ensure_path_materialized(page.image_path)
        page.image = imk.read_image(page.image_path)
        return page

    def _run_chunk_detection(
        self,
        pages: list[PreparedBatchPage],
        total_images: int,
    ) -> list[PreparedBatchPage]:
        if not pages:
            return []

        settings_page = self.main_page.settings_page
        detector = self._ensure_block_detector(settings_page)
        detected_pages: list[PreparedBatchPage] = []

        for page in pages:
            self.emit_progress(page.index, total_images, 1, 10, False)
            if self._is_cancelled():
                return detected_pages

        try:
            detected_blk_lists = detector.detect_many([page.image for page in pages])
            if len(detected_blk_lists) != len(pages):
                raise RuntimeError(
                    f"Detection engine returned {len(detected_blk_lists)} results for {len(pages)} pages."
                )
        except Exception:
            logger.debug(
                "Chunk detection failed; falling back to per-page detection.",
                exc_info=True,
            )
            detected_blk_lists = [detector.detect(page.image) for page in pages]

        for page, blk_list in zip(pages, detected_blk_lists):
            if self._is_cancelled():
                return detected_pages

            page.blk_list = blk_list
            if not page.blk_list:
                self.skip_save(
                    page.directory,
                    page.timestamp,
                    page.base_name,
                    page.extension,
                    page.archive_bname,
                    page.image,
                )
                self.main_page.image_skipped.emit(page.image_path, "Text Blocks", "")
                self.log_skipped_image(
                    page.directory,
                    page.timestamp,
                    page.image_path,
                    "No text blocks detected",
                )
                continue

            detected_pages.append(page)

        return detected_pages

    def _prepare_page_after_ocr(
        self,
        page: PreparedBatchPage,
        total_images: int,
        export_settings: dict,
    ) -> PreparedBatchPage | None:
        self.emit_progress(page.index, total_images, 3, 10, False)
        if self._is_cancelled():
            return None

        if page.image is None:
            self._reload_page_image(page)
        if page.image is None:
            err_msg = "Failed to reload the page image before mask generation."
            logger.warning("%s image=%s", err_msg, page.image_path)
            self.skip_save(
                page.directory,
                page.timestamp,
                page.base_name,
                page.extension,
                page.archive_bname,
                page.image,
            )
            self.main_page.image_skipped.emit(page.image_path, "Generate Mask", err_msg)
            return None

        page.mask = generate_mask(page.image, page.blk_list)

        self.emit_progress(page.index, total_images, 4, 10, False)
        if self._is_cancelled():
            return None

        return page

    def _finalize_page_after_inpainting(
        self,
        page: PreparedBatchPage,
        total_images: int,
        export_settings: dict,
    ) -> PreparedBatchPage | None:
        page.inpaint_input_img = imk.convert_scale_abs(page.inpaint_input_img)

        patches = self.inpainting.get_inpainted_patches(page.mask, page.inpaint_input_img)
        self.main_page.patches_processed.emit(patches, page.image_path)

        if export_settings["export_inpainted_image"]:
            path = os.path.join(
                page.directory,
                f"comic_translate_{page.timestamp}",
                "cleaned_images",
                page.archive_bname,
            )
            os.makedirs(path, exist_ok=True)
            imk.write_image(
                os.path.join(path, f"{page.base_name}_cleaned{page.extension}"),
                page.inpaint_input_img,
            )

        self.emit_progress(page.index, total_images, 5, 10, False)
        if self._is_cancelled():
            return None

        page.mask = None
        return page

    def _run_chunk_inpainting(
        self,
        pages: list[PreparedBatchPage],
        total_images: int,
        export_settings: dict,
    ) -> list[PreparedBatchPage]:
        if not pages:
            return []

        settings_page = self.main_page.settings_page
        config = get_config(settings_page)
        inpaint_batch_size = 1
        prepared_pages: list[PreparedBatchPage] = []

        for page in pages:
            prepared_page = self._prepare_page_after_ocr(page, total_images, export_settings)
            if self._is_cancelled():
                return prepared_pages
            if prepared_page is not None:
                prepared_pages.append(prepared_page)

        if not prepared_pages:
            return []

        finalized_pages: list[PreparedBatchPage] = []
        if self.inpainting.supports_image_batching(config):
            grouped_pages: dict[tuple[tuple[int, ...], tuple[int, ...]], list[PreparedBatchPage]] = {}
            for page in prepared_pages:
                if page.image is None:
                    self._reload_page_image(page)
                image_shape = tuple(page.image.shape)
                mask_shape = tuple(page.mask.shape)
                grouped_pages.setdefault((image_shape, mask_shape), []).append(page)

            for group_pages in grouped_pages.values():
                if self._is_cancelled():
                    return finalized_pages

                inpainted_images = self.inpainting.inpaint_many(
                    [page.image for page in group_pages],
                    [page.mask for page in group_pages],
                    config,
                    batch_size=min(inpaint_batch_size, len(group_pages)),
                )
                for page, inpainted_image in zip(group_pages, inpainted_images):
                    page.inpaint_input_img = inpainted_image
                    finalized_page = self._finalize_page_after_inpainting(
                        page,
                        total_images,
                        export_settings,
                    )
                    if finalized_page is not None:
                        finalized_pages.append(finalized_page)
        else:
            inpainter = self.inpainting._ensure_inpainter()
            for page in prepared_pages:
                if self._is_cancelled():
                    return finalized_pages
                page.inpaint_input_img = inpainter(page.image, page.mask, config)
                finalized_page = self._finalize_page_after_inpainting(
                    page,
                    total_images,
                    export_settings,
                )
                if finalized_page is not None:
                    finalized_pages.append(finalized_page)

        finalized_pages.sort(key=lambda item: item.index)
        return finalized_pages

    def _translate_one_page_worker(self, page: PreparedBatchPage):
        settings_page = self.main_page.settings_page
        extra_context = settings_page.get_llm_settings()["extra_context"]
        translator = Translator(self.main_page, page.source_lang, page.target_lang)
        sanitize_translation_source_blocks(page.blk_list)
        translated_blk_list = translator.translate(
            page.blk_list,
            page.image,
            extra_context,
        )
        usage = getattr(translator.engine, "last_usage", None)
        return translated_blk_list, usage

    def _translate_prepared_pages(
        self,
        prepared_pages: list[PreparedBatchPage],
        total_images: int,
    ):
        if not prepared_pages:
            return

        future_to_page = {}
        max_workers = min(32, len(prepared_pages))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for page in prepared_pages:
                future = executor.submit(self._translate_one_page_worker, page)
                future_to_page[future] = page

            for future in as_completed(future_to_page):
                if self._is_cancelled():
                    return

                page = future_to_page[future]

                try:
                    translated_blk_list, usage = future.result()
                    page.blk_list = translated_blk_list
                    self.emit_progress(page.index, total_images, 7, 10, False)

                    if usage:
                        logger.debug(
                            "TOKENS | prompt=%s completion=%s total=%s | image=%s",
                            usage.get("prompt_tokens"),
                            usage.get("completion_tokens"),
                            usage.get("total_tokens"),
                            page.image_path,
                        )

                    self.cache_manager._cache_translation_results(
                        page.translation_cache_key,
                        page.blk_list,
                    )
                except InsufficientCreditsException:
                    raise
                except Exception as exc:
                    err_msg = str(exc)
                    logger.exception("Translation failed for %s: %s", page.image_path, err_msg)
                    self.skip_save(
                        page.directory,
                        page.timestamp,
                        page.base_name,
                        page.extension,
                        page.archive_bname,
                        page.image,
                    )
                    self.main_page.image_skipped.emit(page.image_path, "Translator", err_msg)
                    page.translation_failed = True

    def _write_text_exports(
        self,
        page: PreparedBatchPage,
        export_settings: dict,
        entire_raw_text: str,
        entire_translated_text: str,
    ):
        if export_settings["export_raw_text"]:
            path = os.path.join(
                page.directory,
                f"comic_translate_{page.timestamp}",
                "raw_texts",
                page.archive_bname,
            )
            os.makedirs(path, exist_ok=True)
            with open(
                os.path.join(path, f"{page.base_name}_raw.json"),
                "w",
                encoding="utf-8",
            ) as file:
                file.write(entire_raw_text)

        if export_settings["export_translated_text"]:
            path = os.path.join(
                page.directory,
                f"comic_translate_{page.timestamp}",
                "translated_texts",
                page.archive_bname,
            )
            os.makedirs(path, exist_ok=True)
            with open(
                os.path.join(path, f"{page.base_name}_translated.json"),
                "w",
                encoding="utf-8",
            ) as file:
                file.write(entire_translated_text)

    def _validate_translation_payloads(
        self,
        page: PreparedBatchPage,
    ) -> tuple[str, str] | None:
        entire_raw_text = get_raw_text(page.blk_list)
        entire_translated_text = get_raw_translation(page.blk_list)

        try:
            raw_text_obj = json.loads(entire_raw_text)
            translated_text_obj = json.loads(entire_translated_text)
            if (not raw_text_obj) or (not translated_text_obj):
                self.skip_save(
                    page.directory,
                    page.timestamp,
                    page.base_name,
                    page.extension,
                    page.archive_bname,
                    page.image,
                )
                self.main_page.image_skipped.emit(page.image_path, "Translator", "")
                self.log_skipped_image(
                    page.directory,
                    page.timestamp,
                    page.image_path,
                    "Translator: empty JSON",
                )
                return None
        except json.JSONDecodeError as exc:
            error_message = str(exc)
            self.skip_save(
                page.directory,
                page.timestamp,
                page.base_name,
                page.extension,
                page.archive_bname,
                page.image,
            )
            self.main_page.image_skipped.emit(page.image_path, "Translator", error_message)
            self.log_skipped_image(
                page.directory,
                page.timestamp,
                page.image_path,
                f"Translator: JSONDecodeError: {error_message}",
                traceback.format_exc(),
            )
            return None

        return entire_raw_text, entire_translated_text

    def _render_page(self, page: PreparedBatchPage):
        render_settings = self.main_page.render_settings()
        upper_case = render_settings.upper_case
        outline = render_settings.outline

        format_translations(page.blk_list, page.trg_lng_cd, upper_case=upper_case)
        get_best_render_area(page.blk_list, page.image, page.inpaint_input_img)

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
        file_on_display = self._current_displayed_file()

        text_items_state = []
        for blk in page.blk_list:
            x1, y1, block_width, block_height = blk.xywh
            translation = blk.translation
            if not translation or len(translation) == 1:
                continue

            vertical = is_vertical_block(blk, page.trg_lng_cd)
            translation, font_size, rendered_width, rendered_height = pyside_word_wrap(
                translation,
                font,
                block_width,
                block_height,
                line_spacing,
                outline_width,
                bold,
                italic,
                underline,
                alignment,
                direction,
                max_font_size,
                min_font_size,
                vertical,
                return_metrics=True,
            )

            if page.image_path == file_on_display:
                self.main_page.blk_rendered.emit(translation, font_size, blk, page.image_path)

            if is_no_space_lang(page.trg_lng_cd):
                translation = translation.replace(" ", "")

            font_color = get_smart_text_color(blk.font_color, setting_font_color)
            text_props = TextItemProperties(
                text=translation,
                font_family=font,
                font_size=font_size,
                text_color=font_color,
                alignment=alignment,
                line_spacing=line_spacing,
                outline_color=outline_color,
                outline_width=outline_width,
                bold=bold,
                italic=italic,
                underline=underline,
                position=(x1, y1),
                rotation=blk.angle,
                scale=1.0,
                transform_origin=blk.tr_origin_point,
                width=rendered_width,
                height=rendered_height,
                direction=direction,
                vertical=vertical,
                selection_outlines=[
                    OutlineInfo(
                        0,
                        len(translation),
                        outline_color,
                        outline_width,
                        OutlineType.Full_Document,
                    )
                ]
                if outline
                else [],
            )
            text_items_state.append(text_props.to_dict())

        viewer_state = self.main_page.image_states[page.image_path]["viewer_state"]
        viewer_state.update(
            {
                "text_items_state": text_items_state,
                "push_to_stack": True,
            }
        )

    def _finalize_prepared_page(
        self,
        page: PreparedBatchPage,
        total_images: int,
        export_settings: dict,
    ) -> bool:
        payloads = self._validate_translation_payloads(page)
        if payloads is None:
            return True

        entire_raw_text, entire_translated_text = payloads
        self._write_text_exports(page, export_settings, entire_raw_text, entire_translated_text)

        self._render_page(page)

        self.emit_progress(page.index, total_images, 9, 10, False)
        if self._is_cancelled():
            return False

        self.main_page.image_states[page.image_path].update({"blk_list": page.blk_list})
        self.main_page.render_state_ready.emit(page.image_path)

        if page.image_path == self._current_displayed_file():
            self.main_page.blk_list = page.blk_list

        self.emit_progress(page.index, total_images, 10, 10, False)
        return True

    def _release_page_buffers(self, page: PreparedBatchPage, release_blk_list: bool = False):
        page.image = None
        page.mask = None
        page.inpaint_input_img = None
        if release_blk_list:
            page.blk_list = None
            page.ocr_cache_key = None
            page.translation_cache_key = None

    def _trim_runtime_memory(self):
        try:
            gc.collect()
        except Exception:
            logger.debug("Failed to collect Python garbage.", exc_info=True)

        try:
            import torch

            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()

            xpu = getattr(torch, "xpu", None)
            if xpu is not None and hasattr(xpu, "is_available") and xpu.is_available():
                empty_cache = getattr(xpu, "empty_cache", None)
                if callable(empty_cache):
                    empty_cache()
        except Exception:
            logger.debug("Failed to trim accelerator runtime memory.", exc_info=True)

    def _release_detection_model_caches(self):
        self.block_detection.block_detector_cache = None

        try:
            from modules.detection.factory import DetectionEngineFactory

            DetectionEngineFactory._engines.clear()
        except Exception:
            logger.debug("Failed to clear detection engine cache.", exc_info=True)

        try:
            from modules.detection.font.engine import FontEngineFactory

            FontEngineFactory._engines.clear()
        except Exception:
            logger.debug("Failed to clear font engine cache.", exc_info=True)

    def _release_ocr_model_caches(self):
        try:
            from modules.ocr.factory import OCRFactory

            OCRFactory._engines.clear()
        except Exception:
            logger.debug("Failed to clear OCR engine cache.", exc_info=True)

    def _release_inpainting_model_caches(self):
        self.inpainting.inpainter_cache = None
        self.inpainting.cached_inpainter_key = None

    def _release_translation_model_caches(self):
        try:
            from modules.translation.factory import TranslationFactory

            TranslationFactory._engines.clear()
        except Exception:
            logger.debug("Failed to clear translation engine cache.", exc_info=True)

    def _release_non_translation_model_caches(self):
        self._release_detection_model_caches()
        self._release_ocr_model_caches()
        self._release_inpainting_model_caches()

    def _release_all_model_caches(self):
        self._release_non_translation_model_caches()
        self._release_translation_model_caches()

    def _translate_queue(
        self,
        translation_queue: list[PreparedBatchPage],
        total_images: int,
    ) -> list[PreparedBatchPage]:
        if not translation_queue:
            return []

        self._translate_prepared_pages(translation_queue, total_images)
        completed_pages: list[PreparedBatchPage] = []
        for page in sorted(translation_queue, key=lambda item: item.index):
            self._release_page_buffers(page)
            if not page.translation_failed:
                completed_pages.append(page)

        translation_queue.clear()
        return completed_pages

    def batch_process(self, selected_paths: List[str] = None):
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        image_list = list(selected_paths if selected_paths is not None else self.main_page.image_files)
        total_images = len(image_list)
        if total_images == 0:
            return

        settings_page = self.main_page.settings_page
        export_settings = settings_page.get_export_settings()
        page_batch_size = max(1, self._get_batch_settings()["batch_size"])
        detection_batch_size = 1
        extra_context = settings_page.get_llm_settings()["extra_context"]
        translator_key = settings_page.get_tool_selection("translator")

        try:
            if self.main_page.file_handler.should_pre_materialize(image_list):
                count = self.main_page.file_handler.pre_materialize(image_list)
                logger.info(
                    "Batch pre-materialized %d paths before full-run processing.",
                    count,
                )
        except Exception:
            logger.debug("Batch pre-materialization failed; continuing lazily.", exc_info=True)

        pages = [
            self._build_page_context(page_index, image_path, timestamp)
            for page_index, image_path in enumerate(image_list)
        ]
        detected_pages: list[PreparedBatchPage] = []
        pending_detection_pages: list[PreparedBatchPage] = []

        for page in pages:
            if self._is_cancelled():
                return

            loaded_page = self._load_page(page, total_images)
            if self._is_cancelled():
                return
            if loaded_page is None:
                continue

            pending_detection_pages.append(loaded_page)
            if len(pending_detection_pages) < detection_batch_size:
                continue

            stage_pages = self._run_chunk_detection(pending_detection_pages, total_images)
            for buffered_page in pending_detection_pages:
                self._release_page_buffers(buffered_page)
            if stage_pages:
                detected_pages.extend(stage_pages)
            pending_detection_pages = []

        if pending_detection_pages:
            stage_pages = self._run_chunk_detection(pending_detection_pages, total_images)
            for buffered_page in pending_detection_pages:
                self._release_page_buffers(buffered_page)
            if stage_pages:
                detected_pages.extend(stage_pages)

        self._release_detection_model_caches()
        self._trim_runtime_memory()
        if self._is_cancelled():
            return

        ocr_ready_pages: list[PreparedBatchPage] = []
        for _chunk_start, page_chunk in self._iter_chunks(detected_pages, page_batch_size):
            if self._is_cancelled():
                return

            for page in page_chunk:
                self._reload_page_image(page)

            stage_pages = self._run_chunk_ocr(page_chunk, total_images)

            for page in page_chunk:
                self._release_page_buffers(page)

            if stage_pages:
                ocr_ready_pages.extend(stage_pages)

        detected_pages.clear()
        self._release_ocr_model_caches()
        self._trim_runtime_memory()
        if self._is_cancelled():
            return

        translated_pages: list[PreparedBatchPage] = []
        translation_queue: list[PreparedBatchPage] = []

        for page in ocr_ready_pages:
            if self._is_cancelled():
                return

            self._reload_page_image(page)
            sanitize_translation_source_blocks(page.blk_list)
            page.translation_cache_key = self.cache_manager._get_translation_cache_key(
                page.image,
                page.source_lang,
                page.target_lang,
                translator_key,
                extra_context,
            )
            if self.cache_manager._can_serve_all_blocks_from_translation_cache(
                page.translation_cache_key,
                page.blk_list,
            ):
                self.cache_manager._apply_cached_translations_to_blocks(
                    page.translation_cache_key,
                    page.blk_list,
                )
                self.emit_progress(page.index, total_images, 7, 10, False)
                self._release_page_buffers(page)
                translated_pages.append(page)
                continue

            translation_queue.append(page)
            if len(translation_queue) >= page_batch_size:
                translated_pages.extend(
                    self._translate_queue(
                        translation_queue,
                        total_images,
                    )
                )
                if self._is_cancelled():
                    return

        translated_pages.extend(
            self._translate_queue(
                translation_queue,
                total_images,
            )
        )
        ocr_ready_pages.clear()
        if self._is_cancelled():
            return

        self._release_translation_model_caches()
        self._trim_runtime_memory()
        finalized_pages = self._run_chunk_inpainting(
            translated_pages,
            total_images,
            export_settings,
        )
        translated_pages.clear()
        self._trim_runtime_memory()
        if self._is_cancelled():
            return

        for page in finalized_pages:
            if not self._finalize_prepared_page(
                page,
                total_images,
                export_settings,
            ):
                return

            self._release_page_buffers(page, release_blk_list=True)

        finalized_pages.clear()
        self._release_inpainting_model_caches()
        self._trim_runtime_memory()
