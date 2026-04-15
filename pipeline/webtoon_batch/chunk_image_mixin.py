from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import imkit as imk
import numpy as np

from app.path_materialization import ensure_path_materialized
from modules.detection.processor import TextBlockDetector
from modules.utils.textblock import TextBlock
from ..virtual_page import VirtualPage

logger = logging.getLogger(__name__)


class ChunkImageMixin:
    def _create_virtual_chunk_image(
        self,
        vpage1: VirtualPage,
        vpage2: VirtualPage,
    ) -> Tuple[np.ndarray, List[Dict]]:
        if vpage1.virtual_id == vpage2.virtual_id:
            ensure_path_materialized(vpage1.physical_page_path)
            img = imk.read_image(vpage1.physical_page_path)

            if img is None:
                logger.error("Failed to load image: %s", vpage1.physical_page_path)
                return None, []

            virtual_img = vpage1.extract_virtual_image(img)
            h, w = virtual_img.shape[:2]
            mapping_data = [{
                "virtual_page": vpage1,
                "physical_page_index": vpage1.physical_page_index,
                "physical_page_path": vpage1.physical_page_path,
                "combined_y_start": 0,
                "combined_y_end": h,
                "x_offset": 0,
                "virtual_width": w,
                "virtual_height": h,
            }]
            return virtual_img, mapping_data

        ensure_path_materialized(vpage1.physical_page_path)
        img1 = imk.read_image(vpage1.physical_page_path)
        ensure_path_materialized(vpage2.physical_page_path)
        img2 = imk.read_image(vpage2.physical_page_path)

        if img1 is None or img2 is None:
            logger.error("Failed to load images: %s, %s", vpage1.physical_page_path, vpage2.physical_page_path)
            return None, []

        virtual_img1 = vpage1.extract_virtual_image(img1)
        virtual_img2 = vpage2.extract_virtual_image(img2)

        max_width = max(virtual_img1.shape[1], virtual_img2.shape[1])
        total_height = virtual_img1.shape[0] + virtual_img2.shape[0]

        combined_image = np.zeros((total_height, max_width, 3), dtype=np.uint8)
        combined_image.fill(255)

        h1, w1 = virtual_img1.shape[:2]
        x1_offset = (max_width - w1) // 2
        combined_image[0:h1, x1_offset: x1_offset + w1] = virtual_img1

        h2, w2 = virtual_img2.shape[:2]
        x2_offset = (max_width - w2) // 2
        combined_image[h1: h1 + h2, x2_offset: x2_offset + w2] = virtual_img2

        mapping_data = [
            {
                "virtual_page": vpage1,
                "physical_page_index": vpage1.physical_page_index,
                "physical_page_path": vpage1.physical_page_path,
                "combined_y_start": 0,
                "combined_y_end": h1,
                "x_offset": x1_offset,
                "virtual_width": w1,
                "virtual_height": h1,
            },
            {
                "virtual_page": vpage2,
                "physical_page_index": vpage2.physical_page_index,
                "physical_page_path": vpage2.physical_page_path,
                "combined_y_start": h1,
                "combined_y_end": h1 + h2,
                "x_offset": x2_offset,
                "virtual_width": w2,
                "virtual_height": h2,
            },
        ]

        return combined_image, mapping_data

    def _detect_edge_blocks_virtual(
        self,
        combined_image: np.ndarray,
        vpage1: VirtualPage,
        vpage2: VirtualPage,
    ) -> Tuple[List[TextBlock], bool]:
        if self.block_detection.block_detector_cache is None:
            self.block_detection.block_detector_cache = TextBlockDetector(self.main_page.settings_page)

        blk_list = self.block_detection.block_detector_cache.detect(combined_image)
        if not blk_list:
            return [], False

        boundary_y = vpage1.crop_height
        has_edge_blocks = False
        for blk in blk_list:
            if blk.xyxy[1] < boundary_y and blk.xyxy[3] > boundary_y:
                has_edge_blocks = True
                logger.info("Detected text block spanning virtual page boundary: %s", blk.xyxy)
                break
            if abs(blk.xyxy[3] - boundary_y) < self.edge_threshold or abs(blk.xyxy[1] - boundary_y) < self.edge_threshold:
                has_edge_blocks = True
                logger.info("Detected text block near virtual page boundary: %s", blk.xyxy)
                break

        return blk_list, has_edge_blocks
