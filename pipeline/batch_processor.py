from __future__ import annotations

import copy
import gc
import hashlib
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
    is_vertical_block,
    pyside_word_wrap,
    resolve_init_font_size,
)
from modules.translation.processor import Translator
from modules.utils.device import resolve_device
from modules.utils.exceptions import InsufficientCreditsException
from modules.utils.image_utils import get_smart_text_color
from modules.detection.utils.orientation import infer_orientation, infer_reading_order
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
from .render_state import build_render_template_map, get_target_snapshot, set_target_snapshot
from .stage_state import (
    activate_target_lang,
    ensure_pipeline_state,
    finalize_render_stage,
    is_stage_available,
    mark_clean_ready,
    mark_ocr_ready,
    set_current_stage,
    set_page_stage_validity,
)

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
    skip_full_pipeline: bool = False  # Page is fully done for the active target
    skip_inpaint: bool = False  # Cached inpaint layer is already available for this page


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
            target_lang=target_lang,
            trg_lng_cd=trg_lng_cd,
        )

    def _ensure_block_detector(self, settings_page):
        if self.block_detection.block_detector_cache is None:
            self.block_detection.block_detector_cache = TextBlockDetector(settings_page)
        return self.block_detection.block_detector_cache

    def _get_pipeline_state(self, image_path: str) -> dict:
        """Get the pipeline_state dict for an image, ensuring it exists."""
        state = self.main_page.image_states.setdefault(image_path, {})
        ps, _ = activate_target_lang(
            state,
            self.main_page.t_combo.currentText(),
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main_page.image_patches.get(image_path)
            ),
        )
        return ps

    def _has_stages_completed(self, stages: set, pipeline_state: dict) -> bool:
        """Check if all specified stages have been completed for a page."""
        completed = set(pipeline_state.get("completed_stages", []))
        return stages.issubset(completed)

    def _page_is_fully_done(self, page: PreparedBatchPage, translator_key: str, extra_context: str) -> bool:
        """Check if a page has been fully processed with the same settings and needs zero re-running."""
        ps = self._get_pipeline_state(page.image_path)
        state = self.main_page.image_states.get(page.image_path, {})
        has_runtime_patches = bool(
            state.get("inpaint_cache") or self.main_page.image_patches.get(page.image_path)
        )
        if not (
            is_stage_available(state, "detect", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
            and is_stage_available(state, "ocr", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
            and is_stage_available(state, "translate", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
            and is_stage_available(state, "render", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
        ):
            logger.debug(f"_page_is_fully_done: stage validity incomplete for {page.image_path}")
            return False
        if ps.get("target_lang") != page.target_lang:
            logger.debug(f"_page_is_fully_done: target mismatch ps_trg={ps.get('target_lang')} page_trg={page.target_lang} for {page.image_path}")
            return False
        if ps.get("translator_key") != translator_key:
            logger.debug(f"_page_is_fully_done: translator mismatch ps={ps.get('translator_key')} now={translator_key} for {page.image_path}")
            return False
        current_ctx_hash = hashlib.md5(extra_context.encode()).hexdigest() if extra_context else "no_context"
        if ps.get("extra_context_hash") != current_ctx_hash:
            logger.debug(f"_page_is_fully_done: context hash mismatch for {page.image_path}")
            return False
        state = self.main_page.image_states.get(page.image_path, {})
        blk_list = state.get("blk_list")
        if not blk_list:
            logger.debug(f"_page_is_fully_done: no blk_list for {page.image_path}")
            return False
        ocr_cache_key = self._get_ocr_cache_key_for_page(page)
        if not self.cache_manager._can_serve_all_blocks_from_ocr_cache(ocr_cache_key, blk_list):
            logger.debug(f"_page_is_fully_done: OCR cache incomplete for {page.image_path}")
            return False

        translation_cache_key = self.cache_manager._get_translation_cache_key(
            page.image,
            "",
            page.target_lang,
            translator_key,
            extra_context,
        )
        if not self.cache_manager._can_serve_all_blocks_from_translation_cache(translation_cache_key, blk_list):
            logger.debug(f"_page_is_fully_done: translation cache incomplete for {page.image_path}")
            return False

        viewer_state = get_target_snapshot(
            state,
            page.target_lang,
            fallback_to_viewer_state=False,
        )
        if not viewer_state:
            logger.debug(f"_page_is_fully_done: missing target render snapshot for {page.image_path}")
            return False
        text_items_state = viewer_state.get("text_items_state") or []
        if not text_items_state:
            logger.debug(f"_page_is_fully_done: missing rendered text items for {page.image_path}")
            return False

        rendered_uids = {
            str(item.get("block_uid", ""))
            for item in text_items_state
            if isinstance(item, dict) and item.get("block_uid")
        }
        expected_uids = {
            str(getattr(blk, "block_uid", ""))
            for blk in blk_list
            if getattr(blk, "block_uid", "") and len((getattr(blk, "translation", "") or "")) > 1
        }
        if rendered_uids != expected_uids:
            logger.debug(
                f"_page_is_fully_done: render snapshot mismatch for {page.image_path} "
                f"rendered={len(rendered_uids)} expected={len(expected_uids)}"
            )
            return False
        return True

    def _page_can_skip_detection(self, page: PreparedBatchPage) -> bool:
        """Check if a page already has detected blocks and can skip text-block detection.
        This is true when detection stage was completed and blk_list is available."""
        state = self.main_page.image_states.get(page.image_path, {})
        return bool(state.get("blk_list")) and is_stage_available(
            state,
            "detect",
            target_lang=page.target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main_page.image_patches.get(page.image_path)
            ),
        )

    def _page_can_skip_inpainting(self, page: PreparedBatchPage) -> bool:
        """Check if a page already has a reusable inpaint result.

        Inpaint is page-wide and target-independent. Once it has been completed
        and the generated patches are still present in the project state, later
        target-language reruns should reuse that cached cleanup instead of
        recomputing a new mask/inpaint pass.
        """
        state = self.main_page.image_states.get(page.image_path, {})
        if not is_stage_available(
            state,
            "clean",
            target_lang=page.target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main_page.image_patches.get(page.image_path)
            ),
        ):
            return False
        return bool(self._get_cached_inpaint_patches(page.image_path))

    def _get_cached_inpaint_patches(self, image_path: str) -> list[dict]:
        state = self.main_page.image_states.get(image_path, {})
        inpaint_cache = state.get("inpaint_cache") or []
        if inpaint_cache:
            return inpaint_cache
        return self.main_page.image_patches.get(image_path, []) or []

    def _prime_runtime_inpaint_cache(self, page: PreparedBatchPage) -> list[dict]:
        cached_patches = self._get_cached_inpaint_patches(page.image_path)
        if cached_patches and not self.main_page.image_patches.get(page.image_path):
            self.main_page.image_patches[page.image_path] = [
                dict(patch) for patch in cached_patches
            ]
        return cached_patches

    def _restore_cached_inpaint_image(self, page: PreparedBatchPage):
        """Rebuild the cleaned page image from cached inpaint patches.

        The cache stores patch slices, not a full flattened image, so reuse on a
        later target language needs to replay those slices back onto the base
        page image.
        """
        if page.image is None:
            return None

        cached_patches = self._prime_runtime_inpaint_cache(page)
        if not cached_patches:
            return page.image

        restored = page.image.copy()
        mem_by_hash = {
            patch.get("hash"): patch
            for patch in self.main_page.in_memory_patches.get(page.image_path, [])
            if patch.get("hash")
        }

        for saved_patch in cached_patches:
            bbox = saved_patch.get("bbox") or []
            if len(bbox) != 4:
                continue

            x, y, w, h = (int(round(float(v))) for v in bbox)
            if w <= 0 or h <= 0:
                continue
            if x >= restored.shape[1] or y >= restored.shape[0]:
                continue

            patch_image = None
            patch_hash = saved_patch.get("hash")
            if patch_hash and patch_hash in mem_by_hash:
                patch_image = mem_by_hash[patch_hash].get("image")

            if patch_image is None:
                png_path = saved_patch.get("png_path")
                if png_path:
                    ensure_path_materialized(png_path)
                    patch_image = imk.read_image(png_path)

            if patch_image is None:
                continue

            patch_h, patch_w = patch_image.shape[:2]
            copy_w = min(w, patch_w, restored.shape[1] - x)
            copy_h = min(h, patch_h, restored.shape[0] - y)
            if copy_w <= 0 or copy_h <= 0:
                continue

            restored[y : y + copy_h, x : x + copy_w] = patch_image[:copy_h, :copy_w]

        return restored

    def _page_can_skip_ocr(self, page: PreparedBatchPage) -> bool:
        """Check if a page already has OCR results and can skip OCR stage.
        This is true when OCR stage was completed and OCR settings unchanged."""
        state = self.main_page.image_states.get(page.image_path, {})
        ps = self._get_pipeline_state(page.image_path)
        if not is_stage_available(
            state,
            "ocr",
            target_lang=page.target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main_page.image_patches.get(page.image_path)
            ),
        ):
            return False

        # Check if OCR cache key matches (this validates model/device/settings)
        expected_ocr_cache_key = self._get_ocr_cache_key_for_page(page)
        cached_ocr_cache_key = ps.get("ocr_cache_key", "")
        return expected_ocr_cache_key == cached_ocr_cache_key

    def _build_render_template_map(self, image_path: str, target_lang: str) -> dict[tuple[str, tuple[int, int, int, int], float], dict]:
        state = self.main_page.image_states.get(image_path, {})
        return build_render_template_map(state, target_lang)

    def _load_page_state_into_blk_list(self, page: PreparedBatchPage):
        """Load the saved blk_list from image_states into the page object, skipping
        detection/ocr/inpaint stages. Also ensures the image is loaded."""
        ensure_path_materialized(page.image_path)
        if page.image is None:
            page.image = imk.read_image(page.image_path)

        state = self.main_page.image_states.get(page.image_path, {})
        saved_blk_list = state.get("blk_list")
        if saved_blk_list is not None and len(saved_blk_list) > 0:
            page.blk_list = [blk for blk in saved_blk_list]  # shallow copy
            logger.info(f"Loaded saved blk_list for {page.image_path} ({len(page.blk_list)} blocks)")

    def _cache_ocr_results_for_page(self, cache_key, page_or_blocks):
        if isinstance(page_or_blocks, PreparedBatchPage):
            blk_list = page_or_blocks.blk_list
        else:
            blk_list = page_or_blocks
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
        return self.cache_manager._get_ocr_cache_key(
            page.image,
            "",
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
            logger.debug(
                "Block-crop batch OCR failed, falling back to page OCR.",
                exc_info=True,
            )
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
        translator = Translator(self.main_page, "", page.target_lang)
        sanitize_translation_source_blocks(page.blk_list)
        blocks_to_translate = getattr(page, "_translation_missing_blocks", page.blk_list)
        translated_blk_list = translator.translate(
            blocks_to_translate,
            page.image,
            extra_context,
        )
        usage = getattr(translator.engine, "last_usage", None)
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

        template_map = self._build_render_template_map(page.image_path, page.target_lang)
        text_items_state = []
        for blk in page.blk_list:
            x1, y1, block_width, block_height = blk.xywh
            translation = blk.translation
            if not translation or len(translation) == 1:
                continue

            block_uid = str(getattr(blk, "block_uid", "") or "")
            template = template_map.get((block_uid, (), 0.0), {}) if block_uid else {}
            if not template:
                template = template_map.get(
                    (
                        "",
                        (
                            int(blk.xyxy[0]),
                            int(blk.xyxy[1]),
                            int(blk.xyxy[2]),
                            int(blk.xyxy[3]),
                        ),
                        float(getattr(blk, "angle", 0.0) or 0.0),
                    ),
                    {},
                )
            font_family = template.get("font_family", font)
            line_spacing_for_block = float(template.get("line_spacing", line_spacing))
            outline_width_for_block = float(template.get("outline_width", outline_width))
            bold_for_block = bool(template.get("bold", bold))
            italic_for_block = bool(template.get("italic", italic))
            underline_for_block = bool(template.get("underline", underline))
            alignment_for_block = template.get("alignment", alignment)
            direction_for_block = template.get("direction", direction)
            outline_enabled = bool(template.get("outline", outline))
            template_outline_color = template.get("outline_color", outline_color)
            if template_outline_color is not None and not isinstance(template_outline_color, QColor):
                template_outline_color = QColor(template_outline_color)
            outline_color_for_block = template_outline_color if outline_enabled else None
            template_font_color = template.get("text_color")
            if template_font_color is not None and not isinstance(template_font_color, QColor):
                template_font_color = QColor(template_font_color)

            vertical = is_vertical_block(blk, page.trg_lng_cd)
            block_init_font_size = int(round(template.get("font_size", resolve_init_font_size(blk, max_font_size, min_font_size))))
            translation, font_size = pyside_word_wrap(
                translation,
                font_family,
                block_width,
                block_height,
                line_spacing_for_block,
                outline_width_for_block,
                bold_for_block,
                italic_for_block,
                underline_for_block,
                alignment_for_block,
                direction_for_block,
                block_init_font_size,
                min_font_size,
                vertical,
            )

            if page.image_path == file_on_display:
                self.main_page.blk_rendered.emit(translation, font_size, blk, page.image_path)

            if is_no_space_lang(page.trg_lng_cd):
                translation = translation.replace(" ", "")

            font_color = get_smart_text_color(blk.font_color, template_font_color or setting_font_color)
            text_props = TextItemProperties(
                text=translation,
                source_text=blk.translation or blk.text or translation,
                font_family=font_family,
                font_size=font_size,
                text_color=font_color,
                alignment=alignment_for_block,
                line_spacing=line_spacing_for_block,
                outline_color=outline_color_for_block,
                outline_width=outline_width_for_block,
                outline=outline_enabled,
                bold=bold_for_block,
                italic=italic_for_block,
                underline=underline_for_block,
                position=(x1, y1),
                rotation=blk.angle,
                scale=1.0,
                transform_origin=blk.tr_origin_point,
                width=block_width,
                height=block_height,
                direction=direction_for_block,
                vertical=vertical,
                block_uid=getattr(blk, "block_uid", ""),
                selection_outlines=[
                    OutlineInfo(
                        0,
                        len(translation),
                        outline_color_for_block,
                        outline_width_for_block,
                        OutlineType.Full_Document,
                    )
                ]
                if outline_enabled and outline_color_for_block is not None
                else [],
            )
            text_items_state.append(text_props.to_dict())

        state = self.main_page.image_states[page.image_path]
        viewer_state = state.setdefault("viewer_state", {})
        viewer_state.update(
            {
                "text_items_state": text_items_state,
                "push_to_stack": False,
            }
        )
        set_target_snapshot(state, page.target_lang, viewer_state)

    def _finalize_prepared_page(
        self,
        page: PreparedBatchPage,
        total_images: int,
        export_settings: dict,
        translator_key: str = "",
        extra_context: str = "",
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

        state = self.main_page.image_states[page.image_path]
        state.update({"blk_list": page.blk_list, "target_lang": page.target_lang})

        if page.image_path == self._current_displayed_file():
            self.main_page.blk_list = page.blk_list

        has_runtime_patches = bool(
            state.get("inpaint_cache") or self.main_page.image_patches.get(page.image_path)
        )
        ps, _ = activate_target_lang(
            state,
            page.target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        set_page_stage_validity(
            state,
            "detect",
            bool(page.blk_list),
            target_lang=page.target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        set_page_stage_validity(
            state,
            "segment",
            bool(
                state.get("brush_strokes")
                or any(getattr(blk, "inpaint_bboxes", None) is not None for blk in page.blk_list or [])
            ),
            target_lang=page.target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        mark_ocr_ready(state, has_runtime_patches=has_runtime_patches)
        if self._get_cached_inpaint_patches(page.image_path):
            state["inpaint_cache"] = copy.deepcopy(self._get_cached_inpaint_patches(page.image_path))
            mark_clean_ready(state, has_runtime_patches=has_runtime_patches)
        ps, _ = finalize_render_stage(
            state,
            page.target_lang,
            has_runtime_patches=has_runtime_patches,
            ui_stage="render",
        )
        ps["ocr_cache_key"] = page.ocr_cache_key or ps.get("ocr_cache_key", "")
        ps["translator_key"] = translator_key
        ps["extra_context_hash"] = hashlib.md5(extra_context.encode()).hexdigest() if extra_context else "no_context"
        self.main_page.render_state_ready.emit(page.image_path)

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

        # Pre-filter pages: identify fully-done, skip-detection, and fresh pages
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
            logger.info(f"Page {loaded_page.image_path} pipeline_state: completed={ps.get('completed_stages')} trg={ps.get('target_lang')}")

            if self._page_is_fully_done(loaded_page, translator_key, extra_context):
                fully_done_pages.append(loaded_page)
                logger.info(f"Page already fully translated, skipping reprocessing: {loaded_page.image_path}")
            elif self._page_can_skip_detection(loaded_page):
                skip_detection_pages.append(loaded_page)
                logger.info(f"Reusing cached blocks, skipping detection: {loaded_page.image_path}")
            else:
                fresh_pages.append(loaded_page)

        # Process fresh pages through the full pipeline (detection → ocr → inpaint)
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

        # === Fully done pages: skip EVERYTHING, just render with existing blocks ===
        for page in fully_done_pages:
            if self._is_cancelled():
                return
            self.emit_progress(page.index, total_images, 0, 10, True)
            self._load_page_state_into_blk_list(page)
            # Apply cached translations directly (they are guaranteed to match)
            tc_key = self.cache_manager._get_translation_cache_key(
                page.image, "", page.target_lang, translator_key, extra_context
            )
            page.translation_cache_key = tc_key
            self.cache_manager._apply_cached_translations_to_blocks(tc_key, page.blk_list)
            # Skip inpainting — restore the cached cleaned image as render target.
            page.inpaint_input_img = self._restore_cached_inpaint_image(page)
            page.skip_full_pipeline = True
            page.skip_inpaint = True
            translated_pages.append(page)
            self.emit_progress(page.index, total_images, 10, 10, False)
            logger.info(f"Fully done page rendered without reprocessing: {page.image_path}")

        # === Skip-detection pages: load blk_list, run OCR + inpaint, then translate ===
        for page in skip_detection_pages:
            if self._is_cancelled():
                return
            self._load_page_state_into_blk_list(page)
        skip_detection_pages = self._run_chunk_ocr(
            skip_detection_pages, total_images
        )
        self._release_ocr_model_caches()
        self._trim_runtime_memory()
        if self._is_cancelled():
            return

        # Merge skip-detection pages into the normal pipeline flow for inpaint → translate
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
            page.translation_cache_key = self.cache_manager._get_translation_cache_key(
                page.image,
                "",
                page.target_lang,
                translator_key,
                extra_context,
            )
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

        # Separate pages that still need a fresh inpaint pass from pages that can
        # reuse the cached cleanup layer from a previous run/target.
        pages_needing_inpaint = [p for p in translated_pages if getattr(p, 'skip_inpaint', False) is False]
        fully_done_rendered = [p for p in translated_pages if getattr(p, 'skip_inpaint', False) is True]

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

        # Finalize fully-done pages (they skipped inpaint, just need rendering)
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
