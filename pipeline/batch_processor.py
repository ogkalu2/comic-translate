from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List

from modules.utils.translator_utils import sanitize_translation_source_blocks

from .batch_execution_mixin import BatchExecutionMixin
from .batch_render_mixin import BatchRenderMixin
from .batch_state_mixin import BatchStateMixin
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
    target_lang: str = ""
    trg_lng_cd: str = ""
    image: object | None = None
    blk_list: list | None = None
    mask: object | None = None
    inpaint_input_img: object | None = None
    ocr_cache_key: object | None = None
    translation_cache_key: object | None = None
    translation_failed: bool = False
    skip_full_pipeline: bool = False
    skip_inpaint: bool = False


class BatchProcessor(BatchExecutionMixin, BatchRenderMixin, BatchStateMixin):
    PreparedBatchPage = PreparedBatchPage

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

    def batch_process(self, selected_paths: List[str] = None):
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        image_list = list(selected_paths if selected_paths is not None else self.main_page.image_files)
        total_images = len(image_list)
        if total_images == 0:
            return

        settings_page = self.main_page.settings_page
        export_settings = settings_page.get_export_settings()
        page_batch_size = max(64, self._get_batch_settings()["batch_size"])
        detection_batch_size = 64
        extra_context = settings_page.get_llm_settings()["extra_context"]
        translator_key = settings_page.get_tool_selection("translator")
        ordered_context = self._translation_context_requires_ordering()

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

        fully_done_pages: list[PreparedBatchPage] = []
        skip_detection_pages: list[PreparedBatchPage] = []
        fresh_pages: list[PreparedBatchPage] = []

        for page in pages:
            if self._is_cancelled():
                return

            loaded_page = self._load_page(page, total_images)
            if loaded_page is None:
                continue

            ps = self._get_pipeline_state(loaded_page.image_path)
            logger.info(
                "Page %s pipeline_state: completed=%s trg=%s",
                loaded_page.image_path,
                ps.get("completed_stages"),
                ps.get("target_lang"),
            )

            if self._page_is_fully_done(loaded_page, translator_key, extra_context):
                fully_done_pages.append(loaded_page)
                logger.info(
                    "Page already fully translated, skipping reprocessing: %s",
                    loaded_page.image_path,
                )
            elif self._page_can_skip_detection(loaded_page):
                skip_detection_pages.append(loaded_page)
                logger.info(
                    "Reusing cached blocks, skipping detection: %s",
                    loaded_page.image_path,
                )
            else:
                fresh_pages.append(loaded_page)

        detected_pages: list[PreparedBatchPage] = []
        pending_detection_pages: list[PreparedBatchPage] = []

        for page in fresh_pages:
            if self._is_cancelled():
                return

            pending_detection_pages.append(page)
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

        translated_pages: list[PreparedBatchPage] = []
        translation_queue: list[PreparedBatchPage] = []

        for page in fully_done_pages:
            if self._is_cancelled():
                return
            self.emit_progress(page.index, total_images, 0, 10, True)
            self._load_page_state_into_blk_list(page)
            tc_key = self._build_page_translation_cache_key(page)
            page.translation_cache_key = tc_key
            self.cache_manager._apply_cached_translations_to_blocks(tc_key, page.blk_list)
            page.inpaint_input_img = self._restore_cached_inpaint_image(page)
            page.skip_full_pipeline = True
            page.skip_inpaint = True
            translated_pages.append(page)
            self.emit_progress(page.index, total_images, 10, 10, False)
            logger.info(
                "Fully done page rendered without reprocessing: %s",
                page.image_path,
            )

        for page in skip_detection_pages:
            if self._is_cancelled():
                return
            self._load_page_state_into_blk_list(page)
        skip_detection_pages = self._run_chunk_ocr(skip_detection_pages, total_images)

        self._release_ocr_model_caches()
        self._trim_runtime_memory()
        if self._is_cancelled():
            return

        ocr_ready_pages.extend(skip_detection_pages)
        skip_detection_pages.clear()
        fully_done_pages.clear()

        for page in ocr_ready_pages:
            if self._is_cancelled():
                return

            self._reload_page_image(page)
            page.skip_inpaint = self._page_can_skip_inpainting(page)
            if page.skip_inpaint:
                logger.info("Reusing cached inpaint layer for %s", page.image_path)
                page.inpaint_input_img = self._restore_cached_inpaint_image(page)

            sanitize_translation_source_blocks(page.blk_list)

            if not ordered_context:
                page.translation_cache_key = self._build_page_translation_cache_key(page)
                self.cache_manager._apply_cached_translations_to_blocks(
                    page.translation_cache_key,
                    page.blk_list,
                )
                missing_blocks = self.cache_manager._get_missing_translation_blocks(
                    page.translation_cache_key,
                    page.blk_list,
                )
                if not missing_blocks:
                    self.emit_progress(page.index, total_images, 7, 10, False)
                    self._release_page_buffers(page)
                    translated_pages.append(page)
                    continue

                page._translation_missing_blocks = missing_blocks

            translation_queue.append(page)
            if len(translation_queue) >= page_batch_size:
                translated_pages.extend(self._translate_queue(translation_queue, total_images))
                if self._is_cancelled():
                    return

        translated_pages.extend(self._translate_queue(translation_queue, total_images))
        ocr_ready_pages.clear()
        if self._is_cancelled():
            return

        self._release_translation_model_caches()
        self._trim_runtime_memory()

        pages_needing_inpaint = [p for p in translated_pages if getattr(p, "skip_inpaint", False) is False]
        fully_done_rendered = [p for p in translated_pages if getattr(p, "skip_inpaint", False) is True]

        finalized_pages = self._run_chunk_inpainting(
            pages_needing_inpaint,
            total_images,
            export_settings,
        )
        pages_needing_inpaint.clear()
        self._trim_runtime_memory()
        if self._is_cancelled():
            return

        for page in finalized_pages:
            if not self._finalize_prepared_page(
                page,
                total_images,
                export_settings,
                translator_key,
                extra_context,
            ):
                return
            self._release_page_buffers(page, release_blk_list=True)

        finalized_pages.clear()

        for page in fully_done_rendered:
            if not self._finalize_prepared_page(
                page,
                total_images,
                export_settings,
                translator_key,
                extra_context,
            ):
                return
            self._release_page_buffers(page, release_blk_list=True)

        fully_done_rendered.clear()

        self._release_inpainting_model_caches()
        self._trim_runtime_memory()
