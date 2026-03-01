from typing import Dict, List

from modules.utils.textblock import TextBlock


class DedupeMixin:
    @staticmethod
    def _rect_area_xyxy(xyxy: List[float]) -> float:
        x1, y1, x2, y2 = xyxy
        return max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))

    @staticmethod
    def _rect_intersection_area_xyxy(a: List[float], b: List[float]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(float(ax1), float(bx1))
        iy1 = max(float(ay1), float(by1))
        ix2 = min(float(ax2), float(bx2))
        iy2 = min(float(ay2), float(by2))
        return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)

    def _should_suppress_clipped_block(
        self,
        physical_page_index: int,
        physical_coords: List[float],
        physical_height: float,
    ) -> bool:
        """
        Suppress clipped duplicates on page boundaries when a neighboring page already
        emitted a spanning/merged block that visually covers this region.
        """
        claims = self._spanning_claims_by_page.get(physical_page_index)
        if not claims:
            return False

        x1, y1, x2, y2 = physical_coords
        if y1 < 0 or y2 > physical_height:
            return False

        if not (y1 < self.edge_threshold or (physical_height - y2) < self.edge_threshold):
            return False

        cand_area = self._rect_area_xyxy(physical_coords)
        if cand_area <= 1.0:
            return False

        for claim_xyxy in claims:
            overlap = self._rect_intersection_area_xyxy(physical_coords, claim_xyxy)
            if overlap / cand_area >= 0.60:
                return True

        return False

    @staticmethod
    def _patch_area(patch: Dict) -> float:
        bbox = patch.get("bbox")
        if not bbox or len(bbox) < 4:
            return 0.0
        _, _, w, h = bbox
        return max(0.0, float(w)) * max(0.0, float(h))

    @staticmethod
    def _patch_bbox_to_xyxy(patch: Dict) -> List[float]:
        bbox = patch.get("bbox")
        if not bbox or len(bbox) < 4:
            return [0.0, 0.0, 0.0, 0.0]
        x, y, w, h = bbox
        x1 = float(x)
        y1 = float(y)
        return [x1, y1, x1 + float(w), y1 + float(h)]

    def _patches_significantly_overlap(
        self,
        a: Dict,
        b: Dict,
        overlap_threshold: float = 0.70,
    ) -> bool:
        area_a = self._patch_area(a)
        area_b = self._patch_area(b)
        if area_a <= 1.0 or area_b <= 1.0:
            return False

        overlap = self._rect_intersection_area_xyxy(
            self._patch_bbox_to_xyxy(a),
            self._patch_bbox_to_xyxy(b),
        )
        return (overlap / min(area_a, area_b)) >= overlap_threshold

    def _filter_duplicate_patches(
        self,
        existing_patches: List[Dict],
        candidate_patches: List[Dict],
        overlap_threshold: float = 0.70,
    ) -> List[Dict]:
        if not candidate_patches:
            return []

        selected_indices = set()
        dedupe_pool = list(existing_patches)
        ranked_candidates = sorted(
            enumerate(candidate_patches),
            key=lambda item: (-self._patch_area(item[1]), item[0]),
        )

        for idx, patch in ranked_candidates:
            if self._patch_area(patch) <= 1.0:
                continue

            if any(
                self._patches_significantly_overlap(
                    patch,
                    existing_patch,
                    overlap_threshold=overlap_threshold,
                )
                for existing_patch in dedupe_pool
            ):
                continue

            selected_indices.add(idx)
            dedupe_pool.append(patch)

        return [patch for idx, patch in enumerate(candidate_patches) if idx in selected_indices]

    def _merge_virtual_page_results(self, virtual_page_id: str) -> List[TextBlock]:
        """
        Merge results from all chunks that processed this virtual page.
        """
        all_blocks = []
        for chunk_id in self.virtual_page_to_chunks.get(virtual_page_id, []):
            chunk_data = self.virtual_chunk_results.get(chunk_id)
            if chunk_data and "blocks" in chunk_data and virtual_page_id in chunk_data["blocks"]:
                all_blocks.extend(chunk_data["blocks"][virtual_page_id])

        if not all_blocks:
            return []

        merged_blocks = []
        for block in all_blocks:
            is_duplicate = False
            for existing_block in merged_blocks:
                overlap_x = max(
                    0,
                    min(block.xyxy[2], existing_block.xyxy[2])
                    - max(block.xyxy[0], existing_block.xyxy[0]),
                )
                overlap_y = max(
                    0,
                    min(block.xyxy[3], existing_block.xyxy[3])
                    - max(block.xyxy[1], existing_block.xyxy[1]),
                )
                overlap_area = overlap_x * overlap_y

                block_area = (block.xyxy[2] - block.xyxy[0]) * (
                    block.xyxy[3] - block.xyxy[1]
                )
                existing_area = (existing_block.xyxy[2] - existing_block.xyxy[0]) * (
                    existing_block.xyxy[3] - existing_block.xyxy[1]
                )

                overlap_threshold = 0.5
                if overlap_area > overlap_threshold * min(block_area, existing_area):
                    is_duplicate = True
                    if len(block.translation or "") > len(existing_block.translation or ""):
                        existing_block.text = block.text
                        existing_block.translation = block.translation
                        existing_block.xyxy = block.xyxy
                        existing_block.bubble_xyxy = block.bubble_xyxy
                        existing_block.angle = block.angle
                        existing_block.tr_origin_point = block.tr_origin_point
                    break

            if not is_duplicate:
                merged_blocks.append(block)

        return merged_blocks

    def _deduplicate_physical_blocks(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Final deduplication of blocks at the physical page level.
        """
        if not blocks:
            return []

        blocks_with_area = [
            (blk, (blk.xyxy[2] - blk.xyxy[0]) * (blk.xyxy[3] - blk.xyxy[1]))
            for blk in blocks
        ]
        blocks_with_area.sort(key=lambda x: x[1], reverse=True)

        final_blocks = []
        for block, block_area in blocks_with_area:
            is_duplicate = False
            for existing_block in final_blocks:
                overlap_x = max(
                    0,
                    min(block.xyxy[2], existing_block.xyxy[2])
                    - max(block.xyxy[0], existing_block.xyxy[0]),
                )
                overlap_y = max(
                    0,
                    min(block.xyxy[3], existing_block.xyxy[3])
                    - max(block.xyxy[1], existing_block.xyxy[1]),
                )
                overlap_area = overlap_x * overlap_y

                existing_area = (existing_block.xyxy[2] - existing_block.xyxy[0]) * (
                    existing_block.xyxy[3] - existing_block.xyxy[1]
                )

                overlap_threshold = 0.7
                if overlap_area > overlap_threshold * min(block_area, existing_area):
                    is_duplicate = True
                    break

            if not is_duplicate:
                final_blocks.append(block)

        return final_blocks
