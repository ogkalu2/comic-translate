from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.path_materialization import ensure_path_materialized
from ..virtual_page import VirtualPage

logger = logging.getLogger(__name__)


class PlanningLayoutMixin:
    def _create_virtual_pages_for_physical(
        self,
        physical_page_index: int,
        physical_page_path: str,
        physical_width: int,
        physical_height: int,
    ) -> List[VirtualPage]:
        min_chunk = max(1, self.min_virtual_chunk_height)
        max_chunk = max(min_chunk, self.max_virtual_chunk_height)
        target_chunk = max(min_chunk, min(max_chunk, self.target_virtual_chunk_height))

        chunk_count = self._select_virtual_chunk_count(
            physical_height=physical_height,
            min_chunk=min_chunk,
            max_chunk=max_chunk,
            target_chunk=target_chunk,
        )
        if chunk_count <= 1:
            return [VirtualPage(
                physical_page_index=physical_page_index,
                physical_page_path=physical_page_path,
                virtual_index=0,
                crop_top=0,
                crop_bottom=physical_height,
                crop_height=physical_height,
                physical_width=physical_width,
                physical_height=physical_height,
                virtual_id=f"p{physical_page_index}_v0",
            )]

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
        physical_height: int,
        min_chunk: int,
        max_chunk: int,
        target_chunk: int,
    ) -> int:
        h = max(1, int(physical_height))
        min_chunk = max(1, int(min_chunk))
        max_chunk = max(min_chunk, int(max_chunk))
        target_chunk = max(min_chunk, min(max_chunk, int(target_chunk)))

        lower_k = max(1, int(np.ceil(float(h) / float(max_chunk))))
        upper_k = max(1, int(np.floor(float(h) / float(min_chunk))))
        ideal_k = max(1, int(round(float(h) / float(target_chunk))))

        if lower_k <= upper_k:
            candidates = range(lower_k, upper_k + 1)
            return min(candidates, key=lambda k: (abs((float(h) / float(k)) - float(target_chunk)), k))

        candidate_set = {1, lower_k, upper_k, ideal_k, max(1, ideal_k - 1), ideal_k + 1, lower_k + 1, max(1, upper_k - 1)}
        candidate_set = {k for k in candidate_set if k >= 1}

        def score(k: int) -> Tuple[float, float, int]:
            small = h // k
            large = int(np.ceil(float(h) / float(k)))
            under = max(0, min_chunk - small)
            over = max(0, large - max_chunk)
            avg_dev = abs((float(h) / float(k)) - float(target_chunk))
            return (2.0 * float(under) + float(over), avg_dev, k)

        return min(candidate_set, key=score)

    def _read_virtual_image(self, vpage: VirtualPage) -> Optional[np.ndarray]:
        ensure_path_materialized(vpage.physical_page_path)
        with Image.open(vpage.physical_page_path) as image:
            crop = image.crop((0, int(vpage.crop_top), int(vpage.physical_width), int(vpage.crop_bottom)))
            if crop.mode != "RGB":
                crop = crop.convert("RGB")
            arr = np.array(crop)
        if arr is None or arr.size == 0:
            return None
        return arr

    def _load_virtual_record(
        self,
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
