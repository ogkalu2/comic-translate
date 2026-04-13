from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.path_materialization import ensure_path_materialized
from modules.utils.textblock import sort_blk_list
from modules.detection.utils.orientation import infer_orientation, infer_reading_order
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

    def _create_virtual_pages_for_physical(
        self: WebtoonBatchProcessor,
        physical_page_index: int,
        physical_page_path: str,
        physical_width: int,
        physical_height: int,
    ) -> List[VirtualPage]:
        
        min_chunk = self.min_virtual_chunk_height
        max_chunk = self.max_virtual_chunk_height
        target_chunk = self.target_virtual_chunk_height

        min_chunk = max(1, min_chunk)
        max_chunk = max(min_chunk, max_chunk)
        target_chunk = max(min_chunk, min(max_chunk, target_chunk))

        chunk_count = self._select_virtual_chunk_count(
            physical_height=physical_height,
            min_chunk=min_chunk,
            max_chunk=max_chunk,
            target_chunk=target_chunk,
        )
        if chunk_count <= 1:
            return [
                VirtualPage(
                    physical_page_index=physical_page_index,
                    physical_page_path=physical_page_path,
                    virtual_index=0,
                    crop_top=0,
                    crop_bottom=physical_height,
                    crop_height=physical_height,
                    physical_width=physical_width,
                    physical_height=physical_height,
                    virtual_id=f"p{physical_page_index}_v0",
                )
            ]

        # Balanced chunking with chosen count:
        # distribute into k chunks of near-equal height (difference <= 1 px).
        base_chunk_height = physical_height // chunk_count
        extra_rows = physical_height % chunk_count

        virtual_pages: List[VirtualPage] = []
        top = 0
        for virtual_index in range(chunk_count):
            chunk_height = base_chunk_height + (1 if virtual_index < extra_rows else 0)
            bottom = top + chunk_height
            virtual_pages.append(
                VirtualPage(
                    physical_page_index=physical_page_index,
                    physical_page_path=physical_page_path,
                    virtual_index=virtual_index,
                    crop_top=top,
                    crop_bottom=bottom,
                    crop_height=bottom - top,
                    physical_width=physical_width,
                    physical_height=physical_height,
                    virtual_id=f"p{physical_page_index}_v{virtual_index}",
                )
            )
            top = bottom
        return virtual_pages

    @staticmethod
    def _select_virtual_chunk_count(
        physical_height: int, min_chunk: int, max_chunk: int, target_chunk: int
    ) -> int:
        """
        Choose chunk count using three parameters:
        - min_chunk: preferred lower bound for chunk height
        - max_chunk: preferred upper bound for chunk height
        - target_chunk: ideal chunk height

        If no chunk count can satisfy both bounds (mathematically impossible for some
        heights), choose the least-violating count with a stronger penalty for dropping
        below min_chunk.
        """
        h = max(1, int(physical_height))
        min_chunk = max(1, int(min_chunk))
        max_chunk = max(min_chunk, int(max_chunk))
        target_chunk = max(min_chunk, min(max_chunk, int(target_chunk)))

        lower_k = max(1, int(np.ceil(float(h) / float(max_chunk))))
        upper_k = max(1, int(np.floor(float(h) / float(min_chunk))))
        ideal_k = max(1, int(round(float(h) / float(target_chunk))))

        if lower_k <= upper_k:
            candidates = range(lower_k, upper_k + 1)
            return min(
                candidates,
                key=lambda k: (abs((float(h) / float(k)) - float(target_chunk)), k),
            )

        # Infeasible band: no k can satisfy both min and max simultaneously.
        # Evaluate nearby candidates and pick least-violating option.
        candidate_set = {
            1,
            lower_k,
            upper_k,
            ideal_k,
            max(1, ideal_k - 1),
            ideal_k + 1,
            lower_k + 1,
            max(1, upper_k - 1),
        }
        candidate_set = {k for k in candidate_set if k >= 1}

        def score(k: int) -> Tuple[float, float, int]:
            small = h // k
            large = int(np.ceil(float(h) / float(k)))
            under = max(0, min_chunk - small)
            over = max(0, large - max_chunk)
            avg_dev = abs((float(h) / float(k)) - float(target_chunk))
            # Below-min chunks are penalized more heavily.
            return (2.0 * float(under) + float(over), avg_dev, k)

        return min(candidate_set, key=score)

    def _read_virtual_image(
        self: WebtoonBatchProcessor, vpage: VirtualPage
    ) -> Optional[np.ndarray]:
        ensure_path_materialized(vpage.physical_page_path)
        with Image.open(vpage.physical_page_path) as image:
            crop = image.crop(
                (0, int(vpage.crop_top), int(vpage.physical_width), int(vpage.crop_bottom))
            )
            if crop.mode != "RGB":
                crop = crop.convert("RGB")
            arr = np.array(crop)
        if arr is None or arr.size == 0:
            return None
        return arr

    def _load_virtual_record(
        self: WebtoonBatchProcessor,
        record: Dict,
        total_images: int,
        emit_progress: bool,
    ) -> Dict:
        if record.get("skip_only", False):
            if emit_progress:
                self._emit_progress(record["selected_index"], total_images, 1, False)
            return record
        if record.get("image") is not None:
            if emit_progress:
                self._emit_progress(record["selected_index"], total_images, 1, False)
            return record

        vpage: VirtualPage = record["vpage"]
        image = self._read_virtual_image(vpage)
        if image is None:
            logger.error("Failed to load virtual image: %s", vpage.virtual_id)
            record["skip_only"] = True
            if emit_progress:
                self._emit_progress(record["selected_index"], total_images, 1, False)
            return record

        record["image"] = image
        record["detected_blocks"] = self._detect_blocks_for_page(image)
        logger.info(
            "Webtoon batch detect: page=%s virtual=%s detected_blocks=%d",
            record["path"],
            vpage.virtual_id,
            len(record["detected_blocks"]),
        )
        if emit_progress:
            self._emit_progress(record["selected_index"], total_images, 1, False)
        return record

    @staticmethod
    def _can_pair_for_seam(current_record: Dict, next_record: Optional[Dict]) -> bool:
        if next_record is None:
            return False
        if current_record.get("skip_only", False) or next_record.get("skip_only", False):
            return False

        curr_v: VirtualPage = current_record["vpage"]
        next_v: VirtualPage = next_record["vpage"]
        if curr_v.physical_page_index == next_v.physical_page_index:
            return next_v.virtual_index == curr_v.virtual_index + 1
        if next_v.physical_page_index == curr_v.physical_page_index + 1:
            return curr_v.is_last_virtual and next_v.is_first_virtual
        return False

    def _build_pair_split_matches(
        self: WebtoonBatchProcessor,
        current_record: Dict,
        next_record: Dict,
        current_excluded: set,
    ) -> Tuple[List, set]:
        current_blocks = current_record.get("detected_blocks", [])
        next_blocks = next_record.get("detected_blocks", [])
        if not current_blocks or not next_blocks:
            return [], set()

        current_height = int(current_record["image"].shape[0])
        pairs = self._match_split_blocks(current_blocks, current_height, next_blocks)
        if not pairs:
            return [], set()

        split_matches = []
        consumed_bottom_indices = set()
        for top_idx, bottom_idx in pairs:
            if top_idx in current_excluded:
                continue

            top_block = current_blocks[top_idx]
            bottom_block = next_blocks[bottom_idx]
            owner_block = top_block.deep_copy()

            shifted_bottom_xyxy = self._shift_xyxy(
                bottom_block.xyxy, 0.0, float(current_height)
            )
            owner_block.xyxy = self._union_xyxy(top_block.xyxy, shifted_bottom_xyxy)

            top_bubble = top_block.bubble_xyxy
            bottom_bubble = (
                self._shift_xyxy(bottom_block.bubble_xyxy, 0.0, float(current_height))
                if bottom_block.bubble_xyxy is not None
                else None
            )
            if top_bubble is not None and bottom_bubble is not None:
                owner_block.bubble_xyxy = self._union_xyxy(top_bubble, bottom_bubble)
            elif top_bubble is not None:
                owner_block.bubble_xyxy = list(top_bubble)
            elif bottom_bubble is not None:
                owner_block.bubble_xyxy = list(bottom_bubble)
            else:
                owner_block.bubble_xyxy = None

            split_matches.append(
                SimpleNamespace(
                    top_index=top_idx,
                    bottom_index=bottom_idx,
                    owner_block=owner_block,
                )
            )
            current_excluded.add(top_idx)
            consumed_bottom_indices.add(bottom_idx)

        return split_matches, consumed_bottom_indices

    def _build_extended_ocr_image_for_pair(
        self: WebtoonBatchProcessor,
        current_record: Dict,
        next_record: Optional[Dict],
        split_owned_blocks: List,
    ) -> np.ndarray:
        """
        Build a single OCR image for current-page processing.

        If no seam-owned blocks exist, use the current virtual image as-is.
        If seam-owned blocks exist, extend the current image with only the
        required rows from the next image so split blocks are fully visible.
        """
        current_image = current_record["image"]
        if not split_owned_blocks or next_record is None or next_record.get("image") is None:
            return current_image

        next_image = next_record["image"]
        stitched = self._build_stitched_pair(current_image, next_image)
        current_h = int(current_image.shape[0])
        stitched_h = int(stitched.shape[0])
        max_owner_y = max(float(block.xyxy[3]) for block in split_owned_blocks)
        target_h = max(current_h, int(np.ceil(max_owner_y)) + 1)
        target_h = max(1, min(stitched_h, target_h))
        return stitched[:target_h, :].copy()

    @staticmethod
    def _convert_blocks_to_physical(
        blocks: List, owner_vpage: VirtualPage
    ) -> List:
        physical_blocks = []
        for block in blocks:
            out = block.deep_copy()
            out.xyxy = owner_vpage.virtual_to_physical_coords(list(out.xyxy))
            if out.bubble_xyxy is not None:
                out.bubble_xyxy = owner_vpage.virtual_to_physical_coords(list(out.bubble_xyxy))
            physical_blocks.append(out)
        return physical_blocks

    def _finalize_physical_page(
        self: WebtoonBatchProcessor,
        page_info: Dict,
        page_accum: Dict[str, Dict[str, List]],
        total_images: int,
        timestamp: str,
    ) -> None:
        image_path = page_info["path"]
        selected_index = int(page_info["selected_index"])
        global_index = int(page_info["global_index"])
        page_state = self.main_page.image_states.setdefault(image_path, {})
        page_state.setdefault("viewer_state", {})

        if page_info.get("skip", False):
            page_state["blk_list"] = []
            page_state["skip_render"] = True
            page_state["viewer_state"]["text_items_state"] = []
            self.final_patches_for_save[image_path] = []
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

    def webtoon_batch_process(
        self: WebtoonBatchProcessor, selected_paths: List[str] = None
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
            global_index_by_path = {
                path: idx for idx, path in enumerate(self.main_page.image_files)
            }

            physical_pages: List[Dict] = []
            virtual_records: List[Dict] = []

            for selected_index, image_path in enumerate(image_list):
                global_index = int(global_index_by_path.get(image_path, selected_index))
                page_state = self.main_page.image_states.get(image_path, {})
                skip_page = bool(page_state.get("skip", False))

                if skip_page:
                    page_info = {
                        "path": image_path,
                        "selected_index": selected_index,
                        "global_index": global_index,
                        "skip": True,
                        "width": 0,
                        "height": 0,
                    }
                    physical_pages.append(page_info)
                    virtual_records.append(
                        {
                            "path": image_path,
                            "selected_index": selected_index,
                            "global_index": global_index,
                            "physical_index": global_index,
                            "skip_only": True,
                            "is_first_virtual": True,
                            "is_last_virtual": True,
                            "vpage": None,
                        }
                    )
                    continue

                ensure_path_materialized(image_path)
                with Image.open(image_path) as pil_image:
                    width, height = pil_image.size

                page_info = {
                    "path": image_path,
                    "selected_index": selected_index,
                    "global_index": global_index,
                    "skip": False,
                    "width": int(width),
                    "height": int(height),
                }
                completed_stages = set(
                    page_state.get("pipeline_state", {}).get("completed_stages", [])
                )
                page_info["reuse_cached_inpaint"] = (
                    "inpaint" in completed_stages
                    and bool(
                        page_state.get("inpaint_cache")
                        or self.main_page.image_patches.get(image_path)
                    )
                )
                if page_info["reuse_cached_inpaint"]:
                    logger.info("Reusing cached inpaint layer for %s", image_path)
                physical_pages.append(page_info)

                vpages = self._create_virtual_pages_for_physical(
                    physical_page_index=global_index,
                    physical_page_path=image_path,
                    physical_width=int(width),
                    physical_height=int(height),
                )
                for vpage in vpages:
                    virtual_records.append(
                        {
                            "path": image_path,
                            "selected_index": selected_index,
                            "global_index": global_index,
                            "physical_index": global_index,
                            "skip_only": False,
                            "is_first_virtual": vpage.is_first_virtual,
                            "is_last_virtual": vpage.is_last_virtual,
                            "vpage": vpage,
                            "y_offset": int(vpage.crop_top),
                            "image": None,
                            "detected_blocks": [],
                            "exclude_indices_from_prev": set(),
                        }
                    )

            page_info_by_path = {info["path"]: info for info in physical_pages}
            page_accum = {
                info["path"]: {"blocks": [], "patches": []}
                for info in physical_pages
            }
            for info in physical_pages:
                if info.get("reuse_cached_inpaint", False):
                    page_state = self.main_page.image_states.get(info["path"], {})
                    cached_patches = page_state.get("inpaint_cache") or self.main_page.image_patches.get(info["path"], [])
                    if cached_patches:
                        page_accum[info["path"]]["patches"] = list(cached_patches)

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
                    self._emit_progress(
                        current_record["selected_index"], total_images, 1, False
                    )
                else:
                    current_record = self._load_virtual_record(
                        record, total_images, emit_progress=True
                    )

                next_record = None
                if index + 1 < len(virtual_records):
                    next_record = self._load_virtual_record(
                        virtual_records[index + 1], total_images, emit_progress=False
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
                    self._emit_progress(
                        current_record["selected_index"], total_images, 3, False
                    )
                    split_matches, consumed_bottom = self._build_pair_split_matches(
                        current_record, next_record, current_excluded
                    )
                    if consumed_bottom:
                        next_record.setdefault("exclude_indices_from_prev", set()).update(
                            consumed_bottom
                        )
                    if split_matches:
                        split_owned_blocks.extend([m.owner_block for m in split_matches])

                regular_blocks = [
                    blk.deep_copy()
                    for idx_blk, blk in enumerate(current_record.get("detected_blocks", []))
                    if idx_blk not in current_excluded
                ]

                self._emit_progress(current_record["selected_index"], total_images, 2, False)
                page_state = self.main_page.image_states.get(current_record["path"], {})
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
                        current_record["image"], regular_blocks
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
                final_blocks_virtual = (
                    sort_blk_list(final_blocks_virtual, rtl) if final_blocks_virtual else []
                )

                self._emit_progress(current_record["selected_index"], total_images, 7, False)
                target_lang = page_state.get("target_lang", self.main_page.t_combo.currentText())
                self._run_translation_on_blocks(
                    current_record["image"],
                    final_blocks_virtual,
                    "",
                    target_lang,
                    current_record["path"],
                )

                final_blocks_physical = self._convert_blocks_to_physical(
                    final_blocks_virtual, current_vpage
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
