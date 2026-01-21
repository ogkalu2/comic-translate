import os
import json
import shutil
import logging
import requests
import traceback
import numpy as np
import imkit as imk
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from PySide6.QtGui import QColor

from modules.detection.processor import TextBlockDetector
from modules.translation.processor import Translator
from modules.utils.textblock import sort_blk_list, TextBlock
from modules.utils.pipeline_config import inpaint_map, get_config
from modules.utils.image_utils import generate_mask, get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.common_utils import is_directory_empty
from modules.utils.translator_utils import format_translations
from modules.rendering.render import is_vertical_block
from modules.utils.archives import make
from modules.rendering.render import get_best_render_area, pyside_word_wrap
from app.ui.canvas.text_item import OutlineInfo, OutlineType
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.save_renderer import ImageSaveRenderer
from modules.utils.translator_utils import format_translations, get_raw_text, get_raw_translation 
from modules.utils.device import resolve_device
from .virtual_page import VirtualPage, VirtualPageCreator, PageStatus

logger = logging.getLogger(__name__)


class WebtoonBatchProcessor:
    """
    Handles batch processing of webtoon translation using virtual pages and overlapping sliding windows.
    Virtual pages allow processing of very long webtoon images in manageable chunks.
    """
    
    def __init__(
            self, 
            main_page, 
            cache_manager, 
            block_detection_handler, 
            inpainting_handler, 
            ocr_handler
        ):
        
        self.main_page = main_page
        self.cache_manager = cache_manager
        # Use shared handlers from the main pipeline
        self.block_detection = block_detection_handler
        self.inpainting = inpainting_handler
        self.ocr_handler = ocr_handler
        
        # Virtual page settings
        self.max_virtual_height = 2000  # Maximum height for virtual pages
        self.overlap_height = 200       # Overlap between virtual pages
        
        # Virtual page management
        self.virtual_page_creator = VirtualPageCreator(
            max_virtual_height=self.max_virtual_height,
            overlap_height=self.overlap_height
        )
        
        # State tracking for virtual chunks
        self.virtual_chunk_results = defaultdict(list)  # chunk_id -> list of results
        self.virtual_page_processing_count = defaultdict(int)  # virtual_page_id -> count
        self.finalized_virtual_pages = set()  # Virtual pages that have been processed
        self.physical_page_results = defaultdict(list)  # physical_page_index -> merged results
        self.physical_page_status = defaultdict(lambda: PageStatus.UNPROCESSED)
        self.final_patches_for_save = defaultdict(list)
        
        # Edge detection settings
        self.edge_threshold = 50  # pixels from edge to consider as "near edge"
        
    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        imk.write_image(os.path.join(path, f"{base_name}_translated{extension}"), image)

    def log_skipped_image(self, directory, timestamp, image_path, reason="", full_traceback=""):
        skipped_file = os.path.join(directory, f"comic_translate_{timestamp}", "skipped_images.txt")
        os.makedirs(os.path.dirname(skipped_file), exist_ok=True)
        with open(skipped_file, 'a', encoding='UTF-8') as file:
            file.write(image_path + "\n")
            file.write(reason + "\n")
            if full_traceback:
                file.write("Full Traceback:\n")
                file.write(full_traceback + "\n")
            file.write("\n")

    def _create_virtual_chunk_image(self, vpage1: VirtualPage, vpage2: VirtualPage) -> Tuple[np.ndarray, List[Dict]]:
        """
        Create a combined image from two virtual pages.
        
        Args:
            vpage1: First virtual page
            vpage2: Second virtual page
            
        Returns:
            Tuple of (combined_image, mapping_data)
        """
        # Handle self-paired virtual pages (single virtual page processing)
        if vpage1.virtual_id == vpage2.virtual_id:
            # Load the physical image
            img = imk.read_image(vpage1.physical_page_path)
            
            if img is None:
                logger.error(f"Failed to load image: {vpage1.physical_page_path}")
                return None, []
            
            # Extract virtual page region
            virtual_img = vpage1.extract_virtual_image(img)
            
            # Create mapping data for single virtual page
            h, w = virtual_img.shape[:2]
            mapping_data = [
                {
                    'virtual_page': vpage1,
                    'physical_page_index': vpage1.physical_page_index,
                    'physical_page_path': vpage1.physical_page_path,
                    'combined_y_start': 0,
                    'combined_y_end': h,
                    'x_offset': 0,
                    'virtual_width': w,
                    'virtual_height': h
                }
            ]
            
            return virtual_img, mapping_data
        
        # Handle different virtual pages (original logic)
        # Load the physical images
        img1 = imk.read_image(vpage1.physical_page_path)
        img2 = imk.read_image(vpage2.physical_page_path)
        
        if img1 is None or img2 is None:
            logger.error(f"Failed to load images: {vpage1.physical_page_path}, {vpage2.physical_page_path}")
            return None, []
        
        # Extract virtual page regions
        virtual_img1 = vpage1.extract_virtual_image(img1)
        virtual_img2 = vpage2.extract_virtual_image(img2)
        
        # Calculate dimensions for combined image
        max_width = max(virtual_img1.shape[1], virtual_img2.shape[1])
        total_height = virtual_img1.shape[0] + virtual_img2.shape[0]
        
        # Create combined image
        combined_image = np.zeros((total_height, max_width, 3), dtype=np.uint8)
        combined_image.fill(255)  # White background
        
        # Place first virtual page
        h1, w1 = virtual_img1.shape[:2]
        x1_offset = (max_width - w1) // 2
        combined_image[0:h1, x1_offset:x1_offset + w1] = virtual_img1
        
        # Place second virtual page
        h2, w2 = virtual_img2.shape[:2]
        x2_offset = (max_width - w2) // 2
        combined_image[h1:h1 + h2, x2_offset:x2_offset + w2] = virtual_img2
        
        # Create mapping data
        mapping_data = [
            {
                'virtual_page': vpage1,
                'physical_page_index': vpage1.physical_page_index,
                'physical_page_path': vpage1.physical_page_path,
                'combined_y_start': 0,
                'combined_y_end': h1,
                'x_offset': x1_offset,
                'virtual_width': w1,
                'virtual_height': h1
            },
            {
                'virtual_page': vpage2,
                'physical_page_index': vpage2.physical_page_index,
                'physical_page_path': vpage2.physical_page_path,
                'combined_y_start': h1,
                'combined_y_end': h1 + h2,
                'x_offset': x2_offset,
                'virtual_width': w2,
                'virtual_height': h2
            }
        ]
        
        return combined_image, mapping_data

    def _detect_edge_blocks_virtual(self, combined_image: np.ndarray, vpage1: VirtualPage, vpage2: VirtualPage) -> Tuple[List[TextBlock], bool]:
        """
        Detect text blocks on virtual page chunk and check for edge blocks.
        
        Args:
            combined_image: Combined image of two virtual pages
            vpage1: First virtual page
            vpage2: Second virtual page
            
        Returns:
            Tuple of (detected_blocks, has_edge_blocks)
        """
        # Run text block detection
        if self.block_detection.block_detector_cache is None:
            self.block_detection.block_detector_cache = TextBlockDetector(self.main_page.settings_page)
        
        blk_list = self.block_detection.block_detector_cache.detect(combined_image)
        
        if not blk_list:
            return [], False
        
        # Check for edge blocks at the boundary between virtual pages
        boundary_y = vpage1.crop_height  # Height of first virtual page in combined image
        
        has_edge_blocks = False
        for blk in blk_list:
            # Check if block spans the virtual page boundary
            if (blk.xyxy[1] < boundary_y and blk.xyxy[3] > boundary_y):
                has_edge_blocks = True
                logger.info(f"Detected text block spanning virtual page boundary: {blk.xyxy}")
                break
            
            # Also check if block is very close to boundary
            elif (abs(blk.xyxy[3] - boundary_y) < self.edge_threshold or 
                  abs(blk.xyxy[1] - boundary_y) < self.edge_threshold):
                has_edge_blocks = True
                logger.info(f"Detected text block near virtual page boundary: {blk.xyxy}")
                break
        
        return blk_list, has_edge_blocks

    def _process_virtual_chunk(self, vpage1: VirtualPage, vpage2: VirtualPage,
                              chunk_id: str, timestamp: str, physical_pages_in_chunk: set, total_images: int) -> Optional[Dict]:
        """
        Process a chunk consisting of two virtual pages.
        Returns a dictionary with blocks and patches keyed by virtual_page_id.

        Args:
            vpage1: First virtual page
            vpage2: Second virtual page
            chunk_id: Unique identifier for this chunk
            timestamp: Timestamp for output directory

        Returns:
            Dictionary containing processed 'blocks' and 'patches', or None.
        """
        logger.info(f"Processing virtual chunk {chunk_id}: {vpage1.virtual_id} + {vpage2.virtual_id}")
        
        # Create combined image
        combined_image, mapping_data = self._create_virtual_chunk_image(vpage1, vpage2)
        if combined_image is None:
            return None

        # Detect blocks and check for boundary issues
        blk_list, has_edge_blocks = self._detect_edge_blocks_virtual(combined_image, vpage1, vpage2)

        # Progress update: Block detection completed
        # Use the minimum physical page index for progress reporting
        current_physical_page = min(physical_pages_in_chunk)
        self.main_page.progress_update.emit(current_physical_page, total_images, 1, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # Early exit if no blocks are found to save processing time
        if not blk_list:
            logger.info(f"No text blocks detected in virtual chunk {chunk_id}")
            # Still need to process inpainting for blockless cleaning
            # So we continue, but the block-related steps will be skipped.
            pass

        # OCR processing (only if blocks exist)
        if blk_list:
            source_lang = self.main_page.image_states[vpage1.physical_page_path]['source_lang']
            self.ocr_handler.ocr.initialize(self.main_page, source_lang)
            try:
                self.ocr_handler.ocr.process(combined_image, blk_list)
                source_lang_english = self.main_page.lang_mapping.get(source_lang, source_lang)
                rtl = True if source_lang_english == 'Japanese' else False
                blk_list = sort_blk_list(blk_list, rtl)
            except Exception as e:
                if isinstance(e, requests.exceptions.HTTPError):
                    try:
                        err_msg = e.response.json().get("error_description", str(e))
                    except Exception:
                        err_msg = str(e)
                else:
                    err_msg = str(e)
                
                logger.exception(f"OCR failed for virtual chunk {chunk_id}: {err_msg}")
                # Emit a signal to the UI for both affected physical pages
                self.main_page.image_skipped.emit(vpage1.physical_page_path, "OCR Chunk Failed", err_msg)
                self.main_page.image_skipped.emit(vpage2.physical_page_path, "OCR Chunk Failed", err_msg)
                blk_list = [] # Clear blocks if OCR fails, so we can still inpaint

        # Progress update: OCR processing completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 2, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # Inpainting processing
        if self.inpainting.inpainter_cache is None or self.inpainting.cached_inpainter_key != self.main_page.settings_page.get_tool_selection('inpainter'):
            backend = 'onnx'
            device = resolve_device(
                self.main_page.settings_page.is_gpu_enabled(),
                backend=backend
            )
            inpainter_key = self.main_page.settings_page.get_tool_selection('inpainter')
            InpainterClass = inpaint_map[inpainter_key]
            self.inpainting.inpainter_cache = InpainterClass(device, backend=backend)
            self.inpainting.cached_inpainter_key = inpainter_key
        
        # Progress update: Inpainting setup completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 3, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None
        
        config = get_config(self.main_page.settings_page)
        mask = generate_mask(combined_image, blk_list)
        inpaint_input_img = self.inpainting.inpainter_cache(combined_image, mask, config)
        inpaint_input_img = imk.convert_scale_abs(inpaint_input_img)
        
        # Progress update: Inpainting execution completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 4, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None
        
        # Calculate inpaint patches for virtual pages (but don't emit yet)
        virtual_page_patches = self._calculate_virtual_inpaint_patches(mask, inpaint_input_img, mapping_data)

        # Progress update: Patch calculation completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 5, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # if blk_list:
        #     get_best_render_area(blk_list, combined_image, inpaint_input_img)

        # Progress update: Pre-translation setup completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 6, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # Translation processing (only if blocks exist)
        if blk_list:
            target_lang = self.main_page.image_states[vpage1.physical_page_path]['target_lang']
            extra_context = self.main_page.settings_page.get_llm_settings()['extra_context']
            translator = Translator(self.main_page, source_lang, target_lang)
            try:
                translator.translate(blk_list, combined_image, extra_context)
            except Exception as e:
                if isinstance(e, requests.exceptions.HTTPError):
                    try:
                        err_msg = e.response.json().get("error_description", str(e))
                    except Exception:
                        err_msg = str(e)
                else:
                    err_msg = str(e)
                    
                logger.exception(f"Translation failed for virtual chunk {chunk_id}: {err_msg}")
                self.main_page.image_skipped.emit(vpage1.physical_page_path, "Translation Chunk Failed", err_msg)
                self.main_page.image_skipped.emit(vpage2.physical_page_path, "Translation Chunk Failed", err_msg)
                # Clear translations on failure
                for blk in blk_list:
                    blk.translation = ""

        # Progress update: Translation processing completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 7, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # Progress update: Text rendering preparation completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 8, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None

        # Convert blocks back to virtual page coordinates
        virtual_page_blocks = self._convert_blocks_to_virtual_coordinates(blk_list, mapping_data)
        
        # Progress update: Block coordinate conversion completed
        self.main_page.progress_update.emit(current_physical_page, total_images, 9, 10, False)
        if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
            return None
        
        if not virtual_page_blocks and not virtual_page_patches:
            logger.info(f"No results (blocks or patches) for virtual chunk {chunk_id}")
            return None

        return {
            'blocks': virtual_page_blocks,
            'patches': virtual_page_patches
        }

    def _convert_blocks_to_virtual_coordinates(self, blk_list: List[TextBlock], 
                                             mapping_data: List[Dict]) -> Dict[str, List[TextBlock]]:
        """
        Convert blocks from combined image coordinates to virtual page coordinates.
        Each block is assigned to only ONE virtual page based on which page it has the most overlap with.
        
        Args:
            blk_list: List of detected text blocks
            mapping_data: Mapping information from virtual chunk creation
            
        Returns:
            Dictionary mapping virtual_page_id -> list of blocks
        """
        virtual_page_blocks = defaultdict(list)
        
        for blk in blk_list:
            # Assign block to the single virtual page with the most overlap area
            target_mapping = None
            max_overlap_area = -1

            for mapping in mapping_data:
                vpage = mapping['virtual_page']
                y_start = mapping['combined_y_start']
                y_end = mapping['combined_y_end']
                
                # Calculate vertical overlap with this virtual page
                overlap_y_start = max(blk.xyxy[1], y_start)
                overlap_y_end = min(blk.xyxy[3], y_end)
                vertical_overlap = max(0, overlap_y_end - overlap_y_start)
                
                # Calculate overlap area
                block_width = blk.xyxy[2] - blk.xyxy[0]
                overlap_area = block_width * vertical_overlap

                if overlap_area > max_overlap_area:
                    max_overlap_area = overlap_area
                    target_mapping = mapping

            # Create a block for the target virtual page only, if one was found
            if target_mapping:
                vpage = target_mapping['virtual_page']
                y_start = target_mapping['combined_y_start']
                x_offset = target_mapping['x_offset']

                # Create a copy for this virtual page
                virtual_block = blk.deep_copy()

                # Convert to virtual page coordinates
                virtual_block.xyxy = [
                    blk.xyxy[0] - x_offset,
                    blk.xyxy[1] - y_start,
                    blk.xyxy[2] - x_offset,
                    blk.xyxy[3] - y_start
                ]
                
                if virtual_block.bubble_xyxy is not None:
                    virtual_block.bubble_xyxy = [
                        blk.bubble_xyxy[0] - x_offset,
                        blk.bubble_xyxy[1] - y_start,
                        blk.bubble_xyxy[2] - x_offset,
                        blk.bubble_xyxy[3] - y_start
                    ]
                
                virtual_page_blocks[vpage.virtual_id].append(virtual_block)
            else:
                logger.warning(f"Block {blk.xyxy} could not be assigned to any virtual page")
            
        return dict(virtual_page_blocks)

    def _calculate_virtual_inpaint_patches(self, mask: np.ndarray, inpainted_image: np.ndarray,
                                           mapping_data: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Create inpaint patches for virtual pages and convert to physical page coordinates.
        This version returns the patches instead of emitting them.

        Args:
            mask: Inpainting mask from combined virtual image
            inpainted_image: Inpainted combined virtual image
            mapping_data: Virtual page mapping information
            
        Returns:
            Dictionary mapping virtual_page_id -> list of patch data dictionaries
        """
        # Find contours in the mask
        contours, _ = imk.find_contours(mask)

        if not contours:
            return {}

        # Group patches by virtual page
        patches_by_virtual_page = defaultdict(list)

        for i, c in enumerate(contours):
            x, y, w, h = imk.bounding_rect(c)
            patch_bottom = y + h

            # Find which virtual page(s) this patch overlaps
            for mapping in mapping_data:
                vpage = mapping['virtual_page']
                y_start = mapping['combined_y_start']
                y_end = mapping['combined_y_end']
                x_offset = mapping['x_offset']

                # Check if patch overlaps with this virtual page
                if not (patch_bottom <= y_start or y >= y_end):
                    # Clip patch to virtual page bounds
                    clip_y_start = max(y, y_start)
                    clip_y_end = min(patch_bottom, y_end)

                    if clip_y_end <= clip_y_start:
                        continue

                    # Extract patch for this virtual page
                    clipped_patch = inpainted_image[clip_y_start:clip_y_end, x:x + w]

                    # Convert to virtual page coordinates
                    virtual_y = clip_y_start - y_start
                    virtual_x = x - x_offset
                    virtual_height = clip_y_end - clip_y_start

                    # Convert to physical page coordinates
                    physical_coords = vpage.virtual_to_physical_coords([
                        virtual_x, virtual_y, virtual_x + w, virtual_y + virtual_height
                    ])

                    physical_x = int(physical_coords[0])
                    physical_y = int(physical_coords[1])
                    physical_width = w
                    physical_height = int(physical_coords[3] - physical_coords[1])

                    # Get the page's vertical position in the webtoon scene
                    webtoon_manager = self.main_page.image_viewer.webtoon_manager
                    page_y_position_in_scene = 0
                    if (webtoon_manager and
                            vpage.physical_page_index < len(webtoon_manager.image_positions)):
                        page_y_position_in_scene = webtoon_manager.image_positions[vpage.physical_page_index]

                    # Scene coordinates account for the page's vertical offset
                    scene_x = physical_x
                    scene_y = physical_y + page_y_position_in_scene

                    # Create patch data
                    patch_data = {
                        'bbox': [physical_x, physical_y, physical_width, physical_height],
                        'image': clipped_patch.copy(),
                        'page_index': vpage.physical_page_index,
                        'file_path': vpage.physical_page_path,
                        'scene_pos': [scene_x, scene_y]
                    }

                    patches_by_virtual_page[vpage.virtual_id].append(patch_data)

        return dict(patches_by_virtual_page)

    def _merge_virtual_page_results(self, virtual_page_id: str) -> List[TextBlock]:
        """
        Merge results from all chunks that processed this virtual page.
        Adapted to read from the new chunk result structure.

        Args:
            virtual_page_id: The virtual page ID to merge results for

        Returns:
            List of merged and deduplicated text blocks
        """
        all_blocks = []

        # Iterate over all chunk results that processed this virtual page
        for chunk_id in self.virtual_page_to_chunks.get(virtual_page_id, []):
            chunk_data = self.virtual_chunk_results.get(chunk_id)
            if chunk_data and 'blocks' in chunk_data and virtual_page_id in chunk_data['blocks']:
                all_blocks.extend(chunk_data['blocks'][virtual_page_id])

        if not all_blocks:
            return []
        
        # Deduplicate blocks based on overlap (logic remains the same)
        merged_blocks = []
        for block in all_blocks:
            is_duplicate = False
            for existing_block in merged_blocks:
                overlap_x = max(0, min(block.xyxy[2], existing_block.xyxy[2]) - max(block.xyxy[0], existing_block.xyxy[0]))
                overlap_y = max(0, min(block.xyxy[3], existing_block.xyxy[3]) - max(block.xyxy[1], existing_block.xyxy[1]))
                overlap_area = overlap_x * overlap_y
                
                block_area = (block.xyxy[2] - block.xyxy[0]) * (block.xyxy[3] - block.xyxy[1])
                existing_area = (existing_block.xyxy[2] - existing_block.xyxy[0]) * (existing_block.xyxy[3] - existing_block.xyxy[1])
                
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
        
        Args:
            blocks: List of blocks in physical coordinates
            
        Returns:
            Deduplicated list of blocks
        """
        if not blocks:
            return []
        
        # Sort blocks by area (larger first) to prioritize keeping larger blocks
        blocks_with_area = [(blk, (blk.xyxy[2] - blk.xyxy[0]) * (blk.xyxy[3] - blk.xyxy[1])) for blk in blocks]
        blocks_with_area.sort(key=lambda x: x[1], reverse=True)
        
        final_blocks = []
        
        for block, block_area in blocks_with_area:
            is_duplicate = False
            
            for existing_block in final_blocks:
                # Check overlap
                overlap_x = max(0, min(block.xyxy[2], existing_block.xyxy[2]) - max(block.xyxy[0], existing_block.xyxy[0]))
                overlap_y = max(0, min(block.xyxy[3], existing_block.xyxy[3]) - max(block.xyxy[1], existing_block.xyxy[1]))
                overlap_area = overlap_x * overlap_y
                
                existing_area = (existing_block.xyxy[2] - existing_block.xyxy[0]) * (existing_block.xyxy[3] - existing_block.xyxy[1])
                
                # Use strict overlap threshold for final deduplication
                overlap_threshold = 0.7
                
                if overlap_area > overlap_threshold * min(block_area, existing_area):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                final_blocks.append(block)
        
        return final_blocks
        
    def _prepare_physical_page_for_render(self, physical_page_index: int, image_path: str,
                                          virtual_pages: List[VirtualPage]):
        """
        Calculates the final, complete block list for a physical page and stores it.
        It no longer handles rendering or text item creation, as that is now done live.
        """
        logger.info(f"Preparing final block list for physical page {physical_page_index}")
        
        # Merge results from all virtual pages belonging to this physical page
        all_physical_blocks = []
        for vpage in virtual_pages:
            # Merge blocks from the chunks that processed this vpage
            merged_virtual_blocks = self._merge_virtual_page_results(vpage.virtual_id)
            
            # Convert these virtual blocks to physical coordinates
            for block in merged_virtual_blocks:
                physical_block = block.deep_copy()
                physical_block.xyxy = vpage.virtual_to_physical_coords(block.xyxy)
                if block.bubble_xyxy:
                    physical_block.bubble_xyxy = vpage.virtual_to_physical_coords(block.bubble_xyxy)
                all_physical_blocks.append(physical_block)
        
        # Final deduplication at the physical page level
        final_blocks = self._deduplicate_physical_blocks(all_physical_blocks)
        
        if not final_blocks:
            logger.warning(f"No final blocks found for physical page {physical_page_index}. Marking for skip.")
            self.main_page.image_states[image_path]['blk_list'] = []
            self.main_page.image_states[image_path]['skip_render'] = True
            return # Stop further processing for this page

        # If we have blocks, clear the skip flag in case it was set previously
        self.main_page.image_states[image_path]['skip_render'] = False

        logger.info(f"Prepared physical page {physical_page_index} with {len(final_blocks)} final blocks.")

        # Format translations for the complete block list
        render_settings = self.main_page.render_settings()
        target_lang = self.main_page.image_states[image_path]['target_lang']
        target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
        trg_lng_cd = get_language_code(target_lang_en)
        format_translations(final_blocks, trg_lng_cd, upper_case=render_settings.upper_case)

        # Language-specific formatting 
        if is_no_space_lang(trg_lng_cd):
            for blk in final_blocks:
                if blk.translation:
                    blk.translation = blk.translation.replace(' ', '')

        # Store the final, complete block list and set the undo stack flag
        self.main_page.image_states[image_path].update({'blk_list': final_blocks})
        if 'viewer_state' in self.main_page.image_states[image_path]:
            self.main_page.image_states[image_path]['viewer_state']['push_to_stack'] = True

    def _emit_and_store_virtual_page_results(self, vpage: VirtualPage, blk_list_virtual: List[TextBlock]):
        """
        Processes blocks for a confirmed virtual page. It performs two actions:
        1. Emits live render signals (`blk_rendered`) to the scene viewer if the parent page is visible.
        2. Creates and stores the final text item data in the page's state for the eventual save.
        This is now the single source of truth for text item creation.
        """
        # Get the state for the parent physical page, creating it if it doesn't exist.
        image_path = vpage.physical_page_path
        page_state = self.main_page.image_states[image_path]
        viewer_state = page_state.setdefault('viewer_state', {})
        text_items_state = viewer_state.setdefault('text_items_state', [])
        page_blk_list = page_state.setdefault('blk_list', [])

        # Check if we should render to the live scene 
        should_emit_live = False
        webtoon_manager = None
        if self.main_page.webtoon_mode:
            webtoon_manager = self.main_page.image_viewer.webtoon_manager
            if vpage.physical_page_index in webtoon_manager.loaded_pages:
                should_emit_live = True

        if should_emit_live:
            logger.info(f"Emitting and storing text items for confirmed virtual page {vpage.virtual_id}")
        else:
            logger.info(f"Storing text items for confirmed virtual page {vpage.virtual_id} (parent not visible)")

        # Prepare render settings
        render_settings = self.main_page.render_settings()
        font, font_color = render_settings.font_family, QColor(render_settings.color)
        max_font_size, min_font_size = render_settings.max_font_size, render_settings.min_font_size
        line_spacing, outline_width = float(render_settings.line_spacing), float(render_settings.outline_width)
        outline_color, outline = QColor(render_settings.outline_color), render_settings.outline
        bold, italic, underline = render_settings.bold, render_settings.italic, render_settings.underline
        alignment = self.main_page.button_to_alignment[render_settings.alignment_id]
        direction = render_settings.direction
        
        # Get target language code for formatting
        target_lang = self.main_page.image_states[image_path]['target_lang']
        target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
        trg_lng_cd = get_language_code(target_lang_en)
        
        page_y_position_in_scene = 0
        if webtoon_manager and vpage.physical_page_index < len(webtoon_manager.image_positions):
            page_y_position_in_scene = webtoon_manager.image_positions[vpage.physical_page_index]

        # Process each block
        for blk_virtual in blk_list_virtual:
            physical_coords = vpage.virtual_to_physical_coords(blk_virtual.xyxy)
            x1, y1, x2, y2 = physical_coords
            width, height = x2 - x1, y2 - y1

            translation = blk_virtual.translation
            if not translation or len(translation) < 1:
                continue

            # Determine if this block should use vertical rendering
            vertical = is_vertical_block(blk_virtual, trg_lng_cd)

            translation, font_size = pyside_word_wrap(
                translation, 
                font, 
                width, 
                height,
                line_spacing, 
                outline_width, 
                bold, 
                italic, 
                underline,
                alignment, 
                direction, 
                max_font_size, 
                min_font_size,
                vertical
            )
            
            if is_no_space_lang(trg_lng_cd):
                translation = translation.replace(' ', '')

            # Smart Color Override
            font_color = get_smart_text_color(blk_virtual.font_color, font_color)

            render_blk = blk_virtual.deep_copy()
            render_blk.xyxy = list(physical_coords)
            if render_blk.bubble_xyxy:
                render_blk.bubble_xyxy = vpage.virtual_to_physical_coords(render_blk.bubble_xyxy)
            
            # Convert to scene coordinates for correct placement
            render_blk.xyxy[1] += page_y_position_in_scene
            render_blk.xyxy[3] += page_y_position_in_scene
            if render_blk.bubble_xyxy:
                render_blk.bubble_xyxy[1] += page_y_position_in_scene
                render_blk.bubble_xyxy[3] += page_y_position_in_scene

            render_blk.translation = translation

            if should_emit_live:
                self.main_page.blk_rendered.emit(translation, font_size, render_blk)
                self.main_page.blk_list.append(render_blk)

            # Store for final save (always do this)
            # Language-specific formatting for State Storage

            # Use TextItemProperties for consistent text item creation
            text_props = TextItemProperties(
                text=translation,
                font_family=font,
                font_size=font_size,
                text_color=font_color,
                alignment=alignment,
                line_spacing=line_spacing,
                outline_color=outline_color,
                outline_width=outline_width,
                bold=bold,
                italic=italic,
                underline=underline,
                position=(x1, y1),
                rotation=blk_virtual.angle,
                scale=1.0,
                transform_origin=blk_virtual.tr_origin_point if blk_virtual.tr_origin_point else (0, 0),
                width=width,
                direction=direction,
                vertical=vertical,
                selection_outlines=[
                    OutlineInfo(
                        0, 
                        len(translation), 
                        outline_color, 
                        outline_width, 
                        OutlineType.Full_Document
                    )
                ] if outline else [],
            )
            text_items_state.append(text_props.to_dict())
            page_blk_list.append(render_blk)

    def _finalize_and_emit_for_virtual_page(self, vpage: VirtualPage):
        """
        Merges results for a confirmed virtual page and emits its patches and
        text items to the live scene viewer.
        """
        virtual_page_id = vpage.virtual_id

        # 1. Merge Blocks for this virtual page
        merged_blocks = self._merge_virtual_page_results(virtual_page_id)

        # 2. Merge Patches for this virtual page
        all_patches = []
        for chunk_id in self.virtual_page_to_chunks.get(virtual_page_id, []):
            chunk_data = self.virtual_chunk_results.get(chunk_id)
            if chunk_data and 'patches' in chunk_data and virtual_page_id in chunk_data['patches']:
                all_patches.extend(chunk_data['patches'][virtual_page_id])

        # 3. Emit Patches to the scene
        if all_patches:
            logger.info(f"Emitting {len(all_patches)} inpaint patches for confirmed VP {virtual_page_id}")
            self.main_page.patches_processed.emit(all_patches, vpage.physical_page_path)
            self.final_patches_for_save[vpage.physical_page_path].extend(all_patches)

        # 4. Handle and Emit Text Items using the new single source of truth
        if merged_blocks:
            self._emit_and_store_virtual_page_results(vpage, merged_blocks)
    
    def _check_and_render_page(self, p_idx: int, total_images: int, image_list: List[str], timestamp: str, physical_to_virtual_mapping: Dict):
        """
        Checks if a page and its neighbors are ready, and if so, prepares, renders, and saves the page.
        """
        # A page is ready to be rendered if its own live data is final, and it hasn't already been rendered.
        if self.physical_page_status.get(p_idx) != PageStatus.LIVE_DATA_FINALIZED:
            return

        # Check neighbor readiness. Neighbors must have at least had their live data finalized.
        # A page at the boundary of the comic (first or last) doesn't need a neighbor on that side.
        prev_page_ready = (p_idx == 0) or (self.physical_page_status.get(p_idx - 1) in [PageStatus.LIVE_DATA_FINALIZED, PageStatus.RENDERED])
        next_page_ready = (p_idx == total_images - 1) or (self.physical_page_status.get(p_idx + 1) in [PageStatus.LIVE_DATA_FINALIZED, PageStatus.RENDERED])

        # If both the page and its neighbors are ready, we can proceed with the final render.
        if prev_page_ready and next_page_ready:
            logger.info(f"Page {p_idx} and its neighbors' states are ready. Proceeding with final render.")
            image_path = image_list[p_idx]
            
            # Ensure virtual pages exist for this index before proceeding.
            virtual_pages = physical_to_virtual_mapping.get(p_idx)
            if not virtual_pages:
                logger.warning(f"Skipping render for page {p_idx} as it has no virtual pages (might have been skipped).")
                self.physical_page_status[p_idx] = PageStatus.RENDERED # Mark as done to avoid re-checking.
                return

            # Prepare the final, consolidated block list needed for the inpainting mask.
            self._prepare_physical_page_for_render(p_idx, image_path, virtual_pages)
            
            # Call the function that handles the final rendering and saving.
            self._save_final_rendered_page(p_idx, image_path, timestamp)

            # Mark the page as fully rendered and saved.
            self.physical_page_status[p_idx] = PageStatus.RENDERED
            logger.info(f"Successfully rendered and saved physical page {p_idx}.")

    def _save_final_rendered_page(self, page_idx: int, image_path: str, timestamp: str):
        """
        A consolidated function that starts with the ORIGINAL image, applies the pre-calculated 
        inpaint patches, renders text (including spanning items), and saves the final output file.
        This is called only when the page and its neighbors have their data ready.
        """
        logger.info(f"Starting final render process for page {page_idx} at path: {image_path}")

        # Start with the ORIGINAL, un-inpainted image.
        image = imk.read_image(image_path)

        if image is None:
            logger.error(f"Failed to load physical image for rendering: {image_path}")
            return

        # Determine the correct save path and names first for all operations
        base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
        extension = os.path.splitext(image_path)[1]
        directory = os.path.dirname(image_path)
        
        archive_bname = ""
        for archive in self.main_page.file_handler.archive_info:
            if image_path in archive['extracted_images']:
                archive_path = archive['archive_path']
                directory = os.path.dirname(archive_path)
                archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                break
        
        # Check if the page should be skipped due to no text blocks
        if self.main_page.image_states[image_path].get('skip_render'):
            logger.info(f"Skipping final render for page {page_idx}, copying original.")
            reason = "No text blocks detected or processed successfully."
            self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
            self.log_skipped_image(directory, timestamp, image_path, reason)
            return
        
        renderer = ImageSaveRenderer(image)
        patches = self.final_patches_for_save.get(image_path, [])
        renderer.apply_patches(patches)

        # Intermediate Exports
        settings_page = self.main_page.settings_page
        export_settings = settings_page.get_export_settings()

        # Export Cleaned Image
        if export_settings['export_inpainted_image']:
            path = os.path.join(directory, f"comic_translate_{timestamp}", "cleaned_images", archive_bname)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            # The image on the renderer is inpainted but has no text yet. Perfect time to save.
            cleaned_image_rgb = renderer.render_to_image()  # Already in RGB format
            imk.write_image(os.path.join(path, f"{base_name}_cleaned{extension}"), cleaned_image_rgb)

        # Get final block list for text exports
        blk_list = self.main_page.image_states[image_path].get('blk_list', [])

        # Export Raw Text
        if export_settings['export_raw_text'] and blk_list:
            path = os.path.join(directory, f"comic_translate_{timestamp}", "raw_texts", archive_bname)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            raw_text = get_raw_text(blk_list)
            with open(os.path.join(path, f"{base_name}_raw.txt"), 'w', encoding='UTF-8') as f:
                f.write(raw_text)

        # Export Translated Text
        if export_settings['export_translated_text'] and blk_list:
            path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_texts", archive_bname)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            translated_text = get_raw_translation(blk_list)
            with open(os.path.join(path, f"{base_name}_translated.txt"), 'w', encoding='UTF-8') as f:
                f.write(translated_text)

        # Continue Image Rendering
        viewer_state = self.main_page.image_states[image_path].get('viewer_state', {}).copy()
        renderer.add_state_to_image(viewer_state, page_idx, self.main_page)
        render_save_dir = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
        if not os.path.exists(render_save_dir):
            os.makedirs(render_save_dir, exist_ok=True)
        sv_pth = os.path.join(render_save_dir, f"{base_name}_translated{extension}")
        renderer.save_image(sv_pth)
        logger.info(f"Saved final rendered page: {sv_pth}")

    def webtoon_batch_process(self, selected_paths: List[str] = None):
        """
        Main webtoon batch processing method. Saves physical pages as soon as they
        and their neighbors' live data is finalized, allowing for correct handling
        of spanning text items.
        """
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        image_list = selected_paths if selected_paths is not None else self.main_page.image_files
        total_images = len(image_list)

        if total_images < 1:
            logger.warning("No images to process")
            return

        logger.info(f"Starting EAGER webtoon batch processing for {total_images} images with spanning item support.")

        # Reset and Initialize State
        self.virtual_chunk_results.clear()
        self.virtual_page_processing_count.clear()
        self.finalized_virtual_pages.clear()
        self.physical_page_status.clear()
        self.processed_chunks = set()
        self.virtual_page_to_chunks = defaultdict(list)

        # Step 1: Create virtual pages for all physical pages
        all_virtual_pages = []
        physical_to_virtual_mapping = {}
        for physical_idx, image_path in enumerate(image_list):
            state = self.main_page.image_states.get(image_path, {})
            if state.get('skip', False):
                logger.info(f"Skipping physical page {physical_idx} due to user setting.")
                self.physical_page_status[physical_idx] = PageStatus.RENDERED # Mark as done

                # Find archive info for correct save path
                base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
                extension = os.path.splitext(image_path)[1]
                directory = os.path.dirname(image_path)
                archive_bname = ""
                for archive in self.main_page.file_handler.archive_info:
                    if image_path in archive['extracted_images']:
                        archive_path = archive['archive_path']
                        directory = os.path.dirname(archive_path)
                        archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                        break
                
                image = imk.read_image(image_path)
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.log_skipped_image(directory, timestamp, image_path, "User-skipped")
                continue
            
            image = imk.read_image(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                continue
            
            virtual_pages = self.virtual_page_creator.create_virtual_pages(physical_idx, image_path, image)
            all_virtual_pages.extend(virtual_pages)
            physical_to_virtual_mapping[physical_idx] = virtual_pages

        if not all_virtual_pages:
            logger.error("No virtual pages were created from the provided images.")
            return

        # Step 2: Create virtual chunk pairs and lookup maps
        virtual_chunk_pairs = self.virtual_page_creator.get_virtual_chunk_pairs(all_virtual_pages)
        for chunk_idx, (vpage1, vpage2) in enumerate(virtual_chunk_pairs):
            chunk_id = f"chunk_{chunk_idx}_{vpage1.virtual_id}_{vpage2.virtual_id}"
            self.virtual_page_to_chunks[vpage1.virtual_id].append(chunk_id)
            # Only add for vpage2 if it's different from vpage1 (avoid duplicates in self-paired chunks)
            if vpage1.virtual_id != vpage2.virtual_id:
                self.virtual_page_to_chunks[vpage2.virtual_id].append(chunk_id)
        
        total_chunks = len(virtual_chunk_pairs)
        logger.info(f"Created {len(all_virtual_pages)} virtual pages and {total_chunks} chunks to process.")

        # Track progress per physical page
        physical_page_first_chunk = {}  # physical_idx -> first chunk_idx for that page
        physical_page_last_chunk = {}   # physical_idx -> last chunk_idx for that page
        current_physical_pages = set()  # Track which physical pages are currently being processed
        
        # Build mapping of physical pages to their first and last chunks
        for chunk_idx, (vpage1, vpage2) in enumerate(virtual_chunk_pairs):
            physical_pages_in_chunk = {vpage1.physical_page_index, vpage2.physical_page_index}
            for p_idx in physical_pages_in_chunk:
                if p_idx not in physical_page_first_chunk:
                    physical_page_first_chunk[p_idx] = chunk_idx
                physical_page_last_chunk[p_idx] = chunk_idx

        # Step 3: Process chunks and progressively finalize/render pages
        for chunk_idx, (vpage1, vpage2) in enumerate(virtual_chunk_pairs):
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                break
            
            chunk_id = f"chunk_{chunk_idx}_{vpage1.virtual_id}_{vpage2.virtual_id}"
            
            # Determine which physical pages are involved in this chunk
            physical_pages_in_chunk = {vpage1.physical_page_index, vpage2.physical_page_index}
            
            # Check if this is the first chunk for any physical page
            is_first_chunk_for_any_page = any(physical_page_first_chunk[p_idx] == chunk_idx for p_idx in physical_pages_in_chunk)
            
            # If this is the first chunk for a physical page, emit progress with name change
            if is_first_chunk_for_any_page:
                # Find which physical page is starting (use the lowest index if multiple)
                starting_page = min(p_idx for p_idx in physical_pages_in_chunk if physical_page_first_chunk[p_idx] == chunk_idx)
                self.main_page.progress_update.emit(starting_page, total_images, 0, 10, True)
                current_physical_pages.add(starting_page)

            try:
                chunk_results = self._process_virtual_chunk(vpage1, vpage2, chunk_id, timestamp, physical_pages_in_chunk, total_images)
                if chunk_results:
                    self.virtual_chunk_results[chunk_id] = chunk_results
                self.processed_chunks.add(chunk_id)
            except Exception as e:
                logger.exception(f"Error processing virtual chunk {chunk_id}: {e}", exc_info=True)
                self.processed_chunks.add(chunk_id)

            # Live UI and State Finalization Logic
            newly_finalized_physical_pages = set()

            # Check if any virtual pages are now confirmed (all their chunks are processed)
            # Use set to avoid processing the same virtual page twice in self-paired chunks
            unique_vpages = {vpage1.virtual_id: vpage1, vpage2.virtual_id: vpage2}
            for vpage in unique_vpages.values():
                if vpage.virtual_id in self.finalized_virtual_pages:
                    continue
                
                required_chunks = self.virtual_page_to_chunks[vpage.virtual_id]
                if all(c_id in self.processed_chunks for c_id in required_chunks):
                    # Finalize the virtual page for live UI emission
                    self._finalize_and_emit_for_virtual_page(vpage)
                    self.finalized_virtual_pages.add(vpage.virtual_id)

                    # Now, check if this confirmation completes a PHYSICAL page's live data
                    p_idx = vpage.physical_page_index
                    if self.physical_page_status.get(p_idx, PageStatus.UNPROCESSED) == PageStatus.UNPROCESSED:
                        vpages_for_physical = physical_to_virtual_mapping.get(p_idx, [])
                        if all(vp.virtual_id in self.finalized_virtual_pages for vp in vpages_for_physical):
                            logger.info(f"All live data for physical page {p_idx} is now finalized.")
                            self.physical_page_status[p_idx] = PageStatus.LIVE_DATA_FINALIZED
                            newly_finalized_physical_pages.add(p_idx)

            # Trigger Render Check for newly finalized pages and their neighbors
            pages_to_check_for_render = set(newly_finalized_physical_pages)
            for p_idx in newly_finalized_physical_pages:
                if p_idx > 0:
                    pages_to_check_for_render.add(p_idx - 1)
                if p_idx < total_images - 1:
                    pages_to_check_for_render.add(p_idx + 1)
            
            for p_idx in sorted(list(pages_to_check_for_render)):
                self._check_and_render_page(p_idx, total_images, image_list, timestamp, physical_to_virtual_mapping)

            # Check if any physical pages are now completely finished (last chunk processed)
            for p_idx in physical_pages_in_chunk:
                # Check if this was the last chunk for this physical page
                if physical_page_last_chunk[p_idx] == chunk_idx:
                    # Emit final progress for this physical page
                    self.main_page.progress_update.emit(p_idx, total_images, 10, 10, False)
                    logger.info(f"Physical page {p_idx} processing completed (last chunk: {chunk_idx})")

        # Final Cleanup Loop (Safety Net)
        logger.info("Main processing loop finished. Running final cleanup render check for any remaining pages.")
        for p_idx in range(total_images):
            if self.physical_page_status.get(p_idx) == PageStatus.LIVE_DATA_FINALIZED:
                self._check_and_render_page(p_idx, total_images, image_list, timestamp, physical_to_virtual_mapping)

        # Step 4: Handle archive creation
        archive_info_list = self.main_page.file_handler.archive_info
        if archive_info_list:
            save_as_settings = self.main_page.settings_page.get_export_settings()['save_as']
            for archive_index, archive in enumerate(archive_info_list):
                archive_index_input = total_images + archive_index

                self.main_page.progress_update.emit(archive_index_input, total_images, 1, 3, True)
                if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                    self.main_page.current_worker = None
                    break

                archive_path = archive['archive_path']
                archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                archive_directory = os.path.dirname(archive_path)
                archive_ext = os.path.splitext(archive_path)[1]
                save_as_ext = f".{save_as_settings.get(archive_ext.lower(), 'cbz')}"

                save_dir = os.path.join(archive_directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
                check_from = os.path.join(archive_directory, f"comic_translate_{timestamp}")

                if not os.path.exists(save_dir) or is_directory_empty(save_dir):
                    logger.warning(f"Skipping archive creation for {archive_bname} as its render directory is empty.")
                    continue

                self.main_page.progress_update.emit(archive_index_input, total_images, 2, 3, True)
                if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                    self.main_page.current_worker = None
                    break

                output_base_name = f"{archive_bname}"
                make(save_as_ext=save_as_ext, input_dir=save_dir, output_dir=archive_directory, output_base_name=output_base_name)

                self.main_page.progress_update.emit(archive_index_input, total_images, 3, 3, True)
                if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                    self.main_page.current_worker = None
                    break

                if os.path.exists(save_dir):
                    shutil.rmtree(save_dir)
                if os.path.exists(check_from) and is_directory_empty(check_from):
                    shutil.rmtree(check_from)
        
        logger.info("Eager webtoon batch processing completed.")