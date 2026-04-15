from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Dict, List, Optional

from modules.detection.utils.orientation import infer_orientation, infer_reading_order
from modules.utils.textblock import sort_blk_list
from ..page_state import build_page_state_context
from ..virtual_page import VirtualPage

if TYPE_CHECKING:
    from .processor import WebtoonBatchProcessor

logger = logging.getLogger(__name__)


class FlowMixin:
    def _emit_progress(
        self: WebtoonBatchProcessor,
        index: int,
        total_images: int,
        step: int,
        change_name: bool,
    ) -> None:
        self.main_page.progress_update.emit(index, total_images, step, 10, change_name)

    def webtoon_batch_process(
        self: WebtoonBatchProcessor,
        selected_paths: List[str] = None,
    ):
        try:
            timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
            image_list = selected_paths if selected_paths is not None else self.main_page.image_files
            total_images = len(image_list)
            if total_images < 1:
                logger.warning("No images to process")
                return

            try:
                if self.main_page.file_handler.should_pre_materialize(image_list):
                    count = self.main_page.file_handler.pre_materialize(image_list)
                    logger.info(
                        "Webtoon batch pre-materialized %d paths before processing.",
                        count,
                    )
            except Exception:
                logger.debug(
                    "Webtoon batch pre-materialization failed; continuing lazily.",
                    exc_info=True,
                )

            self.final_patches_for_save.clear()
            page_info_by_path, page_accum, virtual_records = self._build_webtoon_batch_plan(image_list)

            logger.info(
                "Starting seam-aware virtual streaming webtoon batch processing for %d pages.",
                total_images,
            )

            cached_current: Optional[Dict] = None
            for index, record in enumerate(virtual_records):
                if self._is_cancelled():
                    logger.warning("Webtoon batch cancelled.")
                    return

                if record.get("is_first_virtual", False):
                    self._emit_progress(record["selected_index"], total_images, 0, True)

                if (
                    cached_current is not None
                    and cached_current.get("path") == record.get("path")
                    and getattr(cached_current.get("vpage"), "virtual_id", None)
                    == getattr(record.get("vpage"), "virtual_id", None)
                ):
                    current_record = cached_current
                    cached_current = None
                    self._emit_progress(current_record["selected_index"], total_images, 1, False)
                else:
                    current_record = self._load_virtual_record(record, total_images, emit_progress=True)

                next_record = None
                if index + 1 < len(virtual_records):
                    next_record = self._load_virtual_record(
                        virtual_records[index + 1],
                        total_images,
                        emit_progress=False,
                    )

                if current_record.get("skip_only", False):
                    self._finalize_physical_page(
                        page_info=page_info_by_path[current_record["path"]],
                        page_accum=page_accum,
                        total_images=total_images,
                        timestamp=timestamp,
                    )
                    cached_current = next_record
                    continue

                current_vpage: VirtualPage = current_record["vpage"]
                current_excluded = set(current_record.get("exclude_indices_from_prev", set()))
                split_owned_blocks = []
                split_matches = []
                reuse_cached_inpaint = bool(
                    page_info_by_path[current_record["path"]].get("reuse_cached_inpaint", False)
                )

                if self._can_pair_for_seam(current_record, next_record):
                    self._emit_progress(current_record["selected_index"], total_images, 3, False)
                    split_matches, consumed_bottom = self._build_pair_split_matches(
                        current_record,
                        next_record,
                        current_excluded,
                    )
                    if consumed_bottom:
                        next_record.setdefault("exclude_indices_from_prev", set()).update(consumed_bottom)
                    if split_matches:
                        split_owned_blocks.extend([m.owner_block for m in split_matches])

                regular_blocks = [
                    blk.deep_copy()
                    for idx_blk, blk in enumerate(current_record.get("detected_blocks", []))
                    if idx_blk not in current_excluded
                ]

                self._emit_progress(current_record["selected_index"], total_images, 2, False)
                page_ctx = build_page_state_context(
                    self.main_page.image_states,
                    self.main_page.image_patches,
                    current_record["path"],
                    preferred_target=self.main_page.t_combo.currentText(),
                    ensure_state=True,
                )
                ocr_image = self._build_extended_ocr_image_for_pair(
                    current_record=current_record,
                    next_record=next_record,
                    split_owned_blocks=split_owned_blocks,
                )
                ocr_blocks = regular_blocks + split_owned_blocks
                ocr_affected_paths = [current_record["path"]]
                if split_owned_blocks and next_record is not None:
                    ocr_affected_paths.append(next_record["path"])
                self._run_ocr_on_blocks(
                    ocr_image,
                    ocr_blocks,
                    "",
                    ocr_affected_paths,
                    reason="OCR",
                    sort_after=False,
                )

                if not reuse_cached_inpaint:
                    self._emit_progress(current_record["selected_index"], total_images, 4, False)
                    mask, inpainted = self._inpaint_image_with_blocks(
                        current_record["image"],
                        regular_blocks,
                    )
                    if mask is not None and inpainted is not None:
                        regular_patches = self._extract_page_patches_from_mask(
                            mask=mask,
                            inpainted=inpainted,
                            page_index=int(current_record["global_index"]),
                            file_path=current_record["path"],
                            y_offset=int(current_record["y_offset"]),
                        )
                        page_accum[current_record["path"]]["patches"].extend(regular_patches)

                    if split_matches and next_record is not None:
                        seam_patches = self._process_seam_job_ocr_and_inpaint(
                            seam_job=SimpleNamespace(
                                top_page_index=0,
                                bottom_page_index=1,
                                matches=split_matches,
                            ),
                            page_records=[current_record, next_record],
                        )
                        for patches in seam_patches.values():
                            for patch in patches:
                                patch_path = patch.get("file_path")
                                if patch_path in page_accum:
                                    page_accum[patch_path]["patches"].append(patch)

                final_blocks_virtual = regular_blocks + split_owned_blocks
                orientation = infer_orientation([blk.xyxy for blk in final_blocks_virtual]) if final_blocks_virtual else "horizontal"
                rtl = infer_reading_order(orientation) == "rtl"
                final_blocks_virtual = sort_blk_list(final_blocks_virtual, rtl) if final_blocks_virtual else []

                self._emit_progress(current_record["selected_index"], total_images, 7, False)
                target_lang = page_ctx.target_lang or self.main_page.t_combo.currentText()
                self._run_translation_on_blocks(
                    current_record["image"],
                    final_blocks_virtual,
                    "",
                    target_lang,
                    current_record["path"],
                )

                final_blocks_physical = self._convert_blocks_to_physical(
                    final_blocks_virtual,
                    current_vpage,
                )
                page_accum[current_record["path"]]["blocks"].extend(final_blocks_physical)

                if current_record.get("is_last_virtual", False):
                    self._finalize_physical_page(
                        page_info=page_info_by_path[current_record["path"]],
                        page_accum=page_accum,
                        total_images=total_images,
                        timestamp=timestamp,
                    )

                cached_current = next_record

            logger.info("Seam-aware virtual streaming webtoon batch processing completed.")
        except Exception:
            logger.exception("Webtoon batch processing failed.")
            raise
