"""
Text Block Manager for Webtoon Scene Items

Handles TextBlock objects management with state storage for webtoon mode.
Manages loading/unloading of blk_list and coordinate conversion.
"""

from typing import List, Dict
from PySide6.QtCore import QPointF, QRectF
from modules.utils.textblock import TextBlock


class TextBlockManager:
    """Manages TextBlock objects for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter, image_loader):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self.image_loader = image_loader
        
        # Main controller reference (set by scene item manager)
        self.main_controller = None
        
        # Current page tracking
        self.current_page_idx = -1
    
    def initialize(self):
        """Initialize or reset the text block manager state."""
        self.current_page_idx = -1
    
    def _convert_bbox_coordinates(self, bbox, page_idx: int, to_scene: bool = True):
        """
        Helper function to convert bounding box coordinates.
        
        Args:
            bbox: List/array with [x1, y1, x2, y2] coordinates
            page_idx: Page index for coordinate conversion
            to_scene: If True, convert page-local to scene. If False, convert scene to page-local.
        """
        if bbox is None or len(bbox) < 4:
            return
            
        x1, y1, x2, y2 = bbox[:4]
        
        top_left = QPointF(x1, y1)
        bottom_right = QPointF(x2, y2)
        
        if to_scene:
            # Convert page-local to scene coordinates
            scene_top_left = self.coordinate_converter.page_local_to_scene_position(top_left, page_idx)
            scene_bottom_right = self.coordinate_converter.page_local_to_scene_position(bottom_right, page_idx)
            
            bbox[0] = scene_top_left.x()
            bbox[1] = scene_top_left.y()
            bbox[2] = scene_bottom_right.x()
            bbox[3] = scene_bottom_right.y()
        else:
            # Convert scene to page-local coordinates
            page_local_top_left = self.coordinate_converter.scene_to_page_local_position(top_left, page_idx)
            page_local_bottom_right = self.coordinate_converter.scene_to_page_local_position(bottom_right, page_idx)
            
            bbox[0] = page_local_top_left.x()
            bbox[1] = page_local_top_left.y()
            bbox[2] = page_local_bottom_right.x()
            bbox[3] = page_local_bottom_right.y()
    
    def _convert_textblock_coordinates(self, blk: TextBlock, page_idx: int, to_scene: bool = True):
        """
        Helper function to convert all coordinates in a TextBlock.
        
        Args:
            blk: TextBlock object to modify
            page_idx: Page index for coordinate conversion
            to_scene: If True, convert page-local to scene. If False, convert scene to page-local.
        """
        # Convert main xyxy coordinates
        self._convert_bbox_coordinates(blk.xyxy, page_idx, to_scene)
        
        # Convert bubble_xyxy coordinates if they exist
        if blk.bubble_xyxy is not None:
            self._convert_bbox_coordinates(blk.bubble_xyxy, page_idx, to_scene)
        
        # Convert inpaint_bboxes coordinates if they exist
        if blk.inpaint_bboxes is not None and len(blk.inpaint_bboxes) > 0:
            for bbox in blk.inpaint_bboxes:
                self._convert_bbox_coordinates(bbox, page_idx, to_scene)
    
    def _create_clipped_textblock(self, original_blk: TextBlock, clipped_xyxy: tuple, page_idx: int) -> TextBlock:
        """
        Create a clipped copy of a text block for a specific page.
        
        Args:
            original_blk: Original TextBlock object
            clipped_xyxy: Clipped coordinates in page-local format (x1, y1, x2, y2)
            page_idx: Page index for additional coordinate clipping if needed
            
        Returns:
            New TextBlock with clipped coordinates
        """
        # Create a deep copy of the original text block
        clipped_blk = original_blk.deep_copy()
        
        # Update the main xyxy coordinates with the clipped version
        clipped_blk.xyxy = list(clipped_xyxy)
        
        # Clip bubble_xyxy if it exists and intersects with the page
        if original_blk.bubble_xyxy is not None:
            # Create a temporary TextBlock with just bubble coordinates to clip
            temp_blk = TextBlock()
            temp_blk.xyxy = original_blk.bubble_xyxy
            clipped_bubble = self.coordinate_converter.clip_textblock_to_page(temp_blk, page_idx)
            if clipped_bubble and clipped_bubble[2] > clipped_bubble[0] and clipped_bubble[3] > clipped_bubble[1]:
                clipped_blk.bubble_xyxy = list(clipped_bubble)
            else:
                clipped_blk.bubble_xyxy = None
        
        # Clip inpaint_bboxes if they exist
        if original_blk.inpaint_bboxes is not None and len(original_blk.inpaint_bboxes) > 0:
            clipped_inpaint_bboxes = []
            for bbox in original_blk.inpaint_bboxes:
                # Create a temporary TextBlock with just this bbox to clip
                temp_blk = TextBlock()
                temp_blk.xyxy = bbox
                clipped_bbox = self.coordinate_converter.clip_textblock_to_page(temp_blk, page_idx)
                if clipped_bbox and clipped_bbox[2] > clipped_bbox[0] and clipped_bbox[3] > clipped_bbox[1]:
                    clipped_inpaint_bboxes.append(list(clipped_bbox))
            
            clipped_blk.inpaint_bboxes = clipped_inpaint_bboxes if clipped_inpaint_bboxes else None
        
        return clipped_blk
    
    def _remove_duplicate_textblocks(self, textblocks: List[TextBlock]) -> List[TextBlock]:
        """
        Remove duplicate text blocks that may appear due to cross-page spanning.
        
        Args:
            textblocks: List of text blocks that may contain duplicates
            
        Returns:
            List of unique text blocks
        """
        if not textblocks:
            return []
            
        unique_blocks = []
        tolerance = 5.0  # Pixel tolerance for coordinate comparison
        
        for blk in textblocks:
            is_duplicate = False
            
            for existing_blk in unique_blocks:
                # Check if this block is similar to an existing one
                if (abs(blk.xyxy[0] - existing_blk.xyxy[0]) < tolerance and
                    abs(blk.xyxy[1] - existing_blk.xyxy[1]) < tolerance and
                    abs(blk.xyxy[2] - existing_blk.xyxy[2]) < tolerance and
                    abs(blk.xyxy[3] - existing_blk.xyxy[3]) < tolerance and
                    abs(blk.angle - existing_blk.angle) < 0.1 and
                    blk.text == existing_blk.text):
                    
                    # This is likely a duplicate, but merge any additional information
                    # Keep the larger bounding box if they differ slightly
                    if ((blk.xyxy[2] - blk.xyxy[0]) * (blk.xyxy[3] - blk.xyxy[1]) > 
                        (existing_blk.xyxy[2] - existing_blk.xyxy[0]) * (existing_blk.xyxy[3] - existing_blk.xyxy[1])):
                        # Replace with the larger version
                        unique_blocks[unique_blocks.index(existing_blk)] = blk
                    
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_blocks.append(blk)
        
        return unique_blocks
    
    def load_text_blocks(self, page_idx: int):
        """Load TextBlock objects for a specific page into main controller's blk_list."""
        if not self.main_controller or page_idx >= len(self.image_loader.image_file_paths):
            return
            
        file_path = self.image_loader.image_file_paths[page_idx]
        stored_blks = self.main_controller.image_states[file_path].get('blk_list', []).copy()
        
        # Convert coordinates from page-local to scene coordinates for webtoon mode
        # Modify coordinates directly without copying (same as original approach)
        for blk in stored_blks:
            self._convert_textblock_coordinates(blk, page_idx, to_scene=True)

        self.main_controller.blk_list.extend(stored_blks)
        self.current_page_idx = page_idx
    
    def unload_text_blocks(self, page_idx: int, page_y: float, page_bottom: float, file_path: str):
        """
        Unload TextBlock objects for a specific page, converting coordinates back to page-local and storing them.
        
        Similar to rectangles, this stores the FULL text block (not clipped) if it intersects with the page.
        In webtoon mode, there's no visual concept of page separation, so we preserve the complete blocks.
        """
        if not self.main_controller:
            return
            
        text_blocks_to_store = []
        text_blocks_to_remove = []
        
        for blk in self.main_controller.blk_list[:]:
            if blk.xyxy is None or len(blk.xyxy) < 4:
                continue
                
            # Check if text block intersects with this page
            blk_y = blk.xyxy[1]
            blk_height = blk.xyxy[3] - blk.xyxy[1] 
            blk_bottom = blk.xyxy[3]
            
            # Check if text block is on this page (same logic as rectangles)
            if (blk_y >= page_y and blk_y < page_bottom) or \
               (blk_bottom > page_y and blk_bottom <= page_bottom) or \
               (blk_y < page_y and blk_bottom > page_bottom):
                
                # Convert the text block coordinates directly to page-local coordinates (no copying)
                self._convert_textblock_coordinates(blk, page_idx, to_scene=False)
                text_blocks_to_store.append(blk)
                text_blocks_to_remove.append(blk)
        
        # Store text blocks in image_states 
        if file_path not in self.main_controller.image_states:
            self.main_controller.image_states[file_path] = {}
        self.main_controller.image_states[file_path]['blk_list'] = text_blocks_to_store
        
        # Remove text blocks from main.blk_list
        for blk in text_blocks_to_remove:
            if blk in self.main_controller.blk_list:
                self.main_controller.blk_list.remove(blk)
    
    def save_text_blocks_to_states(self, scene_items_by_page: Dict):
        """
        Save text blocks to appropriate page states for bulk save operations.
        
        Note: This method works in conjunction with unload_text_blocks() which handles
        individual page transitions. This method ensures all text blocks are distributed
        to their appropriate pages during bulk save operations.
        """
        for blk in self.main_controller.blk_list:
            # Find all pages this text block intersects with
            if blk.xyxy is None or len(blk.xyxy) < 4:
                continue
                
            # Create scene bounds for the text block
            blk_scene_bounds = QRectF(
                blk.xyxy[0], 
                blk.xyxy[1],
                blk.xyxy[2] - blk.xyxy[0],  # width
                blk.xyxy[3] - blk.xyxy[1]   # height
            )
            intersecting_pages = self.layout_manager.get_pages_for_scene_bounds(blk_scene_bounds)
            
            # Add clipped version to each intersecting page
            for page_idx in intersecting_pages:
                if 0 <= page_idx < len(self.image_loader.image_file_paths):
                    clipped_xyxy = self.coordinate_converter.clip_textblock_to_page(blk, page_idx)
                    if clipped_xyxy and clipped_xyxy[2] > clipped_xyxy[0] and clipped_xyxy[3] > clipped_xyxy[1]:
                        # Create a clipped copy of the text block for this page
                        clipped_blk = self._create_clipped_textblock(blk, clipped_xyxy, page_idx)
                        scene_items_by_page[page_idx]['text_blocks'].append(clipped_blk)
    
    def clear(self):
        """Clear all text block management state."""
        self.current_page_idx = -1

    def redistribute_existing_text_blocks(self, all_existing_blk_list: List[tuple], scene_items_by_page: Dict):
        """Redistribute existing text blocks to all pages they intersect with after clipping."""
        processed_blocks = set()  # Track processed blocks to avoid duplicates
        for blk, original_page_idx in all_existing_blk_list:
            # Create a unique identifier for this block to avoid duplicates
            blk_id = id(blk)
            if blk_id in processed_blocks:
                continue
            processed_blocks.add(blk_id)
            
            if not (hasattr(blk, 'xyxy') and blk.xyxy is not None and len(blk.xyxy) >= 4):
                # Keep invalid block on its original page
                scene_items_by_page[original_page_idx]['text_blocks'].append(blk)
                continue
                
            # Convert from page-local to scene coordinates
            local_top_left = QPointF(blk.xyxy[0], blk.xyxy[1])
            scene_top_left = self.coordinate_converter.page_local_to_scene_position(local_top_left, original_page_idx)

            # Create scene bounds for the text block (following save_text_blocks_to_states pattern)
            blk_scene_bounds = QRectF(
                scene_top_left.x(), 
                scene_top_left.y(),
                blk.xyxy[2] - blk.xyxy[0],  # width
                blk.xyxy[3] - blk.xyxy[1]   # height
            )
            intersecting_pages = self.layout_manager.get_pages_for_scene_bounds(blk_scene_bounds)
            
            # Create a temporary text block with scene coordinates
            temp_blk = blk.deep_copy() if hasattr(blk, 'deep_copy') else blk
            temp_blk.xyxy = [scene_top_left.x(), scene_top_left.y(), 
                           scene_top_left.x() + (blk.xyxy[2] - blk.xyxy[0]),
                           scene_top_left.y() + (blk.xyxy[3] - blk.xyxy[1])]
            
            # Add clipped version to each intersecting page (following save_text_blocks_to_states pattern)
            for page_idx in intersecting_pages:
                if 0 <= page_idx < len(self.image_loader.image_file_paths):
                    clipped_xyxy = self.coordinate_converter.clip_textblock_to_page(temp_blk, page_idx)
                    if clipped_xyxy and clipped_xyxy[2] > clipped_xyxy[0] and clipped_xyxy[3] > clipped_xyxy[1]:
                        # Create a clipped copy of the text block for this page
                        clipped_blk = self._create_clipped_textblock(blk, clipped_xyxy, page_idx)
                        scene_items_by_page[page_idx]['text_blocks'].append(clipped_blk)

    def is_duplicate_text_block(self, new_blk, existing_blks, margin=5):
        """Check if a text block is a duplicate of any existing text block within margin."""
        if not (hasattr(new_blk, 'xyxy') and new_blk.xyxy is not None and len(new_blk.xyxy) >= 4):
            return False
            
        new_x1, new_y1, new_x2, new_y2 = new_blk.xyxy[:4]
        new_rotation = new_blk.angle

        for existing_blk in existing_blks:
            if not (hasattr(existing_blk, 'xyxy') and existing_blk.xyxy is not None and len(existing_blk.xyxy) >= 4):
                continue
                
            ex_x1, ex_y1, ex_x2, ex_y2 = existing_blk.xyxy[:4]
            ex_rotation = existing_blk.angle

            # Check if coordinates are within margin
            if (abs(new_x1 - ex_x1) <= margin and 
                abs(new_y1 - ex_y1) <= margin and 
                abs(new_x2 - ex_x2) <= margin and 
                abs(new_y2 - ex_y2) <= margin and
                abs(new_rotation - ex_rotation) <= 1.0):  # 1 degree tolerance for rotation
                return True
        return False

    def merge_clipped_text_blocks(self):
        """Merge text blocks that were clipped across page boundaries in regular mode."""
        if not self.main_controller:
            return
            
        all_text_blocks = []
        
        # Collect all text blocks from all pages
        for page_idx in range(len(self.image_loader.image_file_paths)):
            file_path = self.image_loader.image_file_paths[page_idx]
            state = self.main_controller.image_states.get(file_path, {})
            text_blocks = state.get('blk_list', [])
            
            for blk in text_blocks:
                if not (hasattr(blk, 'xyxy') and blk.xyxy is not None and len(blk.xyxy) >= 4):
                    continue
                    
                # Convert to scene coordinates for comparison
                local_x1, local_y1, local_x2, local_y2 = blk.xyxy[:4]
                local_top_left = QPointF(local_x1, local_y1)
                local_bottom_right = QPointF(local_x2, local_y2)
                
                scene_top_left = self.coordinate_converter.page_local_to_scene_position(local_top_left, page_idx)
                scene_bottom_right = self.coordinate_converter.page_local_to_scene_position(local_bottom_right, page_idx)
                
                all_text_blocks.append({
                    'blk': blk,
                    'page_idx': page_idx,
                    'scene_bounds': QRectF(
                        scene_top_left.x(), 
                        scene_top_left.y(),
                        scene_bottom_right.x() - scene_top_left.x(),
                        scene_bottom_right.y() - scene_top_left.y()
                    )
                })
        
        if len(all_text_blocks) < 2:
            return  # Need at least 2 blocks to merge
        
        # Group vertically adjacent text blocks with similar properties
        merged_groups = []
        used_blocks = set()
        
        for i, block1 in enumerate(all_text_blocks):
            if i in used_blocks:
                continue
                
            group = [block1]
            used_blocks.add(i)
            
            for j, block2 in enumerate(all_text_blocks):
                if j in used_blocks or i == j:
                    continue
                    
                if self._are_text_blocks_mergeable(block1, block2):
                    group.append(block2)
                    used_blocks.add(j)
            
            if len(group) > 1:
                merged_groups.append(group)
        
        # Merge each group
        for group in merged_groups:
            self._merge_text_block_group(group)

    def _are_text_blocks_mergeable(self, block1, block2):
        """Check if two text blocks can be merged (were likely clipped from same original in regular mode)."""
        bounds1 = block1['scene_bounds']
        bounds2 = block2['scene_bounds']
        blk1 = block1['blk']
        blk2 = block2['blk']
        
        # Check if they're on adjacent pages (key for clipped items)
        if abs(block1['page_idx'] - block2['page_idx']) > 1:
            return False
        
        # Check if they're vertically adjacent
        tolerance = 15  # Tolerance for text blocks
        adjacent = (abs(bounds1.bottom() - bounds2.top()) < tolerance or 
                   abs(bounds2.bottom() - bounds1.top()) < tolerance)
        
        if not adjacent:
            return False
            
        # Check horizontal alignment (clipped text blocks should have very similar X positions)
        x_tolerance = 10
        if abs(bounds1.left() - bounds2.left()) > x_tolerance:
            return False
            
        # Check width similarity (clipped text blocks should have similar widths)
        width_tolerance = 20
        if abs(bounds1.width() - bounds2.width()) > width_tolerance:
            return False
            
        # Check similar properties
        if (blk1.text_class != blk2.text_class or
            abs(blk1.angle - blk2.angle) > 1.0 or  # 1 degree tolerance
            blk1.source_lang != blk2.source_lang or
            blk1.target_lang != blk2.target_lang):
            return False
            
        return True

    def _merge_text_block_group(self, group):
        """Merge a group of clipped text blocks back into one."""
        if len(group) <= 1:
            return
        
        # Check if all text blocks have the same text content - if so, don't merge
        texts = []
        for item in group:
            blk_text = getattr(item['blk'], 'text', '') or ''
            texts.append(blk_text.strip())
        
        # Remove empty strings and check uniqueness
        non_empty_texts = [text for text in texts if text]
        if len(set(non_empty_texts)) <= 1:
            # All texts are the same or empty, don't merge
            return
        
        # Sort by Y position to maintain reading order
        group_sorted = sorted(group, key=lambda x: x['scene_bounds'].top())
        
        # Use the first block as base and create a deep copy
        base_block_item = group_sorted[0]
        base_blk = base_block_item['blk']
        merged_blk = base_blk.deep_copy()
        
        # Calculate unified bounds in scene coordinates
        all_bounds = [item['scene_bounds'] for item in group_sorted]
        unified_left = min(bounds.left() for bounds in all_bounds)
        unified_top = min(bounds.top() for bounds in all_bounds)
        unified_right = max(bounds.right() for bounds in all_bounds)
        unified_bottom = max(bounds.bottom() for bounds in all_bounds)
        
        # Determine target page (center of merged block)
        center_y = (unified_top + unified_bottom) / 2
        target_page = self.layout_manager.get_page_at_position(center_y)
        
        # Convert unified bounds back to page-local coordinates
        scene_top_left = QPointF(unified_left, unified_top)
        scene_bottom_right = QPointF(unified_right, unified_bottom)
        local_top_left = self.coordinate_converter.scene_to_page_local_position(scene_top_left, target_page)
        local_bottom_right = self.coordinate_converter.scene_to_page_local_position(scene_bottom_right, target_page)
        
        # Update merged block's xyxy coordinates
        merged_blk.xyxy = [
            local_top_left.x(),
            local_top_left.y(),
            local_bottom_right.x(),
            local_bottom_right.y()
        ]
        
        # Merge text content from all blocks
        merged_texts = []
        for item in group_sorted:
            if hasattr(item['blk'], 'text') and item['blk'].text:
                merged_texts.append(item['blk'].text)
        merged_blk.text = ' '.join(merged_texts) if merged_texts else base_blk.text
        
        # Merge translations if available
        merged_translations = []
        for item in group_sorted:
            if hasattr(item['blk'], 'translation') and item['blk'].translation:
                merged_translations.append(item['blk'].translation)
        merged_blk.translation = ' '.join(merged_translations) if merged_translations else base_blk.translation
        
        # Handle bubble_xyxy if present - merge bubble bounds as well
        if any(hasattr(item['blk'], 'bubble_xyxy') and item['blk'].bubble_xyxy is not None for item in group_sorted):
            # Find the unified bubble bounds
            bubble_bounds = []
            for item in group_sorted:
                blk = item['blk']
                if hasattr(blk, 'bubble_xyxy') and blk.bubble_xyxy is not None and len(blk.bubble_xyxy) >= 4:
                    page_idx = item['page_idx']
                    bx1, by1, bx2, by2 = blk.bubble_xyxy[:4]
                    bubble_top_left = QPointF(bx1, by1)
                    bubble_bottom_right = QPointF(bx2, by2)
                    
                    scene_bubble_top_left = self.coordinate_converter.page_local_to_scene_position(bubble_top_left, page_idx)
                    scene_bubble_bottom_right = self.coordinate_converter.page_local_to_scene_position(bubble_bottom_right, page_idx)
                    
                    bubble_bounds.extend([scene_bubble_top_left, scene_bubble_bottom_right])
            
            if bubble_bounds:
                # Calculate unified bubble bounds
                unified_bubble_left = min(pt.x() for pt in bubble_bounds)
                unified_bubble_top = min(pt.y() for pt in bubble_bounds)
                unified_bubble_right = max(pt.x() for pt in bubble_bounds)
                unified_bubble_bottom = max(pt.y() for pt in bubble_bounds)
                
                # Convert back to target page coordinates
                scene_bubble_top_left = QPointF(unified_bubble_left, unified_bubble_top)
                scene_bubble_bottom_right = QPointF(unified_bubble_right, unified_bubble_bottom)
                local_bubble_top_left = self.coordinate_converter.scene_to_page_local_position(scene_bubble_top_left, target_page)
                local_bubble_bottom_right = self.coordinate_converter.scene_to_page_local_position(scene_bubble_bottom_right, target_page)
                
                merged_blk.bubble_xyxy = [
                    local_bubble_top_left.x(),
                    local_bubble_top_left.y(),
                    local_bubble_bottom_right.x(),
                    local_bubble_bottom_right.y()
                ]
        
        # Remove all blocks from their current pages
        for item in group:
            page_idx = item['page_idx']
            file_path = self.image_loader.image_file_paths[page_idx]
            state = self.main_controller.image_states[file_path]
            blk_list = state.get('blk_list', [])
            # Remove this block
            if item['blk'] in blk_list:
                blk_list.remove(item['blk'])
        
        # Add merged block to target page
        target_file_path = self.image_loader.image_file_paths[target_page]
        target_state = self.main_controller.image_states[target_file_path]
        if 'blk_list' not in target_state:
            target_state['blk_list'] = []
        target_state['blk_list'].append(merged_blk)