"""
Webtoon Layout Manager

Handles layout calculations, positioning, and viewport management.
This class is the single source of truth for layout information.
"""

from typing import Set, Tuple
from PySide6.QtCore import QPointF, QRectF, QTimer


class WebtoonLayoutManager:
    """Manages layout and viewport calculations for webtoon mode."""
    
    def __init__(self, viewer):
        self.viewer = viewer
        self._scene = viewer._scene
        
        # Layout state (OWNER of this data)
        self.image_positions: list[float] = []
        self.image_heights: list[float] = []
        self.total_height: float = 0
        self.webtoon_width: float = 0
        self.image_spacing = 0
        self.placeholder_height = 1000
        
        # Viewport configuration
        self.viewport_buffer = 2  # Load N pages above/below viewport
        
        # Current page tracking
        self.current_page_index: int = 0
        self.page_detection_enabled = False
        
        # Page detection timer
        self.page_detection_timer = QTimer()
        self.page_detection_timer.setSingleShot(True)
        self.page_detection_timer.timeout.connect(self._enable_page_detection)
        
        # Callback for when page detection is enabled
        self.on_page_detection_enabled = None
        # References to other managers (will be set by LazyWebtoonManager)
        self.image_loader = None
        self.coordinate_converter = None
    
    def estimate_layout(self, file_paths: list[str]) -> bool:
        """Estimate layout dimensions without loading all images."""
        try:
            # Load just the first few images to estimate average dimensions
            sample_size = min(3, len(file_paths))
            sample_widths = []
            sample_heights = []
            
            for i in range(sample_size):
                # Quick metadata-only load for size estimation
                try:
                    import cv2
                    img = cv2.imread(file_paths[i])
                    if img is not None:
                        h, w = img.shape[:2]
                        sample_widths.append(w)
                        sample_heights.append(h)
                except:
                    # Fallback to default dimensions
                    sample_widths.append(1920)
                    sample_heights.append(2700)
            
            # Calculate averages
            avg_width = sum(sample_widths) // len(sample_widths) if sample_widths else 1920
            avg_height = sum(sample_heights) // len(sample_heights) if sample_heights else 2700
            
            self.webtoon_width = avg_width
            
            # Estimate positions for all pages
            current_y = 100
            self.image_positions.clear()
            self.image_heights.clear()
            
            for i in range(len(file_paths)):
                self.image_positions.append(current_y)
                # Use actual height if already loaded, otherwise estimate
                height = sample_heights[min(i, len(sample_heights) - 1)] if sample_heights else self.placeholder_height
                self.image_heights.append(height)
                current_y += height + self.image_spacing
                
            self.total_height = current_y - self.image_spacing
            self._scene.setSceneRect(0, 0, self.webtoon_width, self.total_height)
            
            return True
            
        except Exception as e:
            print(f"Error estimating layout: {e}")
            return False
    
    def adjust_layout_for_actual_size(self, page_idx: int, actual_height: int):
        """Adjust layout when actual image dimensions differ from estimates."""
        if not (0 <= page_idx < len(self.image_heights)):
            return
            
        old_height = self.image_heights[page_idx]
        height_diff = actual_height - old_height
        
        if height_diff != 0:
            # Update this page's height
            self.image_heights[page_idx] = actual_height
            
            # Shift all subsequent pages
            for i in range(page_idx + 1, len(self.image_positions)):
                self.image_positions[i] += height_diff
            
            # Update total height and scene rect
            self.total_height += height_diff
            self._scene.setSceneRect(0, 0, self.webtoon_width, self.total_height)
            
            return height_diff
        
        return 0
    
    def get_visible_pages(self) -> Set[int]:
        """Get pages currently visible in viewport + buffer."""
        # During initialization, estimate viewport around current page
        if hasattr(self.viewer, 'viewport') and self.viewer.viewport():
            viewport_rect = self.viewer.mapToScene(self.viewer.viewport().rect()).boundingRect()
            visible_top = viewport_rect.top() - (self.viewport_buffer * 1000)  # Buffer above
            visible_bottom = viewport_rect.bottom() + (self.viewport_buffer * 1000)  # Buffer below
        else:
            # Fallback during initialization - estimate around current page
            current_page_y = self.image_positions[self.current_page_index] if self.current_page_index < len(self.image_positions) else 0
            visible_top = current_page_y - (self.viewport_buffer * 1000)
            visible_bottom = current_page_y + (self.viewport_buffer * 1000)
        
        visible_pages = set()
        for i, (y_pos, height) in enumerate(zip(self.image_positions, self.image_heights)):
            page_bottom = y_pos + height
            if y_pos < visible_bottom and page_bottom > visible_top:
                visible_pages.add(i)
                
        return visible_pages
    
    def get_pages_for_scene_bounds(self, scene_rect: QRectF) -> Set[int]:
        """Get all pages that a scene rectangle intersects with."""
        pages = set()
        top = scene_rect.top()
        bottom = scene_rect.bottom()
        
        for i, (page_y, page_height) in enumerate(zip(self.image_positions, self.image_heights)):
            page_bottom = page_y + page_height
            
            # Check if rectangle intersects with this page
            if not (bottom < page_y or top > page_bottom):
                pages.add(i)
        
        return pages
    
    def get_page_at_position(self, y_pos: float) -> int:
        """Get the page index at a given Y position."""
        for i, (pos, height) in enumerate(zip(self.image_positions, self.image_heights)):
            if pos <= y_pos <= pos + height:
                return i
        return self.current_page_index
    
    def scroll_to_page(self, page_index: int, position: str = 'top'):
        """Scroll to a specific page."""
        if not (0 <= page_index < len(self.image_positions)):
            print(f"WebtoonLayoutManager: Invalid page index {page_index}, total pages: {len(self.image_positions)}")
            return False
            
        # Calculate target position
        page_y = self.image_positions[page_index]
        page_height = self.image_heights[page_index]
        
        target_y = page_y
        if position == 'center':
            target_y += page_height / 2
        elif position == 'bottom':
            target_y += page_height
            
        print(f"WebtoonLayoutManager: Scrolling to page {page_index}, position {position}")
        print(f"  Page Y: {page_y}, Height: {page_height}, Target Y: {target_y}")
        
        # Update current page index before scrolling
        old_page = self.current_page_index
        self.current_page_index = page_index
        
        # Scroll to position
        self.viewer.centerOn(self.webtoon_width / 2, target_y)
        
        # Check viewport after scroll
        viewport_center = self.viewer.mapToScene(self.viewer.viewport().rect().center())
        print(f"  After scroll: viewport center is at {viewport_center.x()}, {viewport_center.y()}")
        
        # Enable page detection after scrolling
        self.viewer.event_handler._enable_page_detection_after_delay()
        
        # Emit page change signal if page actually changed
        if old_page != page_index:
            self.viewer.page_changed.emit(page_index)
            
        return True
    
    def update_current_page(self, loaded_pages_count: int = 0) -> bool:
        """Update current page index based on viewport center. Returns True if page changed."""
        # Don't update during initial loading or if page detection is disabled
        if (loaded_pages_count < 3 or not self.page_detection_enabled):
            return False
            
        center_y = self.viewer.mapToScene(self.viewer.viewport().rect().center()).y()
        old_page = self.current_page_index
        
        # Only change page if viewport is significantly within another page
        # Use a two-pass approach: first try strict detection, then relaxed detection
        best_match_page = None
        best_match_distance = float('inf')
        
        for i, (pos, height) in enumerate(zip(self.image_positions, self.image_heights)):
            page_center = pos + height / 2
            page_top = pos
            page_bottom = pos + height
            
            # First pass: strict detection (10% margin)
            margin = height * 0.1
            page_detection_top = pos + margin
            page_detection_bottom = pos + height - margin
            
            if page_detection_top <= center_y <= page_detection_bottom:
                if i != self.current_page_index:
                    self.current_page_index = i
                    return True  # Page changed
                return False  # Same page
            
            # Second pass: find the closest page for fallback
            if page_top <= center_y <= page_bottom:
                # Viewport is within this page's bounds (no margin)
                distance_from_center = abs(center_y - page_center)
                if distance_from_center < best_match_distance:
                    best_match_distance = distance_from_center
                    best_match_page = i
        
        # If no page matched the strict criteria, use the closest page match
        if best_match_page is not None and best_match_page != self.current_page_index:
            self.current_page_index = best_match_page
            return True  # Page changed
            
        return False  # No change
    
    def update_page_on_click(self, scene_pos: QPointF) -> bool:
        """Check if a click occurred on a new page and update current page. Returns True if changed."""
        page = self.get_page_at_position(scene_pos.y())
        if page != self.current_page_index:
            self.current_page_index = page
            return True
        return False

    def ensure_current_page_visible(self, image_items: dict):
        """Ensure the current page is visible and view is properly set up."""
        print(f"WebtoonLayoutManager: ensure_current_page_visible: current_page_index = {self.current_page_index}")
        
        if self.current_page_index in image_items:
            self.viewer.fitInView()
            
            # Check viewport position
            viewport_center = self.viewer.mapToScene(self.viewer.viewport().rect().center()).y()
            current_page_center = self.image_positions[self.current_page_index] + (self.image_heights[self.current_page_index] / 2)
            
            print(f"Viewport center: {viewport_center}, Page center: {current_page_center}")
            
            # If viewport is far from current page, scroll to it
            distance = abs(viewport_center - current_page_center)
            threshold = self.image_heights[self.current_page_index] / 4
            print(f"Distance: {distance}, Threshold: {threshold}")
            
            if distance > threshold:
                self.scroll_to_page(self.current_page_index, 'center')
    
    def enable_page_detection_after_delay(self):
        """Enable page detection after a delay to let viewport settle."""
        self.page_detection_timer.start(1000)  # 1 second delay
    
    def _enable_page_detection(self):
        """Enable page detection after initialization is complete."""
        self.page_detection_enabled = True
        
        # Notify callback if set
        if self.on_page_detection_enabled:
            self.on_page_detection_enabled()
    
    def set_page_detection_delay(self, delay: int):
        """Set the page detection timer delay."""
        if delay > 0:
            self.page_detection_timer.setInterval(delay)
    
    def get_page_detection_delay(self) -> int:
        """Get the current page detection timer delay."""
        return self.page_detection_timer.interval() if hasattr(self.page_detection_timer, 'interval') else 1000
    
    def disable_page_detection(self):
        """Disable page detection."""
        self.page_detection_enabled = False
        self.page_detection_timer.stop()
    
    def scene_to_page_coordinates(self, scene_pos: QPointF) -> Tuple[int, QPointF]:
        """Convert scene coordinates to page-local coordinates."""
        page_index = self.get_page_at_position(scene_pos.y())
        if 0 <= page_index < len(self.image_positions):
            page_y = self.image_positions[page_index]
            # This would need image data to calculate page width - delegate to coordinate converter
            local_x = scene_pos.x()  # Simplified for now
            local_y = scene_pos.y() - page_y
            return page_index, QPointF(local_x, local_y)
        return page_index, scene_pos
    
    def page_to_scene_coordinates(self, page_index: int, local_pos: QPointF) -> QPointF:
        """Convert page-local coordinates to scene coordinates."""
        if not (0 <= page_index < len(self.image_positions)):
            return local_pos
        
        page_y = self.image_positions[page_index]
        # This would need image data to calculate page width - delegate to coordinate converter
        scene_x = local_pos.x()  # Simplified for now
        scene_y = local_pos.y() + page_y
        return QPointF(scene_x, scene_y)
    
    def clear(self):
        """Clear all layout state."""
        self.page_detection_timer.stop()
        self.page_detection_enabled = False
        self.current_page_index = 0
        self.total_height = 0
        self.webtoon_width = 0
        self.image_positions.clear()
        self.image_heights.clear()

    def _recalculate_layout(self):
        """Recalculate layout positions after page addition/removal."""
        if not self.image_loader.image_file_paths:
            self.total_height = 0
            self.image_positions.clear()
            self.image_heights.clear()
            self._scene.setSceneRect(0, 0, 0, 0)
            return
        
        # Recalculate positions from scratch
        current_y = 100
        new_positions = []
        
        for i in range(len(self.image_loader.image_file_paths)):
            new_positions.append(current_y)
            # Use existing height if available, otherwise estimate
            height = self.image_heights[i] if i < len(self.image_heights) else 1000
            current_y += height + self.image_spacing
        
        # Update layout manager with new positions
        self.image_positions = new_positions
        
        # Update total height
        self.total_height = current_y - self.image_spacing if new_positions else 0
        
        # Update scene rectangle to new dimensions
        scene_rect = QRectF(0, 0, self.webtoon_width, self.total_height)
        self._scene.setSceneRect(scene_rect)
        
        # Also update the viewer's scene rect to ensure scrollbars are updated
        self.viewer.setSceneRect(scene_rect)
        
        # Update image item positions for loaded pages
        for page_idx in list(self.image_loader.loaded_pages):
            if page_idx < len(self.image_positions) and page_idx in self.image_loader.image_items:
                item = self.image_loader.image_items[page_idx]
                y_pos = self.image_positions[page_idx]
                # Calculate x position (centered)
                if page_idx in self.image_loader.image_data:
                    img_width = self.image_loader.image_data[page_idx].shape[1]
                    x_offset = (self.webtoon_width - img_width) / 2
                else:
                    x_offset = item.pos().x()  # Keep existing x position
                item.setPos(x_offset, y_pos)
        
        # Update placeholder positions if any exist
        for page_idx in list(self.image_loader.placeholder_items.keys()):
            if page_idx < len(self.image_positions):
                placeholder = self.image_loader.placeholder_items[page_idx]
                y_pos = self.image_positions[page_idx]
                placeholder.setPos(0, y_pos)
