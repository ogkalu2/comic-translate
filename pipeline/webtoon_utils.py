import logging
from typing import Optional
import logging

from modules.utils.textblock import TextBlock

logger = logging.getLogger(__name__)


def find_block_page_index(blk: TextBlock, webtoon_manager) -> Optional[int]:
    """Find which page index this block belongs to based on its coordinates."""
    # Get block center y coordinate in scene space
    block_center_y = (blk.xyxy[1] + blk.xyxy[3]) / 2
    
    # Find which page this y coordinate belongs to
    for i, (page_y, page_height) in enumerate(zip(webtoon_manager.image_positions, webtoon_manager.image_heights)):
        if page_y <= block_center_y <= page_y + page_height:
            return i
    
    return None


def find_block_intersecting_pages(blk: TextBlock, webtoon_manager) -> list[int]:
    """Find all page indices that this block intersects with."""
    intersecting_pages = []
    
    # Get block bounds in scene space
    blk_y1 = blk.xyxy[1]
    blk_y2 = blk.xyxy[3]
    
    # Check intersection with each page
    for i, (page_y, page_height) in enumerate(zip(webtoon_manager.image_positions, webtoon_manager.image_heights)):
        page_bottom = page_y + page_height
        
        # Check if block intersects with this page
        if blk_y2 > page_y and blk_y1 < page_bottom:
            intersecting_pages.append(i)
    
    return intersecting_pages


def is_block_in_visible_portion(blk: TextBlock, mapping: dict, page_idx: int, webtoon_manager) -> bool:
    """Check if block intersects with the visible portion of the page."""
    page_y = webtoon_manager.image_positions[page_idx]
    
    # Get block bounds in page-local coordinates
    blk_y1_local = blk.xyxy[1] - page_y
    blk_y2_local = blk.xyxy[3] - page_y
    
    # Check if block overlaps with visible portion
    crop_top = mapping['page_crop_top']
    crop_bottom = mapping['page_crop_bottom']
    
    return blk_y2_local > crop_top and blk_y1_local < crop_bottom


def get_first_visible_block(blk_list: list[TextBlock], image_viewer) -> Optional[TextBlock]:
    """Get the first visible block in webtoon mode."""
    webtoon_manager = image_viewer.webtoon_manager
    # Get the visible area image and mapping data
    visible_image, mappings = image_viewer.get_visible_area_image()
    if visible_image is None or not mappings:
        return None
    
    # Create mapping from page index to mapping data for quick lookup
    page_mappings = {}
    for mapping in mappings:
        page_idx = mapping['page_index']
        if page_idx not in page_mappings:
            page_mappings[page_idx] = []
        page_mappings[page_idx].append(mapping)
    
    # Look for the first visible block
    for blk in blk_list:
        # Find which page this block belongs to by checking its coordinates
        blk_page_idx = find_block_page_index(blk, webtoon_manager)
        if blk_page_idx is None or blk_page_idx not in page_mappings:
            continue
        
        # Check if block is in any of the visible page portions
        for mapping in page_mappings[blk_page_idx]:
            if is_block_in_visible_portion(blk, mapping, blk_page_idx, webtoon_manager):
                return blk
    
    return None


def convert_block_to_visible_coordinates(blk: TextBlock, mapping: dict, page_idx: int, webtoon_manager):
    """Convert block coordinates from webtoon scene space to visible image space."""
    page_y = webtoon_manager.image_positions[page_idx]
    
    # Get page width and centering offset
    if page_idx in webtoon_manager.image_data:
        page_width = webtoon_manager.image_data[page_idx].shape[1]
    else:
        page_width = webtoon_manager.webtoon_width
    page_x_offset = (webtoon_manager.webtoon_width - page_width) / 2
    
    # Convert coordinates to page-local first
    x1_local = blk.xyxy[0] - page_x_offset
    y1_local = blk.xyxy[1] - page_y
    x2_local = blk.xyxy[2] - page_x_offset
    y2_local = blk.xyxy[3] - page_y
    
    # Convert from page-local to combined image coordinates
    # The mapping tells us how this page's crop maps to the combined image
    crop_top = mapping['page_crop_top']
    combined_y_start = mapping['combined_y_start']
    
    # Subtract the crop offset and add the combined image offset
    y1_combined = (y1_local - crop_top) + combined_y_start
    y2_combined = (y2_local - crop_top) + combined_y_start
    
    # Update block coordinates
    blk.xyxy[0] = int(max(0, x1_local))
    blk.xyxy[1] = int(max(0, y1_combined))
    blk.xyxy[2] = int(x2_local)
    blk.xyxy[3] = int(y2_combined)
    
    # Also convert bubble coordinates if present
    if blk.bubble_xyxy is not None:
        bubble_x1_local = blk.bubble_xyxy[0] - page_x_offset
        bubble_y1_local = blk.bubble_xyxy[1] - page_y
        bubble_x2_local = blk.bubble_xyxy[2] - page_x_offset
        bubble_y2_local = blk.bubble_xyxy[3] - page_y
        
        # Apply same conversion to bubble coordinates
        bubble_y1_combined = (bubble_y1_local - crop_top) + combined_y_start
        bubble_y2_combined = (bubble_y2_local - crop_top) + combined_y_start
        
        blk.bubble_xyxy[0] = int(max(0, bubble_x1_local))
        blk.bubble_xyxy[1] = int(max(0, bubble_y1_combined))
        blk.bubble_xyxy[2] = int(bubble_x2_local)
        blk.bubble_xyxy[3] = int(bubble_y2_combined)


def filter_and_convert_visible_blocks(main_page, pipeline, mappings: list[dict], single_block: bool = False) -> list[TextBlock]:
    """Filter blocks to visible area and convert their coordinates to visible image space."""
    visible_blocks = []
    
    # Get the blocks to process
    if single_block:
        selected_block = pipeline.get_selected_block()
        if not selected_block:
            return []
        blocks_to_check = [selected_block]
    else:
        blocks_to_check = main_page.blk_list

    webtoon_manager = main_page.image_viewer.webtoon_manager
    
    # Create mapping from page index to mapping data for quick lookup
    page_mappings = {}
    for mapping in mappings:
        page_idx = mapping['page_index']
        if page_idx not in page_mappings:
            page_mappings[page_idx] = []
        page_mappings[page_idx].append(mapping)
    
    for blk in blocks_to_check:
        # Find ALL pages this block intersects with (not just the center page)
        intersecting_pages = find_block_intersecting_pages(blk, webtoon_manager)
        if not intersecting_pages:
            continue
        
        # Check if block is visible in any of the intersecting pages that are also visible
        found_visible_portion = False
        for blk_page_idx in intersecting_pages:
            if blk_page_idx not in page_mappings:
                continue
                
            # Check if block is in any of the visible page portions for this page
            for mapping in page_mappings[blk_page_idx]:
                if is_block_in_visible_portion(blk, mapping, blk_page_idx, webtoon_manager):
                    # Store original coordinates and mapping info for later restoration
                    blk._original_xyxy = blk.xyxy.copy()
                    blk._original_bubble_xyxy = blk.bubble_xyxy.copy() if blk.bubble_xyxy is not None else None
                    blk._mapping = mapping
                    blk._page_index = blk_page_idx
                    
                    # Convert coordinates to visible image space
                    convert_block_to_visible_coordinates(blk, mapping, blk_page_idx, webtoon_manager)
                    
                    # Add the original block to the list
                    visible_blocks.append(blk)
                    found_visible_portion = True
                    break
            
            if found_visible_portion:
                break
    
    return visible_blocks


def restore_original_block_coordinates(processed_blocks: list[TextBlock]):
    """Restore original scene coordinates to blocks and clean up temporary attributes."""
    for blk in processed_blocks:
        if not hasattr(blk, '_original_xyxy'):
            continue
        
        # Restore original coordinates
        blk.xyxy[:] = blk._original_xyxy
        if blk._original_bubble_xyxy is not None:
            blk.bubble_xyxy[:] = blk._original_bubble_xyxy
        
        # Clean up temporary attributes
        delattr(blk, '_original_xyxy')
        delattr(blk, '_original_bubble_xyxy')
        delattr(blk, '_mapping')
        delattr(blk, '_page_index')


def is_text_item_in_visible_portion(text_item, mapping: dict, page_idx: int, webtoon_manager) -> bool:
    """Check if text item intersects with the visible portion of the page."""
    page_y = webtoon_manager.image_positions[page_idx]
    
    # Get text item bounds in page-local coordinates
    item_x = text_item.pos().x()
    item_y = text_item.pos().y()
    item_rect = text_item.boundingRect()
    
    # Convert text item bounds to page-local coordinates
    item_y1_local = item_y - page_y
    item_y2_local = (item_y + item_rect.height()) - page_y
    
    # Check if text item overlaps with visible portion
    crop_top = mapping['page_crop_top']
    crop_bottom = mapping['page_crop_bottom']
    
    return item_y2_local > crop_top and item_y1_local < crop_bottom


def find_text_item_page_index(text_item, webtoon_manager) -> Optional[int]:
    """Find which page index this text item belongs to based on its position."""
    # Get text item center y coordinate in scene space
    item_y = text_item.pos().y()
    item_rect = text_item.boundingRect()
    item_center_y = item_y + (item_rect.height() / 2)
    
    # Find which page this y coordinate belongs to
    for i, (page_y, page_height) in enumerate(zip(webtoon_manager.image_positions, webtoon_manager.image_heights)):
        if page_y <= item_center_y <= page_y + page_height:
            return i
    
    return None


def get_visible_text_items(all_text_items: list, webtoon_manager) -> list:
    """Get text items that are currently visible in webtoon mode."""
    try:
        # Get the visible area image and mapping data
        visible_image, mappings = webtoon_manager.viewer.get_visible_area_image()
        if visible_image is None or not mappings:
            return all_text_items
        
        # Create mapping from page index to mapping data for quick lookup
        page_mappings = {}
        for mapping in mappings:
            page_idx = mapping['page_index']
            if page_idx not in page_mappings:
                page_mappings[page_idx] = []
            page_mappings[page_idx].append(mapping)
        
        visible_text_items = []
        for text_item in all_text_items:
            # Find which page this text item belongs to by checking its position
            item_page_idx = find_text_item_page_index(text_item, webtoon_manager)
            if item_page_idx is None or item_page_idx not in page_mappings:
                continue
            
            # Check if text item is in any of the visible page portions
            for mapping in page_mappings[item_page_idx]:
                if is_text_item_in_visible_portion(text_item, mapping, item_page_idx, webtoon_manager):
                    visible_text_items.append(text_item)
                    break
        
        return visible_text_items
    except Exception:
        # Fallback to all text items if there's any error in webtoon processing
        return all_text_items


def convert_bboxes_to_webtoon_coordinates(bboxes: list, mapping: dict, page_idx: int, webtoon_manager) -> list:
    """Convert bounding boxes from visible image space back to webtoon scene space."""
    if not bboxes:
        return bboxes
    
    page_y = webtoon_manager.image_positions[page_idx]
    
    # Get page width and centering offset
    if page_idx in webtoon_manager.image_data:
        page_width = webtoon_manager.image_data[page_idx].shape[1]
    else:
        page_width = webtoon_manager.webtoon_width
    page_x_offset = (webtoon_manager.webtoon_width - page_width) / 2
    
    crop_top = mapping['page_crop_top']
    combined_y_start = mapping['combined_y_start']
    
    converted_bboxes = []
    for bbox in bboxes:
        # Convert from combined visible image coordinates back to page-local coordinates
        # First, remove the combined image offset to get back to page-relative coordinates
        x1_page_relative = bbox[0]  # x coordinates don't change between pages
        y1_page_relative = bbox[1] - combined_y_start
        x2_page_relative = bbox[2] 
        y2_page_relative = bbox[3] - combined_y_start
        
        # Then add back the crop offset to get full page-local coordinates
        x1_local = x1_page_relative
        y1_local = y1_page_relative + crop_top
        x2_local = x2_page_relative
        y2_local = y2_page_relative + crop_top
        
        # Convert from page-local to webtoon scene coordinates
        x1_scene = x1_local + page_x_offset
        y1_scene = y1_local + page_y
        x2_scene = x2_local + page_x_offset
        y2_scene = y2_local + page_y
        
        converted_bboxes.append([x1_scene, y1_scene, x2_scene, y2_scene])
    
    return converted_bboxes


