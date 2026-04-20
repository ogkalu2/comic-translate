from __future__ import annotations

import hashlib
import logging
import os

import imkit as imk

from app.path_materialization import ensure_path_materialized
from modules.detection.processor import TextBlockDetector
from modules.utils.language_utils import get_language_code
from pipeline.page_state import (
    build_page_state_context,
    get_runtime_patches,
    has_runtime_patches as page_has_runtime_patches,
)
from pipeline.render_state import build_render_template_map, get_target_snapshot
from pipeline.stage_state import activate_target_lang, is_stage_available
from pipeline.translation_context import (
    build_translation_prompt_context,
    translation_context_requires_ordering,
)

logger = logging.getLogger(__name__)


class BatchStateMixin:
    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        logger.info("Skipping fallback translated image save for '%s'.", base_name)

    def emit_progress(self, index, total, step, steps, change_name):
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
    ):
        target_lang = self.main_page.image_states[image_path]["target_lang"]
        target_lang_en = self.main_page.lang_mapping.get(target_lang, target_lang)
        trg_lng_cd = get_language_code(target_lang_en)

        base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
        extension = os.path.splitext(image_path)[1]
        directory, archive_bname = self._resolve_output_location(image_path)

        return self.PreparedBatchPage(
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

    def _page_context(self, image_path: str, *, preferred_target: str = ""):
        return build_page_state_context(
            self.main_page.image_states,
            self.main_page.image_patches,
            image_path,
            preferred_target=preferred_target or self.main_page.t_combo.currentText(),
            ensure_state=True,
        )

    def _get_pipeline_state(self, image_path: str) -> dict:
        page_ctx = self._page_context(image_path)
        ps, _ = activate_target_lang(
            page_ctx.state,
            page_ctx.target_lang,
            has_runtime_patches=page_ctx.has_runtime_patches,
        )
        return ps

    def _has_stages_completed(self, stages: set, pipeline_state: dict) -> bool:
        completed = set(pipeline_state.get("completed_stages", []))
        return stages.issubset(completed)

    def _page_is_fully_done(self, page, translator_key: str, extra_context: str) -> bool:
        llm_settings = self._get_llm_settings()
        if translation_context_requires_ordering(llm_settings):
            return False

        page_ctx = self._page_context(page.image_path, preferred_target=page.target_lang)
        state = page_ctx.state
        ps = self._get_pipeline_state(page.image_path)
        has_runtime_patches = page_ctx.has_runtime_patches
        if not (
            is_stage_available(state, "detect", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
            and is_stage_available(state, "ocr", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
            and is_stage_available(state, "translate", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
            and is_stage_available(state, "render", target_lang=page.target_lang, has_runtime_patches=has_runtime_patches)
        ):
            logger.debug("_page_is_fully_done: stage validity incomplete for %s", page.image_path)
            return False
        if ps.get("target_lang") != page.target_lang:
            logger.debug("_page_is_fully_done: target mismatch ps_trg=%s page_trg=%s for %s", ps.get("target_lang"), page.target_lang, page.image_path)
            return False
        if ps.get("translator_key") != translator_key:
            logger.debug("_page_is_fully_done: translator mismatch ps=%s now=%s for %s", ps.get("translator_key"), translator_key, page.image_path)
            return False
        _prompt_context, context_signature = build_translation_prompt_context(
            self.main_page,
            page.image_path,
            page.target_lang,
            llm_settings=llm_settings,
        )
        current_ctx_hash = hashlib.md5(context_signature.encode()).hexdigest() if context_signature else "no_context"
        if ps.get("extra_context_hash") != current_ctx_hash:
            logger.debug("_page_is_fully_done: context hash mismatch for %s", page.image_path)
            return False
        blk_list = state.get("blk_list")
        if not blk_list:
            logger.debug("_page_is_fully_done: no blk_list for %s", page.image_path)
            return False
        ocr_cache_key = self._get_ocr_cache_key_for_page(page)
        if not self.cache_manager._can_serve_all_blocks_from_ocr_cache(ocr_cache_key, blk_list):
            logger.debug("_page_is_fully_done: OCR cache incomplete for %s", page.image_path)
            return False

        translation_cache_key = self.cache_manager._get_translation_cache_key(
            page.image,
            "",
            page.target_lang,
            translator_key,
            context_signature,
        )
        if not self.cache_manager._can_serve_all_blocks_from_translation_cache(translation_cache_key, blk_list):
            logger.debug("_page_is_fully_done: translation cache incomplete for %s", page.image_path)
            return False

        viewer_state = get_target_snapshot(
            state,
            page.target_lang,
            fallback_to_viewer_state=False,
        )
        if not viewer_state:
            logger.debug("_page_is_fully_done: missing target render snapshot for %s", page.image_path)
            return False
        text_items_state = viewer_state.get("text_items_state") or []
        if not text_items_state:
            logger.debug("_page_is_fully_done: missing rendered text items for %s", page.image_path)
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
                "_page_is_fully_done: render snapshot mismatch for %s rendered=%d expected=%d",
                page.image_path,
                len(rendered_uids),
                len(expected_uids),
            )
            return False
        return True

    def _page_can_skip_detection(self, page) -> bool:
        page_ctx = self._page_context(page.image_path, preferred_target=page.target_lang)
        state = page_ctx.state
        return bool(state.get("blk_list")) and is_stage_available(
            state,
            "detect",
            target_lang=page.target_lang,
            has_runtime_patches=page_ctx.has_runtime_patches,
        )

    def _page_can_skip_inpainting(self, page) -> bool:
        page_ctx = self._page_context(page.image_path, preferred_target=page.target_lang)
        state = page_ctx.state
        if not is_stage_available(
            state,
            "clean",
            target_lang=page.target_lang,
            has_runtime_patches=page_ctx.has_runtime_patches,
        ):
            return False
        return bool(self._get_cached_inpaint_patches(page.image_path))

    def _get_cached_inpaint_patches(self, image_path: str) -> list[dict]:
        state = self.main_page.image_states.get(image_path, {})
        return get_runtime_patches(state, self.main_page.image_patches, image_path)

    def _prime_runtime_inpaint_cache(self, page) -> list[dict]:
        cached_patches = self._get_cached_inpaint_patches(page.image_path)
        if cached_patches and not self.main_page.image_patches.get(page.image_path):
            self.main_page.image_patches[page.image_path] = [
                dict(patch) for patch in cached_patches
            ]
        return cached_patches

    def _restore_cached_inpaint_image(self, page):
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

    def _page_can_skip_ocr(self, page) -> bool:
        page_ctx = self._page_context(page.image_path, preferred_target=page.target_lang)
        state = page_ctx.state
        ps = self._get_pipeline_state(page.image_path)
        if not is_stage_available(
            state,
            "ocr",
            target_lang=page.target_lang,
            has_runtime_patches=page_ctx.has_runtime_patches,
        ):
            return False

        expected_ocr_cache_key = self._get_ocr_cache_key_for_page(page)
        cached_ocr_cache_key = ps.get("ocr_cache_key", "")
        return expected_ocr_cache_key == cached_ocr_cache_key

    def _build_render_template_map(self, image_path: str, target_lang: str) -> dict[tuple[str, tuple[int, int, int, int], float], dict]:
        state = self.main_page.image_states.get(image_path, {})
        return build_render_template_map(state, target_lang)
