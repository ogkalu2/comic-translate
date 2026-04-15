from __future__ import annotations

import json
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import imkit as imk
import requests
from PySide6.QtCore import QCoreApplication

from app.path_materialization import ensure_path_materialized
from app.ui.messages import Messages
from modules.detection.utils.orientation import infer_orientation, infer_reading_order
from modules.translation.processor import Translator
from modules.utils.device import resolve_device
from modules.utils.exceptions import InsufficientCreditsException
from modules.utils.pipeline_config import get_config
from modules.utils.textblock import sort_blk_list
from modules.utils.translator_utils import sanitize_translation_source_blocks

logger = logging.getLogger(__name__)


class BatchExecutionMixin:
    @staticmethod
    def _is_recoverable_translation_error(exc: Exception) -> bool:
        if isinstance(exc, (json.JSONDecodeError, ValueError)):
            return True

        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "unterminated string",
                "invalid result format",
                "length mismatch",
                "json decode",
                "malformed json",
                "truncated json",
            )
        )

    @staticmethod
    def _merge_usage_stats(usage_items: list[dict | None]) -> dict | None:
        totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        has_usage = False
        for usage in usage_items:
            if not isinstance(usage, dict):
                continue
            has_usage = True
            for key in totals:
                try:
                    totals[key] += int(usage.get(key, 0) or 0)
                except Exception:
                    continue
        return totals if has_usage else None

    def _translate_blocks_resiliently(
        self,
        page: PreparedBatchPage,
        blocks_to_translate: list,
        extra_context: str,
    ):
        translator = Translator(self.main_page, "", page.target_lang)
        sanitize_translation_source_blocks(blocks_to_translate)
        try:
            translated_blk_list = translator.translate(
                blocks_to_translate,
                page.image,
                extra_context,
            )
            usage = getattr(translator.engine, "last_usage", None)
            return translated_blk_list, usage
        except InsufficientCreditsException:
            raise
        except Exception as exc:
            if len(blocks_to_translate) <= 1 or not self._is_recoverable_translation_error(exc):
                raise

            logger.warning(
                "Translation batch failed for %s on %d blocks; retrying with smaller chunks: %s",
                page.image_path,
                len(blocks_to_translate),
                exc,
            )
            midpoint = max(1, len(blocks_to_translate) // 2)
            usage_items = []
            for block_chunk in (blocks_to_translate[:midpoint], blocks_to_translate[midpoint:]):
                if not block_chunk:
                    continue
                _translated_chunk, chunk_usage = self._translate_blocks_resiliently(
                    page,
                    block_chunk,
                    extra_context,
                )
                usage_items.append(chunk_usage)
            return blocks_to_translate, self._merge_usage_stats(usage_items)

    def _load_page_state_into_blk_list(self, page: PreparedBatchPage):
        ensure_path_materialized(page.image_path)
        if page.image is None:
            page.image = imk.read_image(page.image_path)

        state = self.main_page.image_states.get(page.image_path, {})
        saved_blk_list = state.get("blk_list")
        if saved_blk_list is not None and len(saved_blk_list) > 0:
            page.blk_list = [blk for blk in saved_blk_list]
            logger.info(
                "Loaded saved blk_list for %s (%d blocks)",
                page.image_path,
                len(page.blk_list),
            )

    def _cache_ocr_results_for_page(self, cache_key, page_or_blocks):
        blk_list = page_or_blocks.blk_list if hasattr(page_or_blocks, "blk_list") else page_or_blocks
        if blk_list:
            self.cache_manager._cache_ocr_results(cache_key, blk_list)

    def _sort_page_blocks_after_ocr(self, page: PreparedBatchPage):
        self.ocr_handler.ocr.sanitize_block_texts(page.blk_list)
        orientation = infer_orientation([blk.xyxy for blk in page.blk_list]) if page.blk_list else "horizontal"
        rtl = infer_reading_order(orientation) == "rtl"
        page.blk_list = sort_blk_list(page.blk_list, rtl)

    def _get_ocr_cache_key_for_page(self, page: PreparedBatchPage):
        settings_page = self.main_page.settings_page
        ocr_model = settings_page.get_tool_selection("ocr")
        device = resolve_device(settings_page.is_gpu_enabled())
        return self.cache_manager._get_ocr_cache_key(page.image, "", ocr_model, device)

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
        self.ocr_handler.ocr.initialize(self.main_page, "")
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
        page_blocks_to_process = [
            getattr(page, "_ocr_missing_blocks", page.blk_list)
            for page in pages
        ]
        try:
            processed_blk_lists = self.ocr_handler.ocr.process_page_block_batches(
                [(page.image, missing_blocks, "") for page, missing_blocks in zip(pages, page_blocks_to_process)],
                batch_size=batch_size,
                main_page=self.main_page,
            )
        except InsufficientCreditsException:
            raise
        except Exception:
            logger.debug("Block-crop batch OCR failed, falling back to page OCR.", exc_info=True)
            for page in pages:
                if self._run_page_ocr_fallback(page):
                    completed_pages.append(page)
            return completed_pages

        for page, blk_list, missing_blocks in zip(pages, processed_blk_lists, page_blocks_to_process):
            self._cache_ocr_results_for_page(page.ocr_cache_key, missing_blocks)
            self._sort_page_blocks_after_ocr(page)
            completed_pages.append(page)

        return completed_pages

    def _run_chunk_ocr(
        self,
        prepared_pages: list[PreparedBatchPage],
        total_images: int,
    ) -> list[PreparedBatchPage]:
        ready_pages: list[PreparedBatchPage] = []
        pending_pages: list[PreparedBatchPage] = []

        for page in prepared_pages:
            self.emit_progress(page.index, total_images, 2, 10, False)
            if self._is_cancelled():
                return ready_pages

            page.ocr_cache_key = self._get_ocr_cache_key_for_page(page)
            self.cache_manager._apply_cached_ocr_to_blocks(page.ocr_cache_key, page.blk_list)
            missing_blocks = self.cache_manager._get_missing_ocr_blocks(page.ocr_cache_key, page.blk_list)
            if not missing_blocks:
                self._sort_page_blocks_after_ocr(page)
                ready_pages.append(page)
                continue

            page._ocr_missing_blocks = missing_blocks
            pending_pages.append(page)

        ocr_batch_size = self._get_batch_settings()["ocr_batch_size"]
        if pending_pages and not self._is_cancelled():
            ready_pages.extend(
                self._run_block_crop_batch_ocr(
                    pending_pages,
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
            logger.debug("Chunk detection failed; falling back to per-page detection.", exc_info=True)
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

        page.mask = self.inpainting.build_mask_from_blocks(page.image, page.blk_list)

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
        blocks_to_translate = getattr(page, "_translation_missing_blocks", page.blk_list)
        sanitize_translation_source_blocks(page.blk_list)
        translated_blk_list, usage = self._translate_blocks_resiliently(
            page,
            blocks_to_translate,
            extra_context,
        )
        return translated_blk_list, blocks_to_translate, usage

    def _merge_translated_blocks(
        self,
        page: PreparedBatchPage,
        original_blocks: list,
        translated_blocks: list,
    ) -> None:
        if not original_blocks:
            if translated_blocks is not None:
                page.blk_list = translated_blocks
            return

        if original_blocks is page.blk_list:
            if translated_blocks is not None:
                page.blk_list = translated_blocks
            return

        for original_blk, translated_blk in zip(original_blocks, translated_blocks or []):
            if translated_blk is original_blk:
                continue
            for attr in ("translation", "text", "source_lang"):
                if hasattr(translated_blk, attr):
                    setattr(original_blk, attr, getattr(translated_blk, attr))

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
                    translated_blk_list, translated_source_blocks, usage = future.result()
                    self._merge_translated_blocks(
                        page,
                        translated_source_blocks,
                        translated_blk_list,
                    )
                    self.emit_progress(page.index, total_images, 7, 10, False)

                    if usage:
                        logger.debug(
                            "TOKENS | prompt=%s completion=%s total=%s | image=%s",
                            usage.get("prompt_tokens"),
                            usage.get("completion_tokens"),
                            usage.get("total_tokens"),
                            page.image_path,
                        )

                    translation_blocks = getattr(page, "_translation_missing_blocks", page.blk_list)
                    self.cache_manager._cache_translation_results(
                        page.translation_cache_key,
                        translation_blocks,
                        translated_blk_list,
                    )
                    if hasattr(page, "_translation_missing_blocks"):
                        delattr(page, "_translation_missing_blocks")
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

    def _release_page_buffers(self, page: PreparedBatchPage, release_blk_list: bool = False):
        page.image = None
        page.mask = None
        page.inpaint_input_img = None
        if release_blk_list:
            page.blk_list = None
            page.ocr_cache_key = None
            page.translation_cache_key = None

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
