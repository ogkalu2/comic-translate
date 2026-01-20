import logging
from typing import List
from PySide6 import QtCore

from modules.detection.processor import TextBlockDetector
from modules.utils.textblock import TextBlock, sort_blk_list
from modules.rendering.render import get_best_render_area
from pipeline.webtoon_utils import get_first_visible_block


logger = logging.getLogger(__name__)


class BlockDetectionHandler:
    """Handles text block detection and coordinate loading."""
    
    def __init__(self, main_page):
        self.main_page = main_page
        self.block_detector_cache = None

    def load_box_coords(self, blk_list: List[TextBlock]):
        # Clear rectangles appropriately based on mode
        if self.main_page.webtoon_mode:
            self.main_page.image_viewer.clear_rectangles_in_visible_area()
        else:
            self.main_page.image_viewer.clear_rectangles()
            
        if self.main_page.image_viewer.hasPhoto() and blk_list:
            for blk in blk_list:
                x1, y1, x2, y2 = blk.xyxy
                rect = QtCore.QRectF(0, 0, x2 - x1, y2 - y1)
                transform_origin = QtCore.QPointF(*blk.tr_origin_point) if blk.tr_origin_point else None
                
                # Use the new add_rectangle method for consistent handling
                rect_item = self.main_page.image_viewer.add_rectangle(
                    rect, QtCore.QPointF(x1, y1), blk.angle, transform_origin
                )
                self.main_page.connect_rect_item_signals(rect_item)

            # In webtoon mode, use first visible block instead of just first block
            if self.main_page.webtoon_mode:
                first_block = get_first_visible_block(self.main_page.blk_list, self.main_page.image_viewer)
                if first_block is None:
                    first_block = self.main_page.blk_list[0]  # Fallback to first block if no visible blocks
            else:
                first_block = self.main_page.blk_list[0]
            
            rect = self.main_page.rect_item_ctrl.find_corresponding_rect(first_block, 0.5)
            self.main_page.image_viewer.select_rectangle(rect)
            self.main_page.set_tool('box')

    def detect_blocks(self, load_rects=True):
        if self.main_page.image_viewer.hasPhoto():
            if self.block_detector_cache is None:
                self.block_detector_cache = TextBlockDetector(self.main_page.settings_page)
            
            # In webtoon mode, detect text only in the currently visible area
            if self.main_page.webtoon_mode:
                # Get the visible area image and its page mappings
                image, page_mappings = self.main_page.image_viewer.get_visible_area_image()
                if image is None:
                    return [], load_rects, None
                
                blk_list = self.block_detector_cache.detect(image)

                # Optimize render area immediately after detection (on local visible coordinates)
                if blk_list:
                    get_best_render_area(blk_list, image)
                
                # Convert coordinates from visible area to scene coordinates
                for blk in blk_list:
                    x1, y1, x2, y2 = blk.xyxy
                    
                    # Find which page mapping this text block belongs to
                    for mapping in page_mappings:
                        if mapping['combined_y_start'] <= y1 < mapping['combined_y_end']:
                            # Convert from combined image coordinates to page coordinates
                            page_y1 = y1 - mapping['combined_y_start'] + mapping['page_crop_top']
                            page_y2 = y2 - mapping['combined_y_start'] + mapping['page_crop_top']
                            
                            # Convert from page coordinates to scene coordinates
                            page_index = mapping['page_index']
                            scene_pos_tl = self.main_page.image_viewer.page_to_scene_coordinates(
                                page_index, QtCore.QPointF(x1, page_y1)
                            )
                            scene_pos_br = self.main_page.image_viewer.page_to_scene_coordinates(
                                page_index, QtCore.QPointF(x2, page_y2)
                            )
                            
                            # Update the block coordinates
                            blk.xyxy = [scene_pos_tl.x(), scene_pos_tl.y(), scene_pos_br.x(), scene_pos_br.y()]
                            
                            # Also update bubble_xyxy if present
                            if blk.bubble_xyxy is not None:
                                bx1, by1, bx2, by2 = blk.bubble_xyxy
                                bubble_page_y1 = by1 - mapping['combined_y_start'] + mapping['page_crop_top']
                                bubble_page_y2 = by2 - mapping['combined_y_start'] + mapping['page_crop_top']
                                bubble_scene_pos_tl = self.main_page.image_viewer.page_to_scene_coordinates(
                                    page_index, QtCore.QPointF(bx1, bubble_page_y1)
                                )
                                bubble_scene_pos_br = self.main_page.image_viewer.page_to_scene_coordinates(
                                    page_index, QtCore.QPointF(bx2, bubble_page_y2)
                                )
                                blk.bubble_xyxy = [
                                    bubble_scene_pos_tl.x(), bubble_scene_pos_tl.y(),
                                    bubble_scene_pos_br.x(), bubble_scene_pos_br.y()
                                ]
                            break
                
                return blk_list, load_rects, page_mappings
            else:
                # Regular single image mode
                current_page = None
                image = self.main_page.image_viewer.get_image_array()
                blk_list = self.block_detector_cache.detect(image)
                if blk_list:
                    get_best_render_area(blk_list, image)
                return blk_list, load_rects, current_page

    def on_blk_detect_complete(self, result): 
        blk_list, load_rects, page_mappings_or_current_page = result
        
        # Handle webtoon mode with visible area detection
        if self.main_page.webtoon_mode and isinstance(page_mappings_or_current_page, list):
            # page_mappings_or_current_page is actually page_mappings from visible area detection
            page_mappings = page_mappings_or_current_page
            
            # The coordinates have already been converted to scene coordinates in detect_blocks
            # We just need to merge with existing blocks and filter out overlapping ones
            
            if page_mappings:
                # Get the scene Y range that was detected
                scene_y_min = min(mapping['scene_y_start'] for mapping in page_mappings)
                scene_y_max = max(mapping['scene_y_end'] for mapping in page_mappings)
                
                # Remove existing blocks that fall within the detected area to avoid duplicates
                filtered_blocks = []
                for existing_blk in self.main_page.blk_list:
                    blk_y = existing_blk.xyxy[1]  # Top Y coordinate
                    blk_bottom = existing_blk.xyxy[3]  # Bottom Y coordinate
                    
                    # Keep blocks that don't overlap with the detected area
                    if not (blk_y >= scene_y_min and blk_bottom <= scene_y_max):
                        filtered_blocks.append(existing_blk)
                
                # Add the new blocks to the filtered list
                self.main_page.blk_list = filtered_blocks + blk_list
            else:
                self.main_page.blk_list = blk_list
        else:
            # In single image mode, replace entirely
            self.main_page.blk_list = blk_list
        
        source_lang = self.main_page.s_combo.currentText()
        source_lang_english = self.main_page.lang_mapping.get(source_lang, source_lang)
        rtl = True if source_lang_english == 'Japanese' else False
        self.main_page.blk_list = sort_blk_list(self.main_page.blk_list, rtl)
        
        if load_rects:
            # For visible area detection, we pass the detected blocks only for rectangle loading
            blocks_to_load = blk_list
            self.load_box_coords(blocks_to_load)
