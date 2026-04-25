from __future__ import annotations

import logging
from typing import Dict, Optional

from modules.utils.exceptions import InsufficientCreditsException
from ..virtual_page import VirtualPage
from .chunk_image_mixin import ChunkImageMixin
from .chunk_pipeline_phase_mixin import ChunkPipelinePhaseMixin

logger = logging.getLogger(__name__)


class ChunkProcessingMixin(ChunkPipelinePhaseMixin, ChunkImageMixin):
    def _process_virtual_chunk(
        self,
        vpage1: VirtualPage,
        vpage2: VirtualPage,
        chunk_id: str,
        timestamp: str,
        physical_pages_in_chunk: set,
        total_images: int,
    ) -> Optional[Dict]:
        logger.info("Processing virtual chunk %s: %s + %s", chunk_id, vpage1.virtual_id, vpage2.virtual_id)

        combined_image, mapping_data = self._create_virtual_chunk_image(vpage1, vpage2)
        if combined_image is None:
            return None

        blk_list, has_edge_blocks = self._detect_edge_blocks_virtual(combined_image, vpage1, vpage2)

        current_physical_page = min(physical_pages_in_chunk)
        self.main_page.progress_update.emit(current_physical_page, total_images, 1, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        if not blk_list:
            logger.info("No text blocks detected in virtual chunk %s", chunk_id)

        try:
            blk_list = self._run_chunk_ocr(chunk_id, combined_image, blk_list, vpage1, vpage2)
        except InsufficientCreditsException:
            raise

        self.main_page.progress_update.emit(current_physical_page, total_images, 2, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        self.main_page.progress_update.emit(current_physical_page, total_images, 3, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        _mask, _inpaint_input_img, virtual_page_patches = self._run_chunk_inpaint(
            combined_image,
            blk_list,
            mapping_data,
        )

        self.main_page.progress_update.emit(current_physical_page, total_images, 4, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        self.main_page.progress_update.emit(current_physical_page, total_images, 5, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        self.main_page.progress_update.emit(current_physical_page, total_images, 6, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        try:
            self._release_inpainting_before_translation()
            self._run_chunk_translation(chunk_id, blk_list, combined_image, vpage1, vpage2)
        except InsufficientCreditsException:
            raise

        self.main_page.progress_update.emit(current_physical_page, total_images, 7, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        self.main_page.progress_update.emit(current_physical_page, total_images, 8, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        virtual_page_blocks = self._convert_blocks_to_virtual_coordinates(blk_list, mapping_data)

        self.main_page.progress_update.emit(current_physical_page, total_images, 9, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        if not virtual_page_blocks and not virtual_page_patches:
            logger.info("No results (blocks or patches) for virtual chunk %s", chunk_id)
            return None

        return {"blocks": virtual_page_blocks, "patches": virtual_page_patches}
