from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.path_materialization import ensure_path_materialized
from ..page_state import build_page_state_context, get_runtime_patches
from ..stage_state import is_stage_available
from ..virtual_page import VirtualPage

logger = logging.getLogger(__name__)


class PlanningPairMixin:
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
        self,
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

            shifted_bottom_xyxy = self._shift_xyxy(bottom_block.xyxy, 0.0, float(current_height))
            owner_block.xyxy = self._union_xyxy(top_block.xyxy, shifted_bottom_xyxy)

            top_bubble = top_block.bubble_xyxy
            bottom_bubble = self._shift_xyxy(bottom_block.bubble_xyxy, 0.0, float(current_height)) if bottom_block.bubble_xyxy is not None else None
            if top_bubble is not None and bottom_bubble is not None:
                owner_block.bubble_xyxy = self._union_xyxy(top_bubble, bottom_bubble)
            elif top_bubble is not None:
                owner_block.bubble_xyxy = list(top_bubble)
            elif bottom_bubble is not None:
                owner_block.bubble_xyxy = list(bottom_bubble)
            else:
                owner_block.bubble_xyxy = None

            split_matches.append(SimpleNamespace(top_index=top_idx, bottom_index=bottom_idx, owner_block=owner_block))
            current_excluded.add(top_idx)
            consumed_bottom_indices.add(bottom_idx)

        return split_matches, consumed_bottom_indices

    def _build_extended_ocr_image_for_pair(
        self,
        current_record: Dict,
        next_record: Optional[Dict],
        split_owned_blocks: List,
    ):
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
    def _convert_blocks_to_physical(blocks: List, owner_vpage: VirtualPage) -> List:
        physical_blocks = []
        for block in blocks:
            out = block.deep_copy()
            out.xyxy = owner_vpage.virtual_to_physical_coords(list(out.xyxy))
            if out.bubble_xyxy is not None:
                out.bubble_xyxy = owner_vpage.virtual_to_physical_coords(list(out.bubble_xyxy))
            physical_blocks.append(out)
        return physical_blocks

    def _build_webtoon_batch_plan(self, image_list: List[str]) -> tuple[dict, dict, list[Dict]]:
        global_index_by_path = {path: idx for idx, path in enumerate(self.main_page.image_files)}

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

            page_ctx = build_page_state_context(
                self.main_page.image_states,
                self.main_page.image_patches,
                image_path,
                preferred_target=self.main_page.t_combo.currentText(),
                ensure_state=True,
            )
            page_state = page_ctx.state
            page_info = {
                "path": image_path,
                "selected_index": selected_index,
                "global_index": global_index,
                "skip": False,
                "width": int(width),
                "height": int(height),
            }
            page_info["reuse_cached_inpaint"] = (
                is_stage_available(
                    page_state,
                    "clean",
                    target_lang=page_ctx.target_lang,
                    has_runtime_patches=page_ctx.has_runtime_patches,
                )
                and page_ctx.has_runtime_patches
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
        page_accum = {info["path"]: {"blocks": [], "patches": []} for info in physical_pages}
        for info in physical_pages:
            if info.get("reuse_cached_inpaint", False):
                page_state = self.main_page.image_states.get(info["path"], {})
                cached_patches = get_runtime_patches(page_state, self.main_page.image_patches, info["path"])
                if cached_patches:
                    page_accum[info["path"]]["patches"] = list(cached_patches)

        return page_info_by_path, page_accum, virtual_records
