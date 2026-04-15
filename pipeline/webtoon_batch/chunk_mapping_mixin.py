from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List

import imkit as imk
import numpy as np

from modules.utils.textblock import TextBlock

logger = logging.getLogger(__name__)


class ChunkMappingMixin:
    def _convert_blocks_to_virtual_coordinates(
        self,
        blk_list: List[TextBlock],
        mapping_data: List[Dict],
    ) -> Dict[str, List[TextBlock]]:
        virtual_page_blocks = defaultdict(list)

        for blk in blk_list:
            target_mapping = None
            if len(mapping_data) == 2:
                boundary_y = mapping_data[0]["combined_y_end"]
                if blk.xyxy[1] < boundary_y and blk.xyxy[3] > boundary_y:
                    target_mapping = mapping_data[0]

            if target_mapping is None:
                max_overlap_area = -1
                for mapping in mapping_data:
                    y_start = mapping["combined_y_start"]
                    y_end = mapping["combined_y_end"]
                    overlap_y_start = max(blk.xyxy[1], y_start)
                    overlap_y_end = min(blk.xyxy[3], y_end)
                    vertical_overlap = max(0, overlap_y_end - overlap_y_start)
                    block_width = blk.xyxy[2] - blk.xyxy[0]
                    overlap_area = block_width * vertical_overlap

                    if overlap_area > max_overlap_area:
                        max_overlap_area = overlap_area
                        target_mapping = mapping

            if target_mapping:
                vpage = target_mapping["virtual_page"]
                y_start = target_mapping["combined_y_start"]
                x_offset = target_mapping["x_offset"]

                virtual_block = blk.deep_copy()
                virtual_block.xyxy = [
                    blk.xyxy[0] - x_offset,
                    blk.xyxy[1] - y_start,
                    blk.xyxy[2] - x_offset,
                    blk.xyxy[3] - y_start,
                ]

                if virtual_block.bubble_xyxy is not None:
                    virtual_block.bubble_xyxy = [
                        blk.bubble_xyxy[0] - x_offset,
                        blk.bubble_xyxy[1] - y_start,
                        blk.bubble_xyxy[2] - x_offset,
                        blk.bubble_xyxy[3] - y_start,
                    ]

                virtual_page_blocks[vpage.virtual_id].append(virtual_block)
            else:
                logger.warning(
                    "Block %s could not be assigned to any virtual page",
                    blk.xyxy,
                )

        return dict(virtual_page_blocks)

    def _calculate_virtual_inpaint_patches(
        self,
        mask: np.ndarray,
        inpainted_image: np.ndarray,
        mapping_data: List[Dict],
    ) -> Dict[str, List[Dict]]:
        contours, _ = imk.find_contours(mask)
        if not contours:
            return {}

        patches_by_virtual_page = defaultdict(list)
        for contour in contours:
            x, y, w, h = imk.bounding_rect(contour)
            patch_bottom = y + h

            for mapping in mapping_data:
                vpage = mapping["virtual_page"]
                y_start = mapping["combined_y_start"]
                y_end = mapping["combined_y_end"]
                x_offset = mapping["x_offset"]

                if patch_bottom <= y_start or y >= y_end:
                    continue

                clip_y_start = max(y, y_start)
                clip_y_end = min(patch_bottom, y_end)
                if clip_y_end <= clip_y_start:
                    continue

                clipped_patch = inpainted_image[clip_y_start:clip_y_end, x: x + w]
                virtual_y = clip_y_start - y_start
                virtual_x = x - x_offset
                virtual_height = clip_y_end - clip_y_start

                physical_coords = vpage.virtual_to_physical_coords(
                    [virtual_x, virtual_y, virtual_x + w, virtual_y + virtual_height]
                )

                physical_x = int(physical_coords[0])
                physical_y = int(physical_coords[1])
                physical_width = w
                physical_height = int(physical_coords[3] - physical_coords[1])

                webtoon_manager = self.main_page.image_viewer.webtoon_manager
                page_y_position_in_scene = 0
                if (
                    webtoon_manager
                    and vpage.physical_page_index < len(webtoon_manager.image_positions)
                ):
                    page_y_position_in_scene = webtoon_manager.image_positions[
                        vpage.physical_page_index
                    ]

                scene_x = physical_x
                scene_y = physical_y + page_y_position_in_scene

                patch_data = {
                    "bbox": [physical_x, physical_y, physical_width, physical_height],
                    "image": clipped_patch.copy(),
                    "page_index": vpage.physical_page_index,
                    "file_path": vpage.physical_page_path,
                    "scene_pos": [scene_x, scene_y],
                }
                patches_by_virtual_page[vpage.virtual_id].append(patch_data)

        return dict(patches_by_virtual_page)
