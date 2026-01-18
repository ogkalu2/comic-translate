"""
Scene Item Manager for Webtoon Manager

Handles scene items (rectangles, text, brush strokes, patches) management with state storage.
Refactored to delegate to specialized managers and reference live data from other main managers.
"""

from PySide6.QtGui import QTextDocument
from .rectangle_manager import RectangleManager
from .text_item_manager import TextItemManager
from .brush_stroke_manager import BrushStrokeManager
from .text_block_manager import TextBlockManager
from .patch_manager import PatchManager


class SceneItemManager:
    """Manages scene items for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter, image_loader):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self.image_loader = image_loader # Central source for image file paths and data
        self._scene = viewer._scene
        
        # Main controller reference
        self.main_controller = None
        
        # Initialize specialized managers, passing all necessary references
        self.rectangle_manager = RectangleManager(viewer, layout_manager, coordinate_converter, image_loader)
        self.text_item_manager = TextItemManager(viewer, layout_manager, coordinate_converter, image_loader)
        self.brush_stroke_manager = BrushStrokeManager(viewer, layout_manager, coordinate_converter, image_loader)
        self.text_block_manager = TextBlockManager(viewer, layout_manager, coordinate_converter, image_loader)
        self.patch_manager = PatchManager(viewer, layout_manager, coordinate_converter, image_loader)
    
    def initialize(self):
        """Initialize all specialized scene item managers."""
        self.rectangle_manager.initialize()
        self.text_item_manager.initialize()
        self.brush_stroke_manager.initialize()
        self.text_block_manager.initialize()
        self.patch_manager.initialize()
        
    def set_main_controller(self, controller):
        """Set the main controller reference for self and all sub-managers."""
        self.main_controller = controller
        self.rectangle_manager.main_controller = controller
        self.text_item_manager.main_controller = controller
        self.brush_stroke_manager.main_controller = controller
        self.text_block_manager.main_controller = controller
        self.patch_manager.main_controller = controller
    
    def load_page_scene_items(self, page_idx: int):
        """Load scene items (rectangles, text, brush strokes, patches) for a specific page."""
        if not self.main_controller:
            return
            
        # Access file paths directly from the image_loader (the data owner)
        file_path = self.image_loader.image_file_paths[page_idx]
        
        # Check if this page has stored state in image_states
        if file_path not in self.main_controller.image_states:
            return
            
        state = self.main_controller.image_states[file_path]
        
        # Load TextBlock objects for this page first (needed for text items)
        self.text_block_manager.load_text_blocks(page_idx)
        
        # Load rectangles, text items, brush strokes, and patches for this page
        self.rectangle_manager.load_rectangles(state, page_idx)
        self.text_item_manager.load_text_items(state, page_idx)
        self.brush_stroke_manager.load_brush_strokes(state, page_idx)
        self.patch_manager.load_patches(page_idx)
    
    def unload_page_scene_items(self, page_idx: int):
        """Unload scene items for a specific page (saving state if needed)."""
        print(f"Unloading scene items for page {page_idx}")
        
        if not self.main_controller or page_idx >= len(self.image_loader.image_file_paths):
            return
            
        file_path = self.image_loader.image_file_paths[page_idx]
        
        # Ensure image_states entry exists
        if file_path not in self.main_controller.image_states:
            self.main_controller.image_states[file_path] = {}
        if 'viewer_state' not in self.main_controller.image_states[file_path]:
            self.main_controller.image_states[file_path]['viewer_state'] = {}
        
        # Determine page bounds for this page from the layout_manager
        page_y = self.layout_manager.image_positions[page_idx]
        page_bottom = page_y + self.layout_manager.image_heights[page_idx]
        
        # Unload all item types
        self.text_block_manager.unload_text_blocks(page_idx, page_y, page_bottom, file_path)
        self.rectangle_manager.unload_rectangles(page_idx, page_y, page_bottom, file_path)
        self.text_item_manager.unload_text_items(page_idx, page_y, page_bottom, file_path)
        self.brush_stroke_manager.unload_brush_strokes(page_idx, page_y, page_bottom, file_path)
        self.patch_manager.unload_patches(page_idx)
    
    def save_all_scene_items_to_states(self):
        """
        Save all currently visible scene items to their appropriate page states.
        This method is called before major state changes (like mode switching or page deletion).
        """
        if not self.main_controller:
            return

        # Initialize a dictionary to hold categorized items for each page
        scene_items_by_page = {
            i: {'rectangles': [], 'text_items': [], 'brush_strokes': [], 'text_blocks': []}
            for i in range(len(self.image_loader.image_file_paths))
        }

        # Delegate saving of currently visible items to sub-managers
        self.text_block_manager.save_text_blocks_to_states(scene_items_by_page)
        self.rectangle_manager.save_rectangles_to_states(scene_items_by_page)
        self.text_item_manager.save_text_items_to_states(scene_items_by_page)
        self.brush_stroke_manager.save_brush_strokes_to_states(scene_items_by_page)

        # Collect all existing items from image_states to be redistributed
        all_existing_rects = []
        all_existing_brush_strokes = []
        all_existing_blk_list = []
        existing_text_items_by_page = {}
        
        for page_idx in range(len(self.image_loader.image_file_paths)):
            file_path = self.image_loader.image_file_paths[page_idx]
            if file_path not in self.main_controller.image_states:
                self.main_controller.image_states[file_path] = {'viewer_state': {}}

            state = self.main_controller.image_states[file_path]
            viewer_state = state.setdefault('viewer_state', {})
            
            for rect in viewer_state.get('rectangles', []): all_existing_rects.append((rect, page_idx))
            for stroke in state.get('brush_strokes', []): all_existing_brush_strokes.append((stroke, page_idx))
            for blk in state.get('blk_list', []): all_existing_blk_list.append((blk, page_idx))
            existing_text_items_by_page[page_idx] = viewer_state.get('text_items_state', [])
            
            # Clear existing items, they will be repopulated after clipping and redistribution
            viewer_state['rectangles'] = []
            state['brush_strokes'] = []
            state['blk_list'] = []
            viewer_state['text_items_state'] = []
        
        # Redistribute existing items across pages they intersect with
        self.rectangle_manager.redistribute_existing_rectangles(all_existing_rects, scene_items_by_page)
        self.brush_stroke_manager.redistribute_existing_brush_strokes(all_existing_brush_strokes, scene_items_by_page)
        self.text_block_manager.redistribute_existing_text_blocks(all_existing_blk_list, scene_items_by_page)
        self.text_item_manager.redistribute_existing_text_items(existing_text_items_by_page, scene_items_by_page)
        
        # Append all categorized items back to the main image_states, avoiding duplicates
        for page_idx, items in scene_items_by_page.items():
            file_path = self.image_loader.image_file_paths[page_idx]
            state = self.main_controller.image_states[file_path]
            viewer_state = state['viewer_state']
            
            # Use sets for faster duplicate checking where possible
            existing_rectangles = viewer_state['rectangles']
            for rect in items['rectangles']:
                if not self.rectangle_manager.is_duplicate_rectangle(rect, existing_rectangles):
                    existing_rectangles.append(rect)
            
            existing_text_items = viewer_state['text_items_state']
            for text_item in items['text_items']:
                if not self.text_item_manager.is_duplicate_text_item(text_item, existing_text_items):
                    existing_text_items.append(text_item)

            existing_brush_strokes = state['brush_strokes']
            for stroke in items['brush_strokes']:
                if not self.brush_stroke_manager.is_duplicate_brush_stroke(stroke, existing_brush_strokes):
                    existing_brush_strokes.append(stroke)

            existing_text_blocks = state['blk_list']
            for blk in items['text_blocks']:
                if not self.text_block_manager.is_duplicate_text_block(blk, existing_text_blocks):
                    existing_text_blocks.append(blk)
        
        # Final consistency check
        self._update_text_blocks_with_clipped_text()
    
    def merge_clipped_items_back(self):
        """
        Merge clipped items back to their original form when switching to webtoon mode.
        This identifies items that were split across page boundaries in regular mode
        and merges them back so they display as whole items in webtoon mode.
        """
        if not self.main_controller:
            return
        
        # Use manager-specific merge methods
        self.text_item_manager.merge_clipped_text_items()
        self.rectangle_manager.merge_clipped_rectangles()
        self.brush_stroke_manager.merge_clipped_brush_strokes()
        self.text_block_manager.merge_clipped_text_blocks()

    def _update_text_blocks_with_clipped_text(self):
        """
        Update text blocks' text to match the plain text of their corresponding clipped text items.
        """
        if not self.main_controller: 
            return
        
        for page_idx in range(len(self.image_loader.image_file_paths)):
            file_path = self.image_loader.image_file_paths[page_idx]
            state = self.main_controller.image_states.get(file_path, {})
            text_items = state.get('viewer_state', {}).get('text_items_state', [])
            text_blocks = state.get('blk_list', [])
            
            for text_item_data in text_items:
                text_item_pos = text_item_data['position']
                text_item_rotation = text_item_data.get('rotation', 0)
                
                for blk in text_blocks:
                    blk_pos_page_local = [blk.xyxy[0], blk.xyxy[1]]
                    
                    # Check if positions and rotations match (with tolerance)
                    if (abs(blk_pos_page_local[0] - text_item_pos[0]) < 5.0 and
                        abs(blk_pos_page_local[1] - text_item_pos[1]) < 5.0 and
                        abs(blk.angle - text_item_rotation) < 1.0):
                        
                        text_content = text_item_data.get('text', '')
                        plain_text = text_content
                        if '<' in text_content and '>' in text_content: # Simple HTML check
                            temp_doc = QTextDocument()
                            temp_doc.setHtml(text_content)
                            plain_text = temp_doc.toPlainText()
                        
                        blk.translation = plain_text
                        break
    
    def _is_html(self, text):
        """Check if text contains HTML tags."""
        import re
        return bool(re.search(r'<[^>]+>', text))
    
    def clear(self):
        """Clear all scene item management state."""
        self.rectangle_manager.clear()
        self.text_item_manager.clear()
        self.brush_stroke_manager.clear()
        self.text_block_manager.clear()
        self.patch_manager.clear()

    def _clear_all_scene_items(self):
        """Clear all managed scene items from the QGraphicsScene."""
        if not self._scene:
            return
            
        items_to_remove = []
        for item in self._scene.items():
            # Exclude the main image pixmap items and their placeholders
            if item in self.image_loader.image_items.values() or item in self.image_loader.placeholder_items.values():
                continue
            items_to_remove.append(item)
        
        for item in items_to_remove:
            self._scene.removeItem(item)

        self.patch_manager.clear()