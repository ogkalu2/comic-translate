"""
Rectangle Manager for Webtoon Scene Items

Handles rectangle management with state storage for webtoon mode.
"""

from typing import List, Dict
from app.ui.canvas.rectangle import MoveableRectItem
from PySide6.QtCore import QPointF, QRectF


class RectangleManager:
    """Manages rectangles for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter, image_loader):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self.image_loader = image_loader
        self._scene = viewer._scene
        
        # Main controller reference (set by scene item manager)
        self.main_controller = None
    
    def initialize(self):
        """Initialize or reset the rectangle manager state."""
        pass
    
    def load_rectangles(self, state: Dict, page_idx: int):
        """Load rectangles for a specific page."""
        rectangles = state.get('viewer_state', {}).get('rectangles', [])
        for rect_data in rectangles:
            # Convert from page-local coordinates to scene coordinates
            page_local_pos = QPointF(rect_data['rect'][0], rect_data['rect'][1])
            scene_pos = self.coordinate_converter.page_local_to_scene_position(page_local_pos, page_idx)
            
            # Use viewer's add_rectangle method for consistency
            rect = QRectF(0, 0, rect_data['rect'][2], rect_data['rect'][3])
            origin = None
            if 'transform_origin' in rect_data:
                origin = QPointF(*rect_data['transform_origin'])
            
            rect_item = self.viewer.add_rectangle(
                rect=rect,
                position=scene_pos, 
                rotation=rect_data['rotation'],
                origin=origin
            )
            
            # Connect signals - the viewer's add_rectangle should handle this
            self.viewer.connect_rect_item.emit(rect_item)
    
    def unload_rectangles(self, page_idx: int, page_y: float, page_bottom: float, file_path: str):
        """Unload rectangles for a specific page."""

        rectangles_to_remove = []
        rectangles_data = []

        for item in self.viewer._scene.items():
            if isinstance(item, MoveableRectItem):
                rect_item = item
        
                rect_y = rect_item.pos().y()
                rect_height = rect_item.boundingRect().height()
                rect_bottom = rect_y + rect_height
                
                # Check if rectangle is primarily on this page
                if (rect_y >= page_y and rect_y < page_bottom) or \
                (rect_bottom > page_y and rect_bottom <= page_bottom) or \
                (rect_y < page_y and rect_bottom > page_bottom):
                    
                    # Convert to page-local coordinates
                    scene_pos = rect_item.pos()
                    page_local_pos = self.coordinate_converter.scene_to_page_local_position(scene_pos, page_idx)
                    
                    rect_data = {
                        'rect': (page_local_pos.x(), page_local_pos.y(), 
                                rect_item.boundingRect().width(), rect_item.boundingRect().height()),
                        'rotation': rect_item.rotation(),
                        'transform_origin': (rect_item.transformOriginPoint().x(), 
                                        rect_item.transformOriginPoint().y())
                    }
                    rectangles_data.append(rect_data)
                    rectangles_to_remove.append(rect_item)
        
        # Store rectangles in image_states
        self.main_controller.image_states[file_path]['viewer_state']['rectangles'] = rectangles_data
        
        # Remove rectangle items from scene and viewer list
        for rect_item in rectangles_to_remove:
            self._scene.removeItem(rect_item)
            if rect_item in self.viewer.rectangles:
                self.viewer.rectangles.remove(rect_item)
            if self.viewer.selected_rect == rect_item:
                self.viewer.selected_rect = None
    
    def save_rectangles_to_states(self, scene_items_by_page: Dict):
        """Save rectangles to appropriate page states."""
        for item in self.viewer._scene.items():
            if isinstance(item, MoveableRectItem):
                rect_item = item
                # Find all pages this rectangle intersects with
                rect_bounds = rect_item.boundingRect()
                rect_scene_bounds = QRectF(
                    rect_item.pos().x(), 
                    rect_item.pos().y(),
                    rect_bounds.width(), 
                    rect_bounds.height()
                )
                intersecting_pages = self.layout_manager.get_pages_for_scene_bounds(rect_scene_bounds)
                
                # Add clipped version to each intersecting page
                for page_idx in intersecting_pages:
                    if 0 <= page_idx < len(self.image_loader.image_file_paths):
                        clipped_rect = self.coordinate_converter.clip_rectangle_to_page(rect_item, page_idx)
                        if clipped_rect and clipped_rect[2] > 0 and clipped_rect[3] > 0:
                            rect_data = {
                                'rect': clipped_rect,
                                'rotation': rect_item.rotation(),
                                'transform_origin': (rect_item.transformOriginPoint().x(), 
                                                rect_item.transformOriginPoint().y())
                            }
                            scene_items_by_page[page_idx]['rectangles'].append(rect_data)
    
    def clear(self):
        """Clear all rectangle management state."""
        pass

    def redistribute_existing_rectangles(self, all_existing_rects: List[tuple], scene_items_by_page: Dict):
        """Redistribute existing rectangles to all pages they intersect with after clipping."""
        processed_rects = set()  # Track processed rectangles to avoid duplicates
        
        for rect_data, original_page_idx in all_existing_rects:
            # Create a unique identifier for this rectangle to avoid duplicates
            rect_id = id(rect_data)
            if rect_id in processed_rects:
                continue
            processed_rects.add(rect_id)
            
            if 'rect' not in rect_data or len(rect_data['rect']) < 4:
                # Keep invalid rectangle on its original page
                scene_items_by_page[original_page_idx]['rectangles'].append(rect_data)
                continue
                
            # Convert from page-local to scene coordinates
            local_x, local_y, local_width, local_height = rect_data['rect']
            scene_top_left = self.coordinate_converter.page_local_to_scene_position(QPointF(local_x, local_y), original_page_idx)
            scene_bounds = QRectF(scene_top_left.x(), scene_top_left.y(), local_width, local_height)
            
            # Find all pages this rectangle intersects with
            intersecting_pages = self.layout_manager.get_pages_for_scene_bounds(scene_bounds)
            
            # Create mock rect item for clipping
            class MockRectItem:
                def __init__(self, x, y, width, height):
                    self._pos = QPointF(x, y)
                    self._rect = QRectF(0, 0, width, height)
                
                def pos(self):
                    return self._pos
                    
                def boundingRect(self):
                    return self._rect
                    
                def rotation(self):
                    return rect_data.get('rotation', 0.0)
                    
                def transformOriginPoint(self):
                    origin = rect_data.get('transform_origin', (0, 0))
                    return QPointF(origin[0], origin[1])
            
            mock_rect = MockRectItem(scene_top_left.x(), scene_top_left.y(), local_width, local_height)
            
            # Add clipped version to each intersecting page (following save_rectangles_to_states pattern)
            for page_idx in intersecting_pages:
                if 0 <= page_idx < len(self.image_loader.image_file_paths):
                    clipped_rect = self.coordinate_converter.clip_rectangle_to_page(mock_rect, page_idx)
                    if clipped_rect and clipped_rect[2] > 0 and clipped_rect[3] > 0:
                        clipped_rect_data = {
                            'rect': clipped_rect,
                            'rotation': rect_data.get('rotation', 0.0),
                            'transform_origin': rect_data.get('transform_origin', (0, 0))
                        }
                        scene_items_by_page[page_idx]['rectangles'].append(clipped_rect_data)

    def is_duplicate_rectangle(self, new_rect, existing_rects, margin=5):
        """Check if a rectangle is a duplicate of any existing rectangle within margin."""
        if 'rect' not in new_rect or len(new_rect['rect']) < 4:
            return False
            
        new_x, new_y, new_width, new_height = new_rect['rect']
        new_rotation = new_rect.get('rotation', 0.0)
        
        for existing_rect in existing_rects:
            if 'rect' not in existing_rect or len(existing_rect['rect']) < 4:
                continue
                
            ex_x, ex_y, ex_width, ex_height = existing_rect['rect']
            ex_rotation = existing_rect.get('rotation', 0.0)
            
            # Check if coordinates are within margin and rotation matches
            if (abs(new_x - ex_x) <= margin and 
                abs(new_y - ex_y) <= margin and 
                abs(new_width - ex_width) <= margin and 
                abs(new_height - ex_height) <= margin and
                abs(new_rotation - ex_rotation) <= 1.0): 
                return True
        return False

    def merge_clipped_rectangles(self):
        """Merge rectangle items that were clipped across page boundaries in regular mode."""
        if not self.main_controller:
            return
            
        all_rectangles = []
        
        # Collect all rectangles from all pages
        for page_idx in range(len(self.image_loader.image_file_paths)):
            file_path = self.image_loader.image_file_paths[page_idx]
            state = self.main_controller.image_states.get(file_path, {})
            rectangles = state.get('viewer_state', {}).get('rectangles', [])
            
            for rect_data in rectangles:
                if 'rect' not in rect_data or len(rect_data['rect']) < 4:
                    continue
                    
                # Convert to scene coordinates
                local_x, local_y, width, height = rect_data['rect']
                local_pos = QPointF(local_x, local_y)
                scene_pos = self.coordinate_converter.page_local_to_scene_position(local_pos, page_idx)
                
                all_rectangles.append({
                    'data': rect_data,
                    'page_idx': page_idx,
                    'scene_bounds': QRectF(scene_pos.x(), scene_pos.y(), width, height)
                })
        
        if len(all_rectangles) < 2:
            return  # Need at least 2 rectangles to merge
        
        # Group vertically adjacent rectangles with similar properties
        merged_groups = []
        used_rects = set()
        
        for i, rect1 in enumerate(all_rectangles):
            if i in used_rects:
                continue
                
            group = [rect1]
            used_rects.add(i)
            
            for j, rect2 in enumerate(all_rectangles):
                if j in used_rects or i == j:
                    continue
                    
                if self._are_rectangles_mergeable(rect1, rect2):
                    group.append(rect2)
                    used_rects.add(j)
            
            if len(group) > 1:
                merged_groups.append(group)
        
        # Merge each group
        for group in merged_groups:
            self._merge_rectangle_group(group)

    def _are_rectangles_mergeable(self, rect1, rect2):
        """Check if two rectangles can be merged (were likely clipped from same original in regular mode)."""
        bounds1 = rect1['scene_bounds']
        bounds2 = rect2['scene_bounds']
        
        # Check if they're on adjacent pages (key for clipped items)
        if abs(rect1['page_idx'] - rect2['page_idx']) > 1:
            return False
        
        # Check if they're vertically adjacent
        tolerance = 10  # Stricter tolerance for rectangles
        adjacent = (abs(bounds1.bottom() - bounds2.top()) < tolerance or 
                   abs(bounds2.bottom() - bounds1.top()) < tolerance)
        
        if not adjacent:
            return False
            
        # Check horizontal alignment (clipped rectangles should have very similar X positions)
        x_tolerance = 5
        if abs(bounds1.left() - bounds2.left()) > x_tolerance:
            return False
            
        # Check width similarity (clipped rectangles should have similar widths)
        width_tolerance = 10
        if abs(bounds1.width() - bounds2.width()) > width_tolerance:
            return False
            
        # Check similar styling
        style_attrs = ['stroke', 'fill', 'opacity']
        for attr in style_attrs:
            if rect1['data'].get(attr) != rect2['data'].get(attr):
                return False
                
        return True

    def _merge_rectangle_group(self, group):
        """Merge a group of clipped rectangles back into one."""
        if len(group) <= 1:
            return
            
        # Calculate unified bounds
        all_bounds = [item['scene_bounds'] for item in group]
        unified_left = min(bounds.left() for bounds in all_bounds)
        unified_top = min(bounds.top() for bounds in all_bounds)
        unified_right = max(bounds.right() for bounds in all_bounds)
        unified_bottom = max(bounds.bottom() for bounds in all_bounds)
        
        # Determine target page (center of merged rectangle)
        center_y = (unified_top + unified_bottom) / 2
        target_page = self.layout_manager.get_page_at_position(center_y)
        
        # Convert to page-local coordinates
        scene_pos = QPointF(unified_left, unified_top)
        local_pos = self.coordinate_converter.scene_to_page_local_position(scene_pos, target_page)
        
        # Create merged rectangle data
        base_data = group[0]['data'].copy()
        base_data['rect'] = [
            local_pos.x(),
            local_pos.y(),
            unified_right - unified_left,
            unified_bottom - unified_top
        ]
        
        # Remove all rectangles from their current pages
        for item in group:
            page_idx = item['page_idx']
            file_path = self.image_loader.image_file_paths[page_idx]
            state = self.main_controller.image_states[file_path]
            rectangles = state['viewer_state']['rectangles']
            rectangles[:] = [r for r in rectangles if r != item['data']]
        
        # Add merged rectangle to target page
        target_file_path = self.image_loader.image_file_paths[target_page]
        target_state = self.main_controller.image_states[target_file_path]
        target_state['viewer_state']['rectangles'].append(base_data)
