"""
Brush Stroke Manager for Webtoon Scene Items

Handles brush stroke management with state storage for webtoon mode.
"""

from typing import List, Dict, Set, Optional, Tuple
from PySide6.QtWidgets import QGraphicsPathItem
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath, Qt


class BrushStrokeManager:
    """Manages brush strokes for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter, image_loader):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self.image_loader = image_loader
        self._scene = viewer._scene
        
        # Main controller reference (set by scene item manager)
        self.main_controller = None
    
    def initialize(self):
        """Initialize or reset the brush stroke manager state."""
        pass
    
    def load_brush_strokes(self, state: Dict, page_idx: int):
        """Load brush strokes for a specific page."""
        brush_strokes = state.get('brush_strokes', [])
        if brush_strokes and hasattr(self.viewer, 'drawing_manager'):
            # Convert brush strokes from page-local to scene coordinates
            for stroke_data in brush_strokes:
                # Convert the path from page-local to scene coordinates
                scene_path = self.coordinate_converter.convert_path_to_scene_coordinates(stroke_data['path'], page_idx)
                
                pen = QPen()
                pen.setColor(QColor(stroke_data['pen']))
                pen.setWidth(stroke_data['width'])
                pen.setStyle(Qt.SolidLine)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                
                brush = QBrush(QColor(stroke_data['brush']))
                if brush.color() == QColor("#80ff0000"):
                    self._scene.addPath(scene_path, pen, brush)
                else:
                    self._scene.addPath(scene_path, pen)
    
    def unload_brush_strokes(self, page_idx: int, page_y: float, page_bottom: float, file_path: str):
        """Unload brush strokes for a specific page."""
        brush_strokes_to_remove = []
        brush_strokes_data = []
        
        for item in self._scene.items():
            if (isinstance(item, QGraphicsPathItem) and 
                item != self.viewer.photo):
                
                # Check if this brush stroke intersects with this page
                item_bounds = item.boundingRect()
                item_scene_bounds = item.mapRectToScene(item_bounds)
                item_top = item_scene_bounds.top()
                item_bottom = item_scene_bounds.bottom()
                
                # If brush stroke intersects with this page, save it
                if not (item_bottom < page_y or item_top > page_bottom):
                    # Convert stroke to page-local coordinates
                    page_local_stroke = self.coordinate_converter.convert_stroke_to_page_local(item, page_idx)
                    if page_local_stroke:
                        brush_strokes_data.append(page_local_stroke)
                        brush_strokes_to_remove.append(item)
        
        # Store brush strokes in image_states
        self.main_controller.image_states[file_path]['brush_strokes'] = brush_strokes_data
        
        # Remove brush stroke items from scene
        for stroke_item in brush_strokes_to_remove:
            self._scene.removeItem(stroke_item)
    
    def save_brush_strokes_to_states(self, scene_items_by_page: Dict):
        """Save brush strokes to appropriate page states."""
        for item in self._scene.items():
            if (isinstance(item, QGraphicsPathItem) and 
                item != self.viewer.photo):
                
                # Process this brush stroke using coordinate converter
                stroke_data = {
                    'path': item.path(),
                    'pen': item.pen().color().name(QColor.HexArgb) if hasattr(item, 'pen') else '#80ff0000',
                    'brush': item.brush().color().name(QColor.HexArgb) if hasattr(item, 'brush') else '#00000000',
                    'width': item.pen().width() if hasattr(item, 'pen') else 25
                }
                
                # Find all pages this stroke intersects with and create clipped versions
                self._process_single_brush_stroke(stroke_data, scene_items_by_page)
    
    def _process_single_brush_stroke(self, stroke: Dict, scene_items_by_page: Dict) -> Set[int]:
        """Process a single brush stroke and distribute it to pages."""
        path = stroke['path']
        pen_color = stroke['pen']
        brush_color = stroke['brush']
        width = stroke['width']
        
        # Get all points in the path to determine which pages this stroke touches
        pages_touched = set()
        path_elements = []
        
        # Iterate through path elements to collect all points
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            point = QPointF(element.x, element.y)
            path_elements.append((element.type, point))
            
            # Check which page this point belongs to
            page_index = self.layout_manager.get_page_at_position(point.y())
            if 0 <= page_index < len(self.image_loader.image_file_paths):
                pages_touched.add(page_index)
        
        # Create page-specific paths for each touched page
        for page_index in pages_touched:
            # Create a new path for this page with converted coordinates
            page_path = self._create_page_path(path_elements, page_index)
            
            # Only add the stroke if it has valid elements on this page
            if page_path and not page_path.isEmpty():
                page_stroke = {
                    'path': page_path,
                    'pen': pen_color,
                    'brush': brush_color,
                    'width': width
                }
                scene_items_by_page[page_index]['brush_strokes'].append(page_stroke)
        
        return pages_touched
    
    def _create_page_path(self, path_elements: List, target_page_index: int) -> Optional[QPainterPath]:
        """Create a page-specific path from scene path elements."""
        page_path = QPainterPath()
        has_valid_elements = False
        current_subpath_started = False
        
        # Get page bounds for clipping
        if not (0 <= target_page_index < len(self.layout_manager.image_positions)):
            return None
            
        page_y = self.layout_manager.image_positions[target_page_index]
        page_height = self.layout_manager.image_heights[target_page_index]
        
        # Calculate page x bounds
        page_width = self.layout_manager.webtoon_width
        if hasattr(self.coordinate_converter, 'image_data') and target_page_index in self.coordinate_converter.image_data:
            page_width = self.coordinate_converter.image_data[target_page_index].shape[1]
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        page_bounds = QRectF(page_x_offset, page_y, page_width, page_height)
        
        for i, (element_type, scene_point) in enumerate(path_elements):
            # Check if point is within this page's bounds
            point_on_page = (page_bounds.left() <= scene_point.x() <= page_bounds.right() and
                           page_bounds.top() <= scene_point.y() <= page_bounds.bottom())
            
            if point_on_page:
                # Convert to page-local coordinates
                local_point = self.coordinate_converter.scene_to_page_local_position(scene_point, target_page_index)
                has_valid_elements = True
                
                if element_type == QPainterPath.ElementType.MoveToElement or not current_subpath_started:
                    page_path.moveTo(local_point)
                    current_subpath_started = True
                else:
                    page_path.lineTo(local_point)
                    
            elif current_subpath_started:
                # Point is outside this page, but we were drawing on this page
                # We need to clip the line to the page boundary
                if i > 0:
                    prev_element_type, prev_scene_point = path_elements[i-1]
                    prev_on_page = (page_bounds.left() <= prev_scene_point.x() <= page_bounds.right() and
                                  page_bounds.top() <= prev_scene_point.y() <= page_bounds.bottom())
                    
                    if prev_on_page:
                        # Previous point was on this page, current point is not
                        # Find intersection with page boundary and add it
                        intersection_point = self.coordinate_converter.find_page_boundary_intersection(
                            prev_scene_point, scene_point, page_bounds, target_page_index)
                        if intersection_point:
                            page_path.lineTo(intersection_point)
                
                # End this subpath since we've left the page
                current_subpath_started = False
                
            elif i > 0:
                # Current point is outside, but check if we're entering the page
                prev_element_type, prev_scene_point = path_elements[i-1]
                prev_on_page = (page_bounds.left() <= prev_scene_point.x() <= page_bounds.right() and
                              page_bounds.top() <= prev_scene_point.y() <= page_bounds.bottom())
                
                if not prev_on_page:
                    # Both points are outside this page, but line might cross it
                    # Find intersection with page boundary for entry point
                    intersection_point = self.coordinate_converter.find_page_boundary_intersection(
                        prev_scene_point, scene_point, page_bounds, target_page_index)
                    if intersection_point:
                        page_path.moveTo(intersection_point)
                        current_subpath_started = True
                        has_valid_elements = True
        
        return page_path if has_valid_elements else None
    
    def clear(self):
        """Clear all brush stroke management state."""
        pass

    def redistribute_existing_brush_strokes(self, all_existing_brush_strokes: List[tuple], scene_items_by_page: Dict):
        """Redistribute existing brush strokes to all pages they intersect with after clipping."""
        processed_strokes = set()  # Track processed strokes to avoid duplicates
        
        for stroke_data, original_page_idx in all_existing_brush_strokes:
            # Create a unique identifier for this stroke to avoid duplicates
            stroke_id = id(stroke_data)
            if stroke_id in processed_strokes:
                continue
            processed_strokes.add(stroke_id)
            
            if 'path' not in stroke_data:
                # Keep invalid stroke on its original page
                scene_items_by_page[original_page_idx]['brush_strokes'].append(stroke_data)
                continue
                
            try:
                path = stroke_data['path']
                if not hasattr(path, 'boundingRect'):
                    # Keep stroke without valid path on its original page
                    scene_items_by_page[original_page_idx]['brush_strokes'].append(stroke_data)
                    continue
                
                # Convert path from page-local to scene coordinates
                scene_path = QPainterPath()
                for i in range(path.elementCount()):
                    element = path.elementAt(i)
                    local_point = QPointF(element.x, element.y)
                    scene_point = self.coordinate_converter.page_local_to_scene_position(local_point, original_page_idx)

                    if element.type == QPainterPath.ElementType.MoveToElement:
                        scene_path.moveTo(scene_point)
                    elif element.type == QPainterPath.ElementType.LineToElement:
                        scene_path.lineTo(scene_point)
                    # Handle other element types as needed
                
                # Create stroke data with scene coordinates
                scene_stroke_data = stroke_data.copy()
                scene_stroke_data['path'] = scene_path
                
                # Use brush stroke manager logic to process and distribute to all pages
                self._process_single_brush_stroke(scene_stroke_data, scene_items_by_page)
                
            except Exception:
                # Keep stroke on original page if processing fails
                scene_items_by_page[original_page_idx]['brush_strokes'].append(stroke_data)

    def is_duplicate_brush_stroke(self, new_stroke, existing_strokes, margin=5):
        """Check if a brush stroke is a duplicate of any existing stroke within margin."""
        if 'path' not in new_stroke:
            return False
            
        new_path = new_stroke['path']
        if not hasattr(new_path, 'boundingRect'):
            return False
            
        new_bounds = new_path.boundingRect()
        
        for existing_stroke in existing_strokes:
            if 'path' not in existing_stroke:
                continue
                
            ex_path = existing_stroke['path']
            if not hasattr(ex_path, 'boundingRect'):
                continue
                
            ex_bounds = ex_path.boundingRect()
            
            # Check if bounding rectangles are within margin
            if (abs(new_bounds.x() - ex_bounds.x()) <= margin and 
                abs(new_bounds.y() - ex_bounds.y()) <= margin and 
                abs(new_bounds.width() - ex_bounds.width()) <= margin and 
                abs(new_bounds.height() - ex_bounds.height()) <= margin):
                return True
        return False
