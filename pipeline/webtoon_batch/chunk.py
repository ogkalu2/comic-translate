import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import imkit as imk
import numpy as np
import requests
from PySide6.QtCore import QCoreApplication

from app.path_materialization import ensure_path_materialized
from app.ui.messages import Messages
from modules.detection.processor import TextBlockDetector
from modules.translation.processor import Translator
from modules.utils.device import resolve_device
from modules.utils.exceptions import InsufficientCreditsException
from modules.utils.image_utils import generate_mask
from modules.utils.pipeline_config import get_config, inpaint_map
from modules.utils.textblock import TextBlock, sort_blk_list
from ..virtual_page import VirtualPage

logger = logging.getLogger(__name__)


class ChunkMixin:
    @staticmethod
    def _union_xyxy(a: List[float], b: List[float]) -> List[float]:
        return [
            min(float(a[0]), float(b[0])),
            min(float(a[1]), float(b[1])),
            max(float(a[2]), float(b[2])),
            max(float(a[3]), float(b[3])),
        ]

    def _merge_seam_split_blocks(
        self, blk_list: List[TextBlock], boundary_y: float
    ) -> List[TextBlock]:
        """
        Merge top+bottom partial detections around the chunk seam into one block.
        This runs before OCR so downstream stages see a single logical block.
        """
        if len(blk_list) < 2:
            return blk_list

        edge = float(self.edge_threshold)
        max_vertical_gap = max(20.0, edge * 1.4)
        max_width_ratio = 3.5

        top_candidates = []
        bottom_candidates = []
        for idx, blk in enumerate(blk_list):
            x1, y1, x2, y2 = [float(v) for v in blk.xyxy]
            if y2 <= boundary_y + edge and y1 < boundary_y:
                top_candidates.append((idx, x1, y1, x2, y2))
            if y1 >= boundary_y - edge and y2 > boundary_y:
                bottom_candidates.append((idx, x1, y1, x2, y2))

        if not top_candidates or not bottom_candidates:
            return blk_list

        candidate_pairs = []
        for top_idx, tx1, ty1, tx2, ty2 in top_candidates:
            top_w = max(1.0, tx2 - tx1)
            top_cx = (tx1 + tx2) / 2.0
            for bot_idx, bx1, by1, bx2, by2 in bottom_candidates:
                if top_idx == bot_idx:
                    continue

                bot_w = max(1.0, bx2 - bx1)
                bot_cx = (bx1 + bx2) / 2.0
                width_ratio = max(top_w, bot_w) / max(1.0, min(top_w, bot_w))
                if width_ratio > max_width_ratio:
                    continue

                vertical_gap = max(0.0, by1 - ty2)
                if vertical_gap > max_vertical_gap:
                    continue

                inter_x = max(0.0, min(tx2, bx2) - max(tx1, bx1))
                overlap_ratio = inter_x / max(1.0, min(top_w, bot_w))
                center_delta = abs(top_cx - bot_cx)
                if overlap_ratio < 0.45 and center_delta > 0.35 * max(top_w, bot_w):
                    continue

                seam_distance = abs(boundary_y - ty2) + abs(by1 - boundary_y)
                score = (
                    (2.5 * overlap_ratio)
                    - (vertical_gap / max(1.0, edge))
                    - (seam_distance / max(1.0, 2.0 * edge))
                    - (0.30 * abs(width_ratio - 1.0))
                )
                candidate_pairs.append((score, top_idx, bot_idx))

        if not candidate_pairs:
            return blk_list

        used_indices = set()
        merged_blocks = []
        for score, top_idx, bot_idx in sorted(candidate_pairs, key=lambda x: x[0], reverse=True):
            if score < 0:
                continue
            if top_idx in used_indices or bot_idx in used_indices:
                continue

            top_blk = blk_list[top_idx]
            bot_blk = blk_list[bot_idx]
            merged_blk = top_blk.deep_copy()
            merged_blk.xyxy = self._union_xyxy(top_blk.xyxy, bot_blk.xyxy)

            top_bubble = top_blk.bubble_xyxy
            bot_bubble = bot_blk.bubble_xyxy
            if top_bubble is not None and bot_bubble is not None:
                merged_blk.bubble_xyxy = self._union_xyxy(top_bubble, bot_bubble)
            elif bot_bubble is not None:
                merged_blk.bubble_xyxy = list(bot_bubble)

            used_indices.add(top_idx)
            used_indices.add(bot_idx)
            merged_blocks.append(merged_blk)

        if not merged_blocks:
            return blk_list

        merged_result = [
            blk for idx, blk in enumerate(blk_list) if idx not in used_indices
        ]
        merged_result.extend(merged_blocks)
        logger.info(
            "Merged %d seam-split block pairs around boundary y=%s",
            len(merged_blocks),
            boundary_y,
        )
        return merged_result

    def _create_virtual_chunk_image(
        self, vpage1: VirtualPage, vpage2: VirtualPage
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Create a combined image from two virtual pages.
        """
        # Handle self-paired virtual pages (single virtual page processing).
        if vpage1.virtual_id == vpage2.virtual_id:
            ensure_path_materialized(vpage1.physical_page_path)
            img = imk.read_image(vpage1.physical_page_path)

            if img is None:
                logger.error("Failed to load image: %s", vpage1.physical_page_path)
                return None, []

            virtual_img = vpage1.extract_virtual_image(img)
            h, w = virtual_img.shape[:2]
            mapping_data = [
                {
                    "virtual_page": vpage1,
                    "physical_page_index": vpage1.physical_page_index,
                    "physical_page_path": vpage1.physical_page_path,
                    "combined_y_start": 0,
                    "combined_y_end": h,
                    "x_offset": 0,
                    "virtual_width": w,
                    "virtual_height": h,
                }
            ]
            return virtual_img, mapping_data

        # Handle different virtual pages by stacking them into one combined chunk image.
        ensure_path_materialized(vpage1.physical_page_path)
        img1 = imk.read_image(vpage1.physical_page_path)
        ensure_path_materialized(vpage2.physical_page_path)
        img2 = imk.read_image(vpage2.physical_page_path)

        if img1 is None or img2 is None:
            logger.error(
                "Failed to load images: %s, %s",
                vpage1.physical_page_path,
                vpage2.physical_page_path,
            )
            return None, []

        virtual_img1 = vpage1.extract_virtual_image(img1)
        virtual_img2 = vpage2.extract_virtual_image(img2)

        max_width = max(virtual_img1.shape[1], virtual_img2.shape[1])
        total_height = virtual_img1.shape[0] + virtual_img2.shape[0]

        combined_image = np.zeros((total_height, max_width, 3), dtype=np.uint8)
        combined_image.fill(255)

        h1, w1 = virtual_img1.shape[:2]
        x1_offset = (max_width - w1) // 2
        combined_image[0:h1, x1_offset : x1_offset + w1] = virtual_img1

        h2, w2 = virtual_img2.shape[:2]
        x2_offset = (max_width - w2) // 2
        combined_image[h1 : h1 + h2, x2_offset : x2_offset + w2] = virtual_img2

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
        self, combined_image: np.ndarray, vpage1: VirtualPage, vpage2: VirtualPage
    ) -> Tuple[List[TextBlock], bool]:
        """
        Detect text blocks on virtual page chunk and check for edge blocks.
        """
        if self.block_detection.block_detector_cache is None:
            self.block_detection.block_detector_cache = TextBlockDetector(
                self.main_page.settings_page
            )

        # Run text block detection once on the combined chunk image.
        blk_list = self.block_detection.block_detector_cache.detect(combined_image)
        if not blk_list:
            return [], False

        # Check if any blocks span or land near the seam between the two virtual pages.
        boundary_y = vpage1.crop_height
        has_edge_blocks = False
        for blk in blk_list:
            if blk.xyxy[1] < boundary_y and blk.xyxy[3] > boundary_y:
                has_edge_blocks = True
                logger.info(
                    "Detected text block spanning virtual page boundary: %s", blk.xyxy
                )
                break
            if (
                abs(blk.xyxy[3] - boundary_y) < self.edge_threshold
                or abs(blk.xyxy[1] - boundary_y) < self.edge_threshold
            ):
                has_edge_blocks = True
                logger.info(
                    "Detected text block near virtual page boundary: %s", blk.xyxy
                )
                break

        return blk_list, has_edge_blocks

    def _process_virtual_chunk(
        self,
        vpage1: VirtualPage,
        vpage2: VirtualPage,
        chunk_id: str,
        timestamp: str,
        physical_pages_in_chunk: set,
        total_images: int,
    ) -> Optional[Dict]:
        """
        Process a chunk consisting of two virtual pages.
        Returns a dictionary with blocks and patches keyed by virtual_page_id.
        """
        logger.info(
            "Processing virtual chunk %s: %s + %s",
            chunk_id,
            vpage1.virtual_id,
            vpage2.virtual_id,
        )

        # Create combined image and mapping metadata for this chunk pair.
        combined_image, mapping_data = self._create_virtual_chunk_image(vpage1, vpage2)
        if combined_image is None:
            return None

        # Detect blocks and seam-edge conditions.
        blk_list, has_edge_blocks = self._detect_edge_blocks_virtual(
            combined_image, vpage1, vpage2
        )
        if (
            blk_list
            and has_edge_blocks
            and len(mapping_data) == 2
            and vpage1.virtual_id != vpage2.virtual_id
        ):
            before_merge = len(blk_list)
            boundary_y = mapping_data[0]["combined_y_end"]
            blk_list = self._merge_seam_split_blocks(blk_list, boundary_y)
            after_merge = len(blk_list)
            if after_merge != before_merge:
                logger.info(
                    "Chunk %s seam merge adjusted block count from %d to %d.",
                    chunk_id,
                    before_merge,
                    after_merge,
                )

        current_physical_page = min(physical_pages_in_chunk)
        self.main_page.progress_update.emit(
            current_physical_page, total_images, 1, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        if not blk_list:
            logger.info("No text blocks detected in virtual chunk %s", chunk_id)

        if blk_list:
            source_lang = self.main_page.image_states[vpage1.physical_page_path][
                "source_lang"
            ]
            self.ocr_handler.ocr.initialize(self.main_page, source_lang)
            try:
                self.ocr_handler.ocr.process(combined_image, blk_list)
                source_lang_english = self.main_page.lang_mapping.get(
                    source_lang, source_lang
                )
                rtl = True if source_lang_english == "Japanese" else False
                blk_list = sort_blk_list(blk_list, rtl)
            except InsufficientCreditsException:
                raise
            except Exception as e:
                if isinstance(e, requests.exceptions.ConnectionError):
                    err_msg = QCoreApplication.translate(
                        "Messages",
                        "Unable to connect to the server.\nPlease check your internet connection.",
                    )
                elif isinstance(e, requests.exceptions.HTTPError):
                    status_code = e.response.status_code if e.response is not None else 500
                    if status_code >= 500:
                        err_msg = Messages.get_server_error_text(status_code, context="ocr")
                    else:
                        try:
                            err_json = e.response.json()
                            if "detail" in err_json and isinstance(err_json["detail"], dict):
                                err_msg = err_json["detail"].get(
                                    "error_description", str(e)
                                )
                            else:
                                err_msg = err_json.get("error_description", str(e))
                        except Exception:
                            err_msg = str(e)
                else:
                    err_msg = str(e)

                logger.exception("OCR failed for virtual chunk %s: %s", chunk_id, err_msg)
                self.main_page.image_skipped.emit(
                    vpage1.physical_page_path, "OCR Chunk Failed", err_msg
                )
                self.main_page.image_skipped.emit(
                    vpage2.physical_page_path, "OCR Chunk Failed", err_msg
                )
                # Keep chunk flow alive for inpainting-only output.
                blk_list = []

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 2, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        if (
            self.inpainting.inpainter_cache is None
            or self.inpainting.cached_inpainter_key
            != self.main_page.settings_page.get_tool_selection("inpainter")
        ):
            backend = "onnx"
            device = resolve_device(
                self.main_page.settings_page.is_gpu_enabled(), backend=backend
            )
            inpainter_key = self.main_page.settings_page.get_tool_selection("inpainter")
            InpainterClass = inpaint_map[inpainter_key]
            self.inpainting.inpainter_cache = InpainterClass(device, backend=backend)
            self.inpainting.cached_inpainter_key = inpainter_key

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 3, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        config = get_config(self.main_page.settings_page)
        mask = generate_mask(combined_image, blk_list)
        inpaint_input_img = self.inpainting.inpainter_cache(combined_image, mask, config)
        inpaint_input_img = imk.convert_scale_abs(inpaint_input_img)

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 4, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # Calculate inpaint patches per virtual page but defer emission until page finalization.
        virtual_page_patches = self._calculate_virtual_inpaint_patches(
            mask, inpaint_input_img, mapping_data
        )

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 5, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 6, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        if blk_list:
            target_lang = self.main_page.image_states[vpage1.physical_page_path][
                "target_lang"
            ]
            extra_context = self.main_page.settings_page.get_llm_settings()[
                "extra_context"
            ]
            translator = Translator(self.main_page, source_lang, target_lang)
            try:
                translator.translate(blk_list, combined_image, extra_context)
            except InsufficientCreditsException:
                raise
            except Exception as e:
                if isinstance(e, requests.exceptions.ConnectionError):
                    err_msg = QCoreApplication.translate(
                        "Messages",
                        "Unable to connect to the server.\nPlease check your internet connection.",
                    )
                elif isinstance(e, requests.exceptions.HTTPError):
                    status_code = e.response.status_code if e.response is not None else 500
                    if status_code >= 500:
                        err_msg = Messages.get_server_error_text(
                            status_code, context="translation"
                        )
                    else:
                        try:
                            err_json = e.response.json()
                            if "detail" in err_json and isinstance(err_json["detail"], dict):
                                err_msg = err_json["detail"].get(
                                    "error_description", str(e)
                                )
                            else:
                                err_msg = err_json.get("error_description", str(e))
                        except Exception:
                            err_msg = str(e)
                else:
                    err_msg = str(e)

                logger.exception(
                    "Translation failed for virtual chunk %s: %s", chunk_id, err_msg
                )
                self.main_page.image_skipped.emit(
                    vpage1.physical_page_path, "Translation Chunk Failed", err_msg
                )
                self.main_page.image_skipped.emit(
                    vpage2.physical_page_path, "Translation Chunk Failed", err_msg
                )
                for blk in blk_list:
                    blk.translation = ""

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 7, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 8, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        virtual_page_blocks = self._convert_blocks_to_virtual_coordinates(
            blk_list, mapping_data
        )

        self.main_page.progress_update.emit(
            current_physical_page, total_images, 9, 10, False
        )
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        if not virtual_page_blocks and not virtual_page_patches:
            logger.info("No results (blocks or patches) for virtual chunk %s", chunk_id)
            return None

        return {"blocks": virtual_page_blocks, "patches": virtual_page_patches}

    def _convert_blocks_to_virtual_coordinates(
        self, blk_list: List[TextBlock], mapping_data: List[Dict]
    ) -> Dict[str, List[TextBlock]]:
        """
        Convert blocks from combined image coordinates to virtual page coordinates.
        """
        virtual_page_blocks = defaultdict(list)

        for blk in blk_list:
            # Prefer stable ownership for blocks that cross the chunk seam:
            # assign spanning blocks to the upper mapping entry.
            target_mapping = None
            if len(mapping_data) == 2:
                boundary_y = mapping_data[0]["combined_y_end"]
                if blk.xyxy[1] < boundary_y and blk.xyxy[3] > boundary_y:
                    target_mapping = mapping_data[0]

            # Otherwise assign to the virtual page with maximum overlap area.
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
                    "Block %s could not be assigned to any virtual page", blk.xyxy
                )

        return dict(virtual_page_blocks)

    def _calculate_virtual_inpaint_patches(
        self, mask: np.ndarray, inpainted_image: np.ndarray, mapping_data: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Create inpaint patches for virtual pages and convert to physical page coordinates.
        """
        # Find contours in the inpaint mask to build patch rectangles.
        contours, _ = imk.find_contours(mask)
        if not contours:
            return {}

        patches_by_virtual_page = defaultdict(list)
        for c in contours:
            x, y, w, h = imk.bounding_rect(c)
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

                clipped_patch = inpainted_image[clip_y_start:clip_y_end, x : x + w]
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
