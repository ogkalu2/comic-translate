from __future__ import annotations

import logging
from typing import Dict, List

from modules.detection.utils.orientation import infer_orientation, infer_reading_order
from modules.utils.textblock import sort_blk_list
from ..page_state import build_page_state_context, has_runtime_patches as page_has_runtime_patches
from ..stage_state import (
    activate_target_lang,
    ensure_pipeline_state,
    finalize_render_stage,
    mark_clean_ready,
    mark_ocr_ready,
    set_page_stage_validity,
)

logger = logging.getLogger(__name__)


class FinalizeMixin:
    def _finalize_physical_page(
        self,
        page_info: Dict,
        page_accum: Dict[str, Dict[str, List]],
        total_images: int,
        timestamp: str,
    ) -> None:
        image_path = page_info["path"]
        selected_index = int(page_info["selected_index"])
        global_index = int(page_info["global_index"])
        page_ctx = build_page_state_context(
            self.main_page.image_states,
            self.main_page.image_patches,
            image_path,
            preferred_target=self.main_page.t_combo.currentText(),
            ensure_state=True,
        )
        page_state = page_ctx.state
        page_state.setdefault("viewer_state", {})

        if page_info.get("skip", False):
            page_state["blk_list"] = []
            page_state["skip_render"] = True
            page_state["viewer_state"]["text_items_state"] = []
            page_state["ui_stage"] = ""
            self.final_patches_for_save[image_path] = []
            ensure_pipeline_state(
                page_state,
                target_lang=page_ctx.target_lang,
                has_runtime_patches=False,
            )["current_stage"] = ""
            self.main_page.render_state_ready.emit(image_path)
            self._save_final_rendered_page(selected_index, image_path, timestamp)
            self._emit_progress(selected_index, total_images, 10, False)
            return

        blocks = list(page_accum[image_path]["blocks"])
        patches = list(page_accum[image_path]["patches"])
        orientation = infer_orientation([blk.xyxy for blk in blocks]) if blocks else "horizontal"
        rtl = infer_reading_order(orientation) == "rtl"
        if blocks:
            blocks = sort_blk_list(blocks, rtl)

        self._emit_progress(selected_index, total_images, 9, False)
        prepared_blocks = self._prepare_page_blocks_for_render(
            image_path=image_path,
            blocks=blocks,
            has_patches=bool(patches),
        )
        self._store_page_text_items(
            page_index=global_index,
            image_path=image_path,
            blocks=prepared_blocks,
            image_shape=(page_info["height"], page_info["width"], 3),
        )

        self.final_patches_for_save[image_path] = patches
        target_lang = page_ctx.target_lang or self.main_page.t_combo.currentText()
        has_runtime_patches = bool(patches) or page_has_runtime_patches(
            page_state,
            self.main_page.image_patches,
            image_path,
        )
        ps, target_lang = activate_target_lang(
            page_state,
            target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        set_page_stage_validity(
            page_state,
            "detect",
            bool(prepared_blocks),
            target_lang=target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        set_page_stage_validity(
            page_state,
            "segment",
            bool(any(getattr(blk, "inpaint_bboxes", None) is not None for blk in prepared_blocks or [])),
            target_lang=target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        mark_ocr_ready(page_state, has_runtime_patches=has_runtime_patches)
        if has_runtime_patches:
            mark_clean_ready(page_state, has_runtime_patches=has_runtime_patches)
        ps, _ = finalize_render_stage(
            page_state,
            target_lang,
            has_runtime_patches=has_runtime_patches,
            ui_stage="render",
        )
        if patches:
            self.main_page.patches_processed.emit(patches, image_path)
        self.main_page.render_state_ready.emit(image_path)

        logger.info(
            "Webtoon batch page-done: page=%s final_blocks=%d patches=%d",
            image_path,
            len(prepared_blocks),
            len(patches),
        )
        self._save_final_rendered_page(selected_index, image_path, timestamp)
        self._emit_progress(selected_index, total_images, 10, False)
