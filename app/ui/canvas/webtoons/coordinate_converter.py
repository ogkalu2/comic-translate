"""
Coordinate Converter for Webtoon Manager

Handles coordinate transformations between page-local and scene coordinates.
This class is stateless and relies on live data from other managers.
"""

from typing import Optional
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath


class CoordinateConverter:
    """Handles coordinate transformations for webtoon mode."""
    
    def __init__(self, layout_manager, image_loader):
        """
        Initializes the converter with references to the data owners.
        This class does not own any state itself.
        """
        self.layout_manager = layout_manager
        self.image_loader = image_loader
    
    def page_local_to_scene_position(self, page_local_pos: QPointF, page_idx: int) -> QPointF:
        """Convert page-local coordinates to scene coordinates."""
        if not (0 <= page_idx < len(self.layout_manager.image_positions)):
            return page_local_pos
            
        # Get page offset from LayoutManager
        page_y = self.layout_manager.image_positions[page_idx]
        
        # Calculate page x offset (items are centered in webtoon mode)
        image_data = self.image_loader.image_data
        if page_idx in image_data:
            page_width = image_data[page_idx].shape[1]
        else:
            page_width = self.layout_manager.webtoon_width
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        # Convert to scene coordinates
        scene_x = page_local_pos.x() + page_x_offset
        scene_y = page_local_pos.y() + page_y
        
        return QPointF(scene_x, scene_y)
    
    def scene_to_page_local_position(self, scene_pos: QPointF, page_idx: int) -> QPointF:
        """Convert scene coordinates to page-local coordinates."""
        if not (0 <= page_idx < len(self.layout_manager.image_positions)):
            return scene_pos
            
        # Get page offset from LayoutManager
        page_y = self.layout_manager.image_positions[page_idx]
        
        # Calculate page x offset (items are centered in webtoon mode)
        image_data = self.image_loader.image_data
        if page_idx in image_data:
            page_width = image_data[page_idx].shape[1]
        else:
            page_width = self.layout_manager.webtoon_width
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        # Convert to page-local coordinates
        local_x = scene_pos.x() - page_x_offset
        local_y = scene_pos.y() - page_y
        
        return QPointF(local_x, local_y)
    
    def convert_path_to_scene_coordinates(self, page_local_path: QPainterPath, page_idx: int) -> QPainterPath:
        """Convert a page-local brush path to scene coordinates."""
        if not (0 <= page_idx < len(self.layout_manager.image_positions)):
            return page_local_path
            
        # Create a new path in scene coordinates
        scene_path = QPainterPath()
        
        # Convert each element of the path
        for i in range(page_local_path.elementCount()):
            element = page_local_path.elementAt(i)
            page_local_point = QPointF(element.x, element.y)
            scene_point = self.page_local_to_scene_position(page_local_point, page_idx)
            
            if element.type == QPainterPath.ElementType.MoveToElement:
                scene_path.moveTo(scene_point)
            elif element.type == QPainterPath.ElementType.LineToElement:
                scene_path.lineTo(scene_point)
            elif element.type == QPainterPath.ElementType.CurveToElement:
                # Handle curve elements
                if i + 2 < page_local_path.elementCount():
                    c1 = page_local_path.elementAt(i + 1)
                    c2 = page_local_path.elementAt(i + 2)
                    c1_scene = self.page_local_to_scene_position(QPointF(c1.x, c1.y), page_idx)
                    c2_scene = self.page_local_to_scene_position(QPointF(c2.x, c2.y), page_idx)
                    scene_path.cubicTo(scene_point, c1_scene, c2_scene)
        
        return scene_path
    
    def convert_stroke_to_page_local(self, stroke_item, page_idx: int) -> Optional[dict]:
        """Convert a brush stroke to page-local coordinates and clip to page bounds."""
        if not (0 <= page_idx < len(self.layout_manager.image_positions)):
            return None
            
        # Get page bounds from LayoutManager
        page_y = self.layout_manager.image_positions[page_idx]
        page_height = self.layout_manager.image_heights[page_idx]
        page_bottom = page_y + page_height
        
        # Calculate page x offset
        image_data = self.image_loader.image_data
        if page_idx in image_data:
            page_width = image_data[page_idx].shape[1]
        else:
            page_width = self.layout_manager.webtoon_width
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        # Create a clipping rectangle for this page in scene coordinates
        page_rect = QRectF(page_x_offset, page_y, page_width, page_height)
        
        # Get the original path
        original_path = stroke_item.path()
        
        # Create a new path translated to page-local coordinates
        local_path = QPainterPath()
        
        # Translate each element of the path
        for i in range(original_path.elementCount()):
            element = original_path.elementAt(i)
            scene_point = QPointF(element.x, element.y)
            
            # Only include points that are within or near this page
            if (scene_point.y() >= page_y - 50 and scene_point.y() <= page_bottom + 50):
                # Convert to page-local coordinates
                local_point = self.scene_to_page_local_position(scene_point, page_idx)
                
                if element.type == QPainterPath.ElementType.MoveToElement:
                    local_path.moveTo(local_point)
                elif element.type == QPainterPath.ElementType.LineToElement:
                    local_path.lineTo(local_point)
                elif element.type == QPainterPath.ElementType.CurveToElement:
                    # Handle curve elements
                    if i + 2 < original_path.elementCount():
                        c1 = original_path.elementAt(i + 1)
                        c2 = original_path.elementAt(i + 2)
                        c1_local = self.scene_to_page_local_position(QPointF(c1.x, c1.y), page_idx)
                        c2_local = self.scene_to_page_local_position(QPointF(c2.x, c2.y), page_idx)
                        local_path.cubicTo(local_point, c1_local, c2_local)
        
        # Only return the stroke if it has meaningful content for this page
        if not local_path.isEmpty():
            return {
                'path': local_path,
                'pen': stroke_item.pen().color().name() if hasattr(stroke_item, 'pen') else '#80ff0000',
                'brush': stroke_item.brush().color().name() if hasattr(stroke_item, 'brush') else '#00000000',
                'width': stroke_item.pen().width() if hasattr(stroke_item, 'pen') else 25
            }
        
        return None
    
    def clip_rectangle_to_page(self, rect_item, page_index: int) -> Optional[tuple]:
        """Clip a rectangle to page bounds and return page-local coordinates"""
        if not (0 <= page_index < len(self.layout_manager.image_positions)):
            return None
            
        # Get page bounds in scene coordinates from LayoutManager
        page_y = self.layout_manager.image_positions[page_index]
        page_height = self.layout_manager.image_heights[page_index]
        
        # Calculate page x offset
        image_data = self.image_loader.image_data
        if page_index in image_data:
            page_width = image_data[page_index].shape[1]
        else:
            page_width = self.layout_manager.webtoon_width
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        # Page bounds in scene coordinates
        page_rect = QRectF(page_x_offset, page_y, page_width, page_height)
        
        # Rectangle bounds in scene coordinates
        rect_x = rect_item.pos().x()
        rect_y = rect_item.pos().y()
        rect_width = rect_item.boundingRect().width()
        rect_height = rect_item.boundingRect().height()
        rect_right = rect_x + rect_width
        rect_bottom = rect_y + rect_height
        
        # Calculate intersection
        clipped_left = max(rect_x, page_rect.left())
        clipped_top = max(rect_y, page_rect.top())
        clipped_right = min(rect_right, page_rect.right())
        clipped_bottom = min(rect_bottom, page_rect.bottom())
        
        # Check if there's actual overlap
        if clipped_left >= clipped_right or clipped_top >= clipped_bottom:
            return None
            
        # Convert to page-local coordinates
        local_x = clipped_left - page_x_offset
        local_y = clipped_top - page_y
        local_width = clipped_right - clipped_left
        local_height = clipped_bottom - clipped_top
        
        return (local_x, local_y, local_width, local_height)
    
    def clip_textblock_to_page(self, text_block, page_index: int) -> Optional[tuple]:
        """Clip a text block to page bounds and return page-local coordinates"""
        if not (0 <= page_index < len(self.layout_manager.image_positions)):
            return None
            
        # Get page bounds in scene coordinates from LayoutManager
        page_y = self.layout_manager.image_positions[page_index]
        page_height = self.layout_manager.image_heights[page_index]
        
        # Calculate page x offset
        image_data = self.image_loader.image_data
        if page_index in image_data:
            page_width = image_data[page_index].shape[1]
        else:
            page_width = self.layout_manager.webtoon_width
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        # Page bounds in scene coordinates
        page_rect = QRectF(page_x_offset, page_y, page_width, page_height)
        
        # TextBlock bounds in scene coordinates (using xyxy format)
        if text_block.xyxy is None or len(text_block.xyxy) < 4:
            return None
            
        rect_x = text_block.xyxy[0]
        rect_y = text_block.xyxy[1]
        rect_right = text_block.xyxy[2]
        rect_bottom = text_block.xyxy[3]
        rect_width = rect_right - rect_x
        rect_height = rect_bottom - rect_y
        
        # Calculate intersection
        clipped_left = max(rect_x, page_rect.left())
        clipped_top = max(rect_y, page_rect.top())
        clipped_right = min(rect_right, page_rect.right())
        clipped_bottom = min(rect_bottom, page_rect.bottom())
        
        # Check if there's actual overlap
        if clipped_left >= clipped_right or clipped_top >= clipped_bottom:
            return None
            
        # Convert to page-local coordinates
        local_x = clipped_left - page_x_offset
        local_y = clipped_top - page_y
        local_width = clipped_right - clipped_left
        local_height = clipped_bottom - clipped_top
        
        return (local_x, local_y, local_x + local_width, local_y + local_height)  # Return as xyxy format
    
    def clip_text_item_to_page(self, text_item, page_index: int) -> Optional[dict]:
        """
        Clip a text item to page bounds and return clipped text data.
        For text items that span multiple pages, this handles text splitting.
        """
        if not (0 <= page_index < len(self.layout_manager.image_positions)):
            return None
            
        # Get page bounds in scene coordinates from LayoutManager
        page_y = self.layout_manager.image_positions[page_index]
        page_height = self.layout_manager.image_heights[page_index]
        
        # Calculate page x offset
        image_data = self.image_loader.image_data
        if page_index in image_data:
            page_width = image_data[page_index].shape[1]
        else:
            page_width = self.layout_manager.webtoon_width
        page_x_offset = (self.layout_manager.webtoon_width - page_width) / 2
        
        # Page bounds in scene coordinates
        page_rect = QRectF(page_x_offset, page_y, page_width, page_height)
        
        # Text item bounds in scene coordinates
        text_x = text_item.pos().x()
        text_y = text_item.pos().y()
        text_width = text_item.boundingRect().width()
        text_height = text_item.boundingRect().height()
        text_right = text_x + text_width
        text_bottom = text_y + text_height
        
        # Calculate intersection
        clipped_left = max(text_x, page_rect.left())
        clipped_top = max(text_y, page_rect.top())
        clipped_right = min(text_right, page_rect.right())
        clipped_bottom = min(text_bottom, page_rect.bottom())
        
        # Check if there's actual overlap
        if clipped_left >= clipped_right or clipped_top >= clipped_bottom:
            return None
            
        # Calculate clipping ratios to determine which portion of text to include
        top_clip_ratio = max(0, (clipped_top - text_y) / text_height) if text_height > 0 else 0
        bottom_clip_ratio = min(1, (clipped_bottom - text_y) / text_height) if text_height > 0 else 1
        left_clip_ratio = max(0, (clipped_left - text_x) / text_width) if text_width > 0 else 0
        right_clip_ratio = min(1, (clipped_right - text_x) / text_width) if text_width > 0 else 1
        
        # Convert clipped position to page-local coordinates
        local_x = clipped_left - page_x_offset
        local_y = clipped_top - page_y
        
        return {
            'clipped_bounds': (local_x, local_y, clipped_right - clipped_left, clipped_bottom - clipped_top),
            'clip_ratios': {
                'top': top_clip_ratio,
                'bottom': bottom_clip_ratio,
                'left': left_clip_ratio,
                'right': right_clip_ratio
            },
            'original_size': (text_width, text_height),
            'page_bounds': (page_width, page_height)
        }
    
    def find_page_boundary_intersection(self, point1: QPointF, point2: QPointF, 
                                      page_bounds: QRectF, target_page_index: int) -> Optional[QPointF]:
        """Find where a line segment intersects with page boundaries."""
        x1, y1 = point1.x(), point1.y()
        x2, y2 = point2.x(), point2.y()
        
        # Page boundaries in scene coordinates
        left = page_bounds.left()
        right = page_bounds.right()
        top = page_bounds.top()
        bottom = page_bounds.bottom()
        
        # Check intersections with each edge
        intersections = []
        
        # Left edge
        if x1 != x2:  # Avoid division by zero
            t = (left - x1) / (x2 - x1)
            if 0 <= t <= 1:
                y = y1 + t * (y2 - y1)
                if top <= y <= bottom:
                    scene_point = QPointF(left, y)
                    local_point = self.scene_to_page_local_position(scene_point, target_page_index)
                    intersections.append(local_point)
        
        # Right edge
        if x1 != x2:
            t = (right - x1) / (x2 - x1)
            if 0 <= t <= 1:
                y = y1 + t * (y2 - y1)
                if top <= y <= bottom:
                    scene_point = QPointF(right, y)
                    local_point = self.scene_to_page_local_position(scene_point, target_page_index)
                    intersections.append(local_point)
        
        # Top edge
        if y1 != y2:  # Avoid division by zero
            t = (top - y1) / (y2 - y1)
            if 0 <= t <= 1:
                x = x1 + t * (x2 - x1)
                if left <= x <= right:
                    scene_point = QPointF(x, top)
                    local_point = self.scene_to_page_local_position(scene_point, target_page_index)
                    intersections.append(local_point)
        
        # Bottom edge
        if y1 != y2:
            t = (bottom - y1) / (y2 - y1)
            if 0 <= t <= 1:
                x = x1 + t * (x2 - x1)
                if left <= x <= right:
                    scene_point = QPointF(x, bottom)
                    local_point = self.scene_to_page_local_position(scene_point, target_page_index)
                    intersections.append(local_point)
        
        # Return the first intersection point (could be improved to choose the best one)
        return intersections[0] if intersections else None
