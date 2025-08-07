"""
Text Item Manager for Webtoon Scene Items

Handles text item management with state storage for webtoon mode.
"""

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QTextDocument, QTextCursor
from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.text.text_item_properties import TextItemProperties


class TextItemManager:
    """Manages text items for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter, image_loader):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self.image_loader = image_loader
        self._scene = viewer._scene
        
        # Main controller reference (set by scene item manager)
        self.main_controller = None
    
    def initialize(self):
        """Initialize or reset the text item manager state."""
        pass
    
    def load_text_items(self, state: dict, page_idx: int):
        """Load text items for a specific page."""
        text_items = state.get('viewer_state', {}).get('text_items_state', [])
        for text_data in text_items:
            # Convert from page-local coordinates to scene coordinates
            page_local_pos = QPointF(*text_data['position'])
            scene_pos = self.coordinate_converter.page_local_to_scene_position(page_local_pos, page_idx)
            
            # Update position in the data and create TextItemProperties
            text_data = text_data.copy()  # Don't modify the original
            text_data['position'] = (scene_pos.x(), scene_pos.y())
            text_item = self.viewer.add_text_item(text_data)
    
    def unload_text_items(self, page_idx: int, page_y: float, page_bottom: float, file_path: str):
        """Unload text items for a specific page."""
        text_items_to_remove = []
        text_items_data = []
        
        for item in self.viewer._scene.items():
            if isinstance(item, TextBlockItem):
                text_item = item
                text_y = text_item.pos().y()
                
                # Check if text item is on this page
                if text_y >= page_y and text_y < page_bottom:
                    # Convert to page-local coordinates
                    scene_pos = text_item.pos()
                    page_local_pos = self.coordinate_converter.scene_to_page_local_position(scene_pos, page_idx)
                    
                    # Use TextItemProperties for consistent serialization
                    text_props = TextItemProperties.from_text_item(text_item)
                    # Override position to use page-local coordinates
                    text_props.position = (page_local_pos.x(), page_local_pos.y())
                    
                    text_items_data.append(text_props.to_dict())
                    text_items_to_remove.append(text_item)
        
        # Store text items in image_states
        self.main_controller.image_states[file_path]['viewer_state']['text_items_state'] = text_items_data
        
        # Remove text items from scene and viewer list
        for text_item in text_items_to_remove:
            self._scene.removeItem(text_item)
            if text_item in self.viewer.text_items:
                self.viewer.text_items.remove(text_item)
    
    def clear(self):
        """Clear all text item management state."""
        pass
    
    def _split_text_by_lines(self, text_item, clip_ratios: dict) -> str:
        """
        Split text content based on clipping ratios for vertical clipping.
        This handles line-based splitting while preserving rich text formatting.
        """
        # Get the text document to work with cursor for precise text selection
        document = text_item.document()
        full_html = text_item.toHtml()
        full_text = document.toPlainText()
        
        # For simple text splitting, we split by lines and take the appropriate portion
        lines = full_text.split('\n')
        if not lines:
            return ""
        
        # Calculate which lines to include based on top/bottom clip ratios
        total_lines = len(lines)
        start_line = int(clip_ratios['top'] * total_lines)
        end_line = int(clip_ratios['bottom'] * total_lines)
        
        # Ensure we have valid line indices
        start_line = max(0, min(start_line, total_lines - 1))
        end_line = max(start_line, min(end_line, total_lines))
        
        # Handle edge case where clipping results in no lines
        if start_line >= end_line:
            # If clipping is very small, try to include at least one line
            if clip_ratios['bottom'] - clip_ratios['top'] > 0.1:  # At least 10% of text height
                if clip_ratios['top'] < 0.5:
                    end_line = max(1, start_line + 1)
                else:
                    start_line = max(0, end_line - 1)
            else:
                return ""  # Text portion too small to be meaningful
        
        # Calculate character positions for the line range
        start_char_pos = sum(len(line) + 1 for line in lines[:start_line]) - (1 if start_line > 0 else 0)
        end_char_pos = sum(len(line) + 1 for line in lines[:end_line]) - 1
        
        # Use QTextCursor to select and extract formatted text
        cursor = QTextCursor(document)
        cursor.setPosition(start_char_pos)
        cursor.setPosition(end_char_pos, QTextCursor.KeepAnchor)
        
        # Create a new document with just the selected content
        temp_doc = QTextDocument()
        temp_cursor = QTextCursor(temp_doc)
        temp_cursor.insertFragment(cursor.selection())
        
        return temp_doc.toHtml()
    
    def _split_text_by_characters(self, text_item, clip_ratios: dict) -> str:
        """
        Split text content based on clipping ratios for horizontal clipping.
        This preserves word boundaries when possible while maintaining rich text formatting.
        """
        document = text_item.document()
        full_text = document.toPlainText()
        
        # For horizontal clipping, estimate character positions
        text_length = len(full_text)
        start_pos = int(clip_ratios['left'] * text_length)
        end_pos = int(clip_ratios['right'] * text_length)
        
        # Ensure valid positions
        start_pos = max(0, min(start_pos, text_length))
        end_pos = max(start_pos, min(end_pos, text_length))
        
        if start_pos >= end_pos:
            return ""
        
        # If we're not at the start, try to find a word boundary
        if start_pos > 0 and start_pos < text_length:
            # Look backwards for word boundary
            word_start = start_pos
            while word_start > 0 and not full_text[word_start - 1].isspace():
                word_start -= 1
            # Don't go too far back
            if start_pos - word_start < 20:  # Reasonable limit
                start_pos = word_start
        
        # If we're not at the end, try to find a word boundary
        if end_pos < text_length:
            # Look forwards for word boundary
            word_end = end_pos
            while word_end < text_length and not full_text[word_end].isspace():
                word_end += 1
            # Don't go too far forward
            if word_end - end_pos < 20:  # Reasonable limit
                end_pos = word_end
        
        # Use QTextCursor to select and extract formatted text
        cursor = QTextCursor(document)
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        
        # Create a new document with just the selected content
        temp_doc = QTextDocument()
        temp_cursor = QTextCursor(temp_doc)
        temp_cursor.insertFragment(cursor.selection())
        
        return temp_doc.toHtml()
    
    def _create_clipped_text_data(self, original_text_data: dict, clipped_text: str, 
                                 clipped_position: tuple[float, float], 
                                 clipped_size: tuple[float, float]) -> dict:
        """Create a new text data dictionary for a clipped portion of text."""
        clipped_data = original_text_data.copy()
        clipped_data.update({
            'text': clipped_text,
            'position': clipped_position,
            'width': clipped_size[0],
            # Note: Height will be recalculated when the text item is recreated
        })
        return clipped_data
    
    def save_text_items_to_states(self, scene_items_by_page: dict):
        """Save text items to appropriate page states with clipping support."""
        for item in self.viewer._scene.items():
            if isinstance(item, TextBlockItem):
                text_item = item
                # Get all pages this text item intersects with
                text_scene_bounds = QRectF(
                    text_item.pos().x(),
                    text_item.pos().y(), 
                    text_item.boundingRect().width(),
                    text_item.boundingRect().height()
                )
                
                intersecting_pages = self.layout_manager.get_pages_for_scene_bounds(text_scene_bounds)
                
                # Create base text properties using TextItemProperties for consistency
                base_text_props = TextItemProperties.from_text_item(text_item)
                base_text_data = base_text_props.to_dict()
                
                # Convert intersecting_pages to list if it's a set
                intersecting_pages_list = list(intersecting_pages) if isinstance(intersecting_pages, set) else intersecting_pages
                
                # If text only intersects one page, no clipping needed
                if len(intersecting_pages_list) == 1:
                    page_idx = intersecting_pages_list[0]
                    if 0 <= page_idx < len(self.image_loader.image_file_paths):
                        scene_pos = text_item.pos()
                        page_local_pos = self.coordinate_converter.scene_to_page_local_position(scene_pos, page_idx)
                        
                        base_text_data.update({
                            'position': (page_local_pos.x(), page_local_pos.y()),
                            'width': text_item.boundingRect().width(),
                            'height': text_item.boundingRect().height()
                        })
                        scene_items_by_page[page_idx]['text_items'].append(base_text_data)
                else:
                    # Text spans multiple pages - need to clip and split
                    for page_idx in intersecting_pages_list:
                        if 0 <= page_idx < len(self.image_loader.image_file_paths):
                            # Get clipping information for this page
                            clip_info = self.coordinate_converter.clip_text_item_to_page(text_item, page_idx)
                            if clip_info:
                                # Determine if this is primarily vertical or horizontal clipping
                                clip_ratios = clip_info['clip_ratios']
                                vertical_clip = (clip_ratios['top'] > 0.01 or clip_ratios['bottom'] < 0.99)
                                horizontal_clip = (clip_ratios['left'] > 0.01 or clip_ratios['right'] < 0.99)
                                
                                # Split the text appropriately
                                if vertical_clip and not horizontal_clip:
                                    # Primarily vertical clipping - split by lines
                                    clipped_text = self._split_text_by_lines(text_item, clip_ratios)
                                elif horizontal_clip:
                                    # Horizontal clipping involved - split by characters (more complex)
                                    clipped_text = self._split_text_by_characters(text_item, clip_ratios)
                                else:
                                    # Minimal clipping - use full text
                                    clipped_text = text_item.toHtml()
                                
                                # Only add if we have meaningful text content
                                # For HTML content, we need to check if there's actual text, not just HTML tags
                                if clipped_text.strip():
                                    # Create a temporary document to extract plain text for validation
                                    temp_doc = QTextDocument()
                                    temp_doc.setHtml(clipped_text)
                                    if temp_doc.toPlainText().strip():  # Check if there's actual text content
                                        clipped_bounds = clip_info['clipped_bounds']
                                        clipped_text_data = self._create_clipped_text_data(
                                            base_text_data,
                                            clipped_text,
                                            (clipped_bounds[0], clipped_bounds[1]),  # position
                                            (clipped_bounds[2], clipped_bounds[3])   # size
                                        )
                                        scene_items_by_page[page_idx]['text_items'].append(clipped_text_data)

    def redistribute_existing_text_items(self, existing_text_items_by_page: dict, scene_items_by_page: dict):
        """Redistribute existing text items to all pages they intersect with after clipping."""
        processed_text_items = set()  # Track processed text items to avoid duplicates
        print(f"Redistributing existing text items with clipping")
        
        for original_page_idx, text_items in existing_text_items_by_page.items():
            for text_item_data in text_items:
                # Create a unique identifier for this text item to avoid duplicates
                text_id = id(text_item_data)
                if text_id in processed_text_items:
                    continue
                processed_text_items.add(text_id)
                
                if 'position' not in text_item_data:
                    # Keep invalid text item on its original page
                    scene_items_by_page[original_page_idx]['text_items'].append(text_item_data)
                    continue
                
                # Convert from page-local to scene coordinates
                local_x, local_y = text_item_data['position']
                scene_pos = self.coordinate_converter.page_local_to_scene_position(QPointF(local_x, local_y), original_page_idx)
                
                # Estimate text dimensions (width is stored, height needs to be estimated)
                text_width = text_item_data.get('width', 100)  # fallback width
                # Rough height estimation based on font size and line count
                font_size = text_item_data.get('font_size', 12)
                text_content = text_item_data.get('text', '')
                line_count = max(1, text_content.count('\n') + 1) if isinstance(text_content, str) else 1
                estimated_height = font_size * line_count * text_item_data.get('line_spacing', 1.2)
                
                # Create scene bounds for the text item
                text_scene_bounds = QRectF(scene_pos.x(), scene_pos.y(), text_width, estimated_height)
                intersecting_pages = self.layout_manager.get_pages_for_scene_bounds(text_scene_bounds)
                
                # Create a mock text item for clipping calculations
                class MockTextItem:
                    def __init__(self, x, y, width, height, text_data):
                        self._pos = QPointF(x, y)
                        self._bounding_rect = QRectF(0, 0, width, height)
                        self._text_data = text_data
                        # Create a proper document for HTML content
                        self._document = QTextDocument()
                        # Set the text as HTML to preserve formatting
                        text_content = text_data.get('text', '')
                        if text_content:
                            self._document.setHtml(text_content)
                    
                    def pos(self):
                        return self._pos
                    
                    def boundingRect(self):
                        return self._bounding_rect
                    
                    def document(self):
                        return self._document
                    
                    def toHtml(self):
                        return self._document.toHtml()
                    
                    def rotation(self):
                        return self._text_data.get('rotation', 0.0)
                    
                    def scale(self):
                        return self._text_data.get('scale', 1.0)
                    
                    def transformOriginPoint(self):
                        origin = self._text_data.get('transform_origin', (0, 0))
                        return QPointF(origin[0], origin[1])
                
                mock_text_item = MockTextItem(scene_pos.x(), scene_pos.y(), text_width, estimated_height, text_item_data)
                
                # Convert intersecting_pages to list if it's a set
                intersecting_pages_list = list(intersecting_pages) if isinstance(intersecting_pages, set) else intersecting_pages
                
                # If text only intersects one page, no clipping needed
                if len(intersecting_pages_list) == 1:
                    page_idx = intersecting_pages_list[0]
                    if 0 <= page_idx < len(self.image_loader.image_file_paths):
                        # Convert back to page-local coordinates for the target page
                        target_page_local_pos = self.coordinate_converter.scene_to_page_local_position(scene_pos, page_idx)
                        clipped_text_data = text_item_data.copy()
                        clipped_text_data['position'] = (target_page_local_pos.x(), target_page_local_pos.y())
                        scene_items_by_page[page_idx]['text_items'].append(clipped_text_data)
                else:
                    # Text spans multiple pages - need to clip and split
                    for page_idx in intersecting_pages_list:
                        if 0 <= page_idx < len(self.image_loader.image_file_paths):
                            clip_info = self.coordinate_converter.clip_text_item_to_page(mock_text_item, page_idx)
                            if clip_info:
                                # Use text item manager's splitting logic
                                clip_ratios = clip_info['clip_ratios']
                                vertical_clip = (clip_ratios['top'] > 0.01 or clip_ratios['bottom'] < 0.99)
                                horizontal_clip = (clip_ratios['left'] > 0.01 or clip_ratios['right'] < 0.99)
                                
                                # Split the text appropriately
                                if vertical_clip and not horizontal_clip:
                                    clipped_text = self._split_text_by_lines(mock_text_item, clip_ratios)
                                elif horizontal_clip:
                                    clipped_text = self._split_text_by_characters(mock_text_item, clip_ratios)
                                else:
                                    clipped_text = text_item_data.get('text', '')
                                
                                # Only add if we have meaningful text content
                                # For HTML content, we need to check if there's actual text, not just HTML tags
                                if clipped_text.strip():
                                    # Create a temporary document to extract plain text for validation
                                    temp_doc = QTextDocument()
                                    temp_doc.setHtml(clipped_text)
                                    if temp_doc.toPlainText().strip():  # Check if there's actual text content
                                        clipped_bounds = clip_info['clipped_bounds']
                                        clipped_text_data = self._create_clipped_text_data(
                                            text_item_data,
                                            clipped_text,
                                            (clipped_bounds[0], clipped_bounds[1]),
                                            (clipped_bounds[2], clipped_bounds[3])
                                        )
                                        scene_items_by_page[page_idx]['text_items'].append(clipped_text_data)

    def is_duplicate_text_item(self, new_text_item, existing_text_items, margin=5):
        """Check if a text item is a duplicate of any existing text item within margin."""
        if 'position' not in new_text_item:
            return False
            
        new_x, new_y = new_text_item['position']
        new_text = new_text_item.get('text', '')
        new_width = new_text_item.get('width', 0)
        new_angle = new_text_item.get('rotation', 0)
        
        for existing_text_item in existing_text_items:
            if 'position' not in existing_text_item:
                continue
                
            ex_x, ex_y = existing_text_item['position']
            ex_text = existing_text_item.get('text', '')
            ex_width = existing_text_item.get('width', 0)
            ex_angle = existing_text_item.get('rotation', 0)    
            
            # Check if position is within margin and text matches
            if (abs(new_x - ex_x) <= margin and 
                abs(new_y - ex_y) <= margin and 
                abs(new_width - ex_width) <= margin and 
                abs(new_angle - ex_angle) <= 1.0 and
                new_text == ex_text):
                return True
        return False
