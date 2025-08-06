"""
Scene Item Manager for Webtoon Manager

Handles scene items (rectangles, text, brush strokes, patches) management with state storage.
Refactored to delegate to specialized managers.
"""

from typing import List, Dict
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QTextDocument
from .rectangle_manager import RectangleManager
from .text_item_manager import TextItemManager
from .brush_stroke_manager import BrushStrokeManager
from .text_block_manager import TextBlockManager
from .patch_manager import PatchManager


class SceneItemManager:
    """Manages scene items for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self._scene = viewer._scene
        
        # Main controller reference (set by lazy webtoon manager)
        self.main_controller = None
        
        # Initialize specialized managers
        self.rectangle_manager = RectangleManager(viewer, layout_manager, coordinate_converter)
        self.text_item_manager = TextItemManager(viewer, layout_manager, coordinate_converter)
        self.brush_stroke_manager = BrushStrokeManager(viewer, layout_manager, coordinate_converter)
        self.text_block_manager = TextBlockManager(viewer, layout_manager, coordinate_converter)
        self.patch_manager = PatchManager(viewer, layout_manager, coordinate_converter)
        
        # File path references (for state storage)
        self.image_file_paths: List[str] = []
    
    def initialize(self, file_paths: List[str]):
        """Initialize scene item manager with file paths."""
        self.image_file_paths = file_paths.copy()
        
        # Initialize all specialized managers
        self.rectangle_manager.initialize(file_paths)
        self.text_item_manager.initialize(file_paths)
        self.brush_stroke_manager.initialize(file_paths)
        self.text_block_manager.initialize(file_paths)
        self.patch_manager.initialize(file_paths)
        
        # Set main controller references
        self.rectangle_manager.main_controller = self.main_controller
        self.text_item_manager.main_controller = self.main_controller
        self.brush_stroke_manager.main_controller = self.main_controller
        self.text_block_manager.main_controller = self.main_controller
        self.patch_manager.main_controller = self.main_controller
        
    def update_file_paths(self, file_paths: List[str]):
        """Update file paths when they change (e.g., after deletion)."""
        print(f"Updating scene item manager file paths: {len(self.image_file_paths)} -> {len(file_paths)}")
        self.image_file_paths = file_paths.copy()
        
        # Update all specialized managers
        self.rectangle_manager.initialize(file_paths)
        self.text_item_manager.initialize(file_paths)
        self.brush_stroke_manager.initialize(file_paths)
        self.text_block_manager.initialize(file_paths)
        self.patch_manager.initialize(file_paths)
    
    def load_page_scene_items(self, page_idx: int):
        """Load scene items (rectangles, text, brush strokes, patches) for a specific page."""
        if not self.main_controller or page_idx >= len(self.image_file_paths):
            return
            
        file_path = self.image_file_paths[page_idx]
        
        # Check if this page has stored state in image_states
        if file_path not in self.main_controller.image_states:
            return
            
        state = self.main_controller.image_states[file_path]
        
        # Update main controller references for managers
        self.rectangle_manager.main_controller = self.main_controller
        self.text_item_manager.main_controller = self.main_controller
        self.brush_stroke_manager.main_controller = self.main_controller
        self.text_block_manager.main_controller = self.main_controller
        self.patch_manager.main_controller = self.main_controller
        
        # Load TextBlock objects for this page first (needed for text items)
        self.text_block_manager.load_text_blocks(page_idx)
        
        # Load rectangles for this page
        self.rectangle_manager.load_rectangles(state, page_idx)
        
        # Load text items for this page
        self.text_item_manager.load_text_items(state, page_idx)
        
        # Load brush strokes for this page
        self.brush_stroke_manager.load_brush_strokes(state, page_idx)
        
        # Load inpaint patches for this page
        self.patch_manager.load_patches(page_idx)
    
    def unload_page_scene_items(self, page_idx: int):
        """Unload scene items for a specific page (saving state if needed)."""
        print(f"Unloading scene items for page {page_idx}")
        
        if not self.main_controller or page_idx >= len(self.image_file_paths):
            return
            
        file_path = self.image_file_paths[page_idx]
        
        # Ensure image_states entry exists
        if file_path not in self.main_controller.image_states:
            self.main_controller.image_states[file_path] = {}
        if 'viewer_state' not in self.main_controller.image_states[file_path]:
            self.main_controller.image_states[file_path]['viewer_state'] = {}
        
        # Determine page bounds for this page
        page_y = self.layout_manager.image_positions[page_idx]
        page_height = self.layout_manager.image_heights[page_idx]
        page_bottom = page_y + page_height
        
        # Update main controller references for managers
        self.rectangle_manager.main_controller = self.main_controller
        self.text_item_manager.main_controller = self.main_controller
        self.brush_stroke_manager.main_controller = self.main_controller
        self.text_block_manager.main_controller = self.main_controller
        self.patch_manager.main_controller = self.main_controller
        
        # Unload rectangles, text items, brush strokes, and patches
        self.text_block_manager.unload_text_blocks(page_idx, page_y, page_bottom, file_path)
        self.rectangle_manager.unload_rectangles(page_idx, page_y, page_bottom, file_path)
        self.text_item_manager.unload_text_items(page_idx, page_y, page_bottom, file_path)
        self.brush_stroke_manager.unload_brush_strokes(page_idx, page_y, page_bottom, file_path)
        self.patch_manager.unload_patches(page_idx)
    
    def save_all_scene_items_to_states(self):
        """
        Save all currently visible scene items to their appropriate page states.
        
        This method is called before switching from webtoon mode to regular mode.
        Items already existing in image_states need to be clipped to page boundaries
        since they were unloaded from webtoon mode which doesn't apply clipping by design.
        In regular mode, items must be clipped to their respective page boundaries.
        """
        if not self.main_controller:
            return

        # Get all scene items and categorize them by page
        scene_items_by_page = {}

        # Initialize dictionaries for each page
        for i in range(len(self.image_file_paths)):
            scene_items_by_page[i] = {
                'rectangles': [],
                'text_items': [],
                'brush_strokes': [],
                'text_blocks': []
            }

        # Update main controller references for managers
        self.rectangle_manager.main_controller = self.main_controller
        self.text_item_manager.main_controller = self.main_controller
        self.brush_stroke_manager.main_controller = self.main_controller
        self.text_block_manager.main_controller = self.main_controller


        # Save TextBlock objects
        self.text_block_manager.save_text_blocks_to_states(scene_items_by_page)

        # Process rectangles
        self.rectangle_manager.save_rectangles_to_states(scene_items_by_page)

        # Process text items with clipping support
        self.text_item_manager.save_text_items_to_states(scene_items_by_page)

        # Process brush strokes
        self.brush_stroke_manager.save_brush_strokes_to_states(scene_items_by_page)

        # Store all items in image_states (append instead of replace)
        # Items already existing in image_states need to be checked for clipping
        # since they were unloaded from webtoon mode which doesn't clip by design
        
        # First, collect all existing items from all pages to avoid processing duplicates
        all_existing_rects = []
        all_existing_brush_strokes = []
        all_existing_blk_list = []
        existing_text_items_by_page = {}  # Text items don't need clipping, handle separately
        
        for page_idx in range(len(self.image_file_paths)):
            file_path = self.image_file_paths[page_idx]
            
            # Ensure image_states structure exists
            if file_path not in self.main_controller.image_states:
                self.main_controller.image_states[file_path] = {}
            if 'viewer_state' not in self.main_controller.image_states[file_path]:
                self.main_controller.image_states[file_path]['viewer_state'] = {}
            
            # Collect existing items (will be redistributed after clipping)
            existing_rects = self.main_controller.image_states[file_path]['viewer_state'].get('rectangles', [])
            existing_brush_strokes = self.main_controller.image_states[file_path].get('brush_strokes', [])
            existing_blk_list = self.main_controller.image_states[file_path].get('blk_list', [])
            existing_text_items = self.main_controller.image_states[file_path]['viewer_state'].get('text_items_state', [])
            
            # Add to collections (with page reference to avoid duplicates)
            for rect in existing_rects:
                all_existing_rects.append((rect, page_idx))
            for stroke in existing_brush_strokes:
                all_existing_brush_strokes.append((stroke, page_idx))
            for blk in existing_blk_list:
                all_existing_blk_list.append((blk, page_idx))
            
            # Text items are now handled with clipping and splitting
            existing_text_items_by_page[page_idx] = existing_text_items
            
            # Clear existing items from image_states (will be repopulated after clipping)
            self.main_controller.image_states[file_path]['viewer_state']['rectangles'] = []
            self.main_controller.image_states[file_path]['brush_strokes'] = []
            self.main_controller.image_states[file_path]['blk_list'] = []
            self.main_controller.image_states[file_path]['viewer_state']['text_items_state'] = []
        
        # Process and redistribute existing items to all pages they intersect with
        self.rectangle_manager.redistribute_existing_rectangles(all_existing_rects, scene_items_by_page)
        self.brush_stroke_manager.redistribute_existing_brush_strokes(all_existing_brush_strokes, scene_items_by_page)
        self.text_block_manager.redistribute_existing_text_blocks(all_existing_blk_list, scene_items_by_page)
        self.text_item_manager.redistribute_existing_text_items(existing_text_items_by_page, scene_items_by_page)
        
        # Now append all items (redistributed existing + new) to image_states
        # Check for duplicates before appending to avoid adding the same items multiple times
        for page_idx, items in scene_items_by_page.items():
            file_path = self.image_file_paths[page_idx]
            
            # Get existing items that were redistributed
            existing_rectangles = self.main_controller.image_states[file_path]['viewer_state']['rectangles']
            existing_brush_strokes = self.main_controller.image_states[file_path]['brush_strokes']
            existing_text_blocks = self.main_controller.image_states[file_path]['blk_list']
            
            # Append rectangles (check for duplicates)
            for rect in items['rectangles']:
                if not self.rectangle_manager.is_duplicate_rectangle(rect, existing_rectangles):
                    existing_rectangles.append(rect)
            
            # Append text items (existing + new, with clipping - check for duplicates)
            existing_text_items = self.main_controller.image_states[file_path]['viewer_state']['text_items_state']
            for text_item in items['text_items']:
                if not self.text_item_manager.is_duplicate_text_item(text_item, existing_text_items):
                    existing_text_items.append(text_item)
            
            # Append brush strokes (check for duplicates)
            for stroke in items['brush_strokes']:
                if not self.brush_stroke_manager.is_duplicate_brush_stroke(stroke, existing_brush_strokes):
                    existing_brush_strokes.append(stroke)
            
            # Append text blocks (check for duplicates)
            for blk in items['text_blocks']:
                if not self.text_block_manager.is_duplicate_text_block(blk, existing_text_blocks):
                    existing_text_blocks.append(blk)
        
        # Update text block's blk.text to match clipped text items
        self._update_text_blocks_with_clipped_text()
    
    def _update_text_blocks_with_clipped_text(self):
        """
        Update text blocks' blk.text to match the plain text of their corresponding clipped text items.
        This ensures that after clipping, the text block content reflects the actual visible text.
        Uses the final state in image_states which contains all items (redistributed existing + new).
        """
        for page_idx in range(len(self.image_file_paths)):
            file_path = self.image_file_paths[page_idx]
            
            # Get all final items from image_states (redistributed existing + new)
            text_items = self.main_controller.image_states[file_path]['viewer_state']['text_items_state']
            text_blocks = self.main_controller.image_states[file_path]['blk_list']
            
            for text_item_data in text_items:
                # Extract position and rotation from text item
                text_item_pos = text_item_data['position']
                text_item_rotation = text_item_data.get('rotation', 0)
                
                # Find corresponding text block by position and rotation
                matching_text_block = None
                for blk in text_blocks:
                    # Text block coordinates are already in page-local coordinates when stored in image_states
                    blk_pos_page_local = [blk.xyxy[0], blk.xyxy[1]]
                    blk_width = blk.xyxy[2] - blk.xyxy[0]
                    
                    # Check if positions, width, and rotations match (with small tolerance)
                    pos_tolerance = 5.0  # Allow small differences due to floating point precision
                    rotation_tolerance = 1.0
                    width_tolerance = 10.0  # Allow small differences in width
                    
                    text_item_width = text_item_data.get('width', 0)
                    
                    if (abs(blk_pos_page_local[0] - text_item_pos[0]) <= pos_tolerance and
                        abs(blk_pos_page_local[1] - text_item_pos[1]) <= pos_tolerance and
                        abs(blk.angle - text_item_rotation) <= rotation_tolerance and
                        abs(blk_width - text_item_width) <= width_tolerance):
                        matching_text_block = blk
                        break
                
                # Update the text block's text if a match is found
                if matching_text_block:
                    # Extract plain text from the text item's HTML/rich text
                    text_content = text_item_data.get('text', '')
                    
                    # Convert HTML to plain text if needed
                    if self._is_html(text_content):
                        temp_doc = QTextDocument()
                        temp_doc.setHtml(text_content)
                        plain_text = temp_doc.toPlainText()
                    else:
                        plain_text = text_content
                    
                    # Update the text block's text
                    matching_text_block.text = plain_text
    
    def _is_html(self, text):
        """Check if text contains HTML tags."""
        import re
        return bool(re.search(r'<[^>]+>', text))
    
    def clear(self):
        """Clear all scene item management state."""
        self.image_file_paths.clear()
        
        # Clear all specialized managers
        self.rectangle_manager.clear()
        self.text_item_manager.clear()
        self.brush_stroke_manager.clear()
        self.text_block_manager.clear()
        self.patch_manager.clear()