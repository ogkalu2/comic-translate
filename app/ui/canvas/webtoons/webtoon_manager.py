"""
Lazy Loading Webtoon Manager

main coordinator that delegates to specialized components:
- LazyImageLoader: Memory-efficient image loading and unloading
- WebtoonLayoutManager: Layout calculations, positioning, and viewport management  
- SceneItemManager: Scene items (rectangles, text, brush strokes) management
- CoordinateConverter: Coordinate transformations between page-local and scene coordinates
"""

from __future__ import annotations

import numpy as np
import cv2
from typing import List, Dict, Set, TYPE_CHECKING
from PySide6.QtCore import QTimer, QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QTransform

from .image_loader import LazyImageLoader
from .webtoon_layout_manager import WebtoonLayoutManager
from .scene_items.scene_item_manager import SceneItemManager
from .coordinate_converter import CoordinateConverter


if TYPE_CHECKING:
    from app.ui.canvas.image_viewer import ImageViewer


class LazyWebtoonManager:
    """Memory-efficient webtoon manager with lazy loading - refactored with component delegation."""

    def __init__(self, viewer: ImageViewer):
        self.viewer = viewer
        self._scene = viewer._scene
        
        # Initialize specialized components
        self.layout_manager = WebtoonLayoutManager(viewer)
        self.coordinate_converter = CoordinateConverter()
        self.image_loader = LazyImageLoader(viewer, self.layout_manager)
        self.scene_item_manager = SceneItemManager(viewer, self.layout_manager, self.coordinate_converter)
        
        # Set up callback for when page detection is enabled
        self.layout_manager.on_page_detection_enabled = self._on_page_detection_enabled
        
        # Set up reference to self in image loader for callbacks
        self.image_loader.webtoon_manager = self
        
        # Connect components
        self.image_loader.main_controller = None  # Will be set by enhanced controller
        self.scene_item_manager.main_controller = None  # Will be set by enhanced controller
        
        # Scroll handling for lazy loading
        self.scroll_timer = QTimer()
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self._update_loaded_pages)
        
        # Main controller reference (set by enhanced webtoon controller)
        self.main_controller = None

    def load_images_lazy(self, file_paths: List[str], current_page: int = 0) -> bool:
        """Initialize webtoon mode with lazy loading."""
        try:
            self.main_controller.blk_list.clear()
            self.viewer.clear_scene()
            
            if not file_paths:
                self.viewer.empty = True
                return True
                
            self.viewer.empty = False
            
            # Set current page before any loading operations
            current_page = max(0, min(current_page, len(file_paths) - 1))
            self.layout_manager.current_page_index = current_page
            
            # Initialize all components
            if not self.layout_manager.estimate_layout(file_paths):
                return False
                
            # Update coordinate converter with layout information
            self.coordinate_converter.update_layout(
                self.layout_manager.image_positions,
                self.layout_manager.image_heights,
                self.layout_manager.webtoon_width,
                {}  # Image data will be updated as images load
            )
            
            # Initialize image loader and scene item manager
            self.image_loader.initialize_images(file_paths, current_page)
            self.scene_item_manager.initialize(file_paths)
            
            # Set up the view properly for webtoon mode
            # Don't call fitInView() yet if we need to center on a different page
            if self.layout_manager.current_page_index == 0:
                self.viewer.fitInView()
            
            # Center the view on the current page if it's not page 0
            if self.layout_manager.current_page_index > 0:
                # Center on the current page initially
                page_center_y = self.layout_manager.image_positions[self.layout_manager.current_page_index] + (self.layout_manager.image_heights[self.layout_manager.current_page_index] / 2)
                
                # Set the scene rect first to ensure proper coordinate space
                self.viewer.setSceneRect(0, 0, self.layout_manager.webtoon_width, self.layout_manager.total_height)
                
                # Use ensureVisible instead of centerOn for more reliable positioning
                page_rect = QRectF(0, self.layout_manager.image_positions[self.layout_manager.current_page_index], 
                                self.layout_manager.webtoon_width, self.layout_manager.image_heights[self.layout_manager.current_page_index])
                self.viewer.ensureVisible(page_rect, 50, 50)  # 50px margins
                
                # Verify the centering worked
                actual_center = self.viewer.mapToScene(self.viewer.viewport().rect().center())
                print(f"After centering: Actual viewport center: {actual_center.x()}, {actual_center.y()}")
                
                # If still not positioned correctly, try a more direct approach
                if abs(actual_center.y() - page_center_y) > 500:  # If more than 500px off
                    print("EnsureVisible failed, trying direct scroll")
                    # Calculate the scroll position needed
                    viewport_height = self.viewer.viewport().height()
                    target_scroll_y = page_center_y - (viewport_height / 2)
                    target_scroll_y = max(0, min(target_scroll_y, self.layout_manager.total_height - viewport_height))
                    
                    # Set the scroll position directly
                    v_scrollbar = self.viewer.verticalScrollBar()
                    max_scroll = v_scrollbar.maximum()
                    if max_scroll > 0:
                        scroll_ratio = target_scroll_y / (self.layout_manager.total_height - viewport_height)
                        scroll_value = int(scroll_ratio * max_scroll)
                        v_scrollbar.setValue(scroll_value)
                        print(f"Set scroll value to {scroll_value} (max: {max_scroll})")
            else:
                self.viewer.fitInView()
            
            # Enable page detection after a delay to let viewport settle
            self.layout_manager.enable_page_detection_after_delay()
            
            return True
            
        except Exception as e:
            print(f"Error in lazy webtoon loading: {e}")
            self.main_controller.blk_list.clear()
            self.viewer.clear_scene()
            return False

    def on_scroll(self):
        """Handle scroll events to trigger lazy loading."""
        # Debounce scroll events - increased delay for better stroke handling
        self.scroll_timer.start(200)  # 200ms delay

    def _update_loaded_pages(self):
        """Update which pages should be loaded based on current viewport."""
        # Delegate to image loader
        self.image_loader.update_loaded_pages()
        
        # Update current page if we have loaded some pages
        if self.image_loader.get_loaded_pages_count() > 2:
            # Check if page changed and emit signal if it did
            page_changed = self.layout_manager.update_current_page(self.image_loader.get_loaded_pages_count())
            if page_changed:
                self.viewer.page_changed.emit(self.layout_manager.current_page_index)

    # Public API methods 
    def is_active(self) -> bool:
        """Check if webtoon mode is active."""
        return len(self.layout_manager.image_positions) > 0
        
    def scroll_to_page(self, page_index: int, position: str = 'top'):
        """Scroll to a specific page, loading it if necessary."""
        # Queue the target page for immediate loading
        self.image_loader.queue_page_for_loading(page_index)
        
        # Delegate to layout manager
        success = self.layout_manager.scroll_to_page(page_index, position)
        
        if success:
            # Trigger loading update
            self._update_loaded_pages()
        
        return success

    def update_page_on_click(self, scene_pos: QPointF):
        """Check if a click occurred on a new page and update current page."""
        if self.layout_manager.update_page_on_click(scene_pos):
            # Page changed, emit signal
            self.viewer.page_changed.emit(self.layout_manager.current_page_index)

    def clear(self):
        """Clear all webtoon state."""
        # Stop timers
        self.scroll_timer.stop()
        
        # Clear all components
        self.layout_manager.clear()
        self.image_loader.clear()
        self.scene_item_manager.clear()
        
        # Reset coordinate converter
        self.coordinate_converter.update_layout([], [], 0, {})

    # Component access for enhanced controller
    def set_main_controller(self, controller):
        """Set the main controller reference for all components."""
        self.main_controller = controller
        self.image_loader.main_controller = controller
        self.scene_item_manager.main_controller = controller

    def save_view_state(self) -> dict:
        """Save the current viewer state for persistence."""
        transform = self.viewer.transform()
        center = self.viewer.mapToScene(self.viewer.viewport().rect().center())

        state = {
            'transform': (transform.m11(), transform.m12(), transform.m13(),
                          transform.m21(), transform.m22(), transform.m23(),
                          transform.m31(), transform.m32(), transform.m33()),
            'center': (center.x(), center.y()),
            'scene_rect': (self.viewer.sceneRect().x(), self.viewer.sceneRect().y(), 
                           self.viewer.sceneRect().width(), self.viewer.sceneRect().height()),
        }
        self.viewer.webtoon_view_state = state
        return state
    
    def restore_view_state(self):
        """Restore the viewer state from a saved state."""
        state = self.viewer.webtoon_view_state
        if not state:
            return
        
        self.viewer.setTransform(QTransform(*state['transform']))
        # self.viewer.centerOn(QPointF(*state['center']))
        # self.viewer.setSceneRect(QRectF(*state['scene_rect']))

    # Layout management proxies
    @property
    def image_positions(self) -> List[float]:
        """Get image positions."""
        return self.layout_manager.image_positions
    
    @property
    def image_heights(self) -> List[float]:
        """Get image heights."""
        return self.layout_manager.image_heights
    
    @property
    def total_height(self) -> float:
        """Get total height."""
        return self.layout_manager.total_height
    
    @property
    def webtoon_width(self) -> float:
        """Get webtoon width."""
        return self.layout_manager.webtoon_width
    
    @property
    def image_spacing(self) -> int:
        """Get image spacing."""
        return self.layout_manager.image_spacing
    
    @property
    def loaded_pages(self) -> Set[int]:
        """Get loaded pages."""
        return self.image_loader.loaded_pages
    
    @property
    def image_items(self) -> Dict[int, QGraphicsPixmapItem]:
        """Get image items."""
        return self.image_loader.image_items
    
    @property
    def image_data(self) -> Dict[int, np.ndarray]:
        """Get image data."""
        return self.image_loader.image_data
    
    @property
    def image_file_paths(self) -> List[str]:
        """Get image file paths."""
        return self.image_loader.image_file_paths

    # Event handling methods (called from the enhanced controller)
    def on_image_loaded(self, page_idx: int, cv2_img: np.ndarray):
        """Handle when an image is loaded - update coordinate converter."""
        # Update coordinate converter with new image data
        self.coordinate_converter.image_data[page_idx] = cv2_img
        
        # Load scene items for this page
        self.scene_item_manager.load_page_scene_items(page_idx)

    def on_image_unloaded(self, page_idx: int):
        """Handle when an image is unloaded - clean up coordinate converter."""
        # Remove from coordinate converter
        if page_idx in self.coordinate_converter.image_data:
            del self.coordinate_converter.image_data[page_idx]
        
        # Unload scene items for this page
        self.scene_item_manager.unload_page_scene_items(page_idx)

    # Enhanced controller compatibility properties and methods
    @property
    def load_timer(self):
        """Access to the load timer for enhanced controller configuration."""
        return self.image_loader.load_timer
    
    @property
    def max_loaded_pages(self) -> int:
        """Get maximum loaded pages configuration."""
        return self.image_loader.max_loaded_pages
    
    @max_loaded_pages.setter
    def max_loaded_pages(self, value: int):
        """Set maximum loaded pages configuration."""
        self.image_loader.max_loaded_pages = value
    
    @property
    def viewport_buffer(self) -> int:
        """Get viewport buffer configuration."""
        return self.layout_manager.viewport_buffer
    
    @viewport_buffer.setter
    def viewport_buffer(self, value: int):
        """Set viewport buffer configuration."""
        self.layout_manager.viewport_buffer = value
    
    def on_scroll(self):
        """Handle scroll events to trigger lazy loading."""
        # Use configured delay if available, otherwise default
        delay = getattr(self, '_scroll_timer_delay', 200)
        self.scroll_timer.start(delay)
    
    # Enhanced controller callback registration
    def set_enhanced_controller(self, controller):
        """Set enhanced controller reference for callbacks."""
        self.enhanced_controller = controller
        # Also set for image loader for any callbacks it might need
        if hasattr(self.image_loader, 'enhanced_controller'):
            self.image_loader.enhanced_controller = controller

    def _on_page_detection_enabled(self):
        """Called when page detection is enabled - notify enhanced controller."""
        if hasattr(self, 'enhanced_controller') and self.enhanced_controller:
            self.enhanced_controller._on_lazy_manager_ready()

    def get_cv2_image(self, page_index: int = None) -> np.ndarray:
        """Get CV2 image data for a specific page."""
        page_index = page_index if page_index is not None else self.layout_manager.current_page_index
        if 0 <= page_index < len(self.image_file_paths):
            return self.image_loader.get_image_data(page_index)
        return None
        
    def get_visible_area_image(self, paint_all=False, include_patches=True) -> tuple[np.ndarray, list]:
        """Get combined image of all visible pages and their mappings.
        
        Args:
            paint_all: If True, render all scene items (text, rectangles, etc.) onto the image
            include_patches: If True, include patch pixmap items in the output
        """
        if not self.image_positions:
            return None, []
        
        # Get viewport rectangle in scene coordinates
        vp_rect = self.viewer.mapToScene(self.viewer.viewport().rect()).boundingRect()
        visible_pages_data = []
        
        # Find all pages that are visible in the viewport
        for i, (y, h) in enumerate(zip(self.image_positions, self.image_heights)):
            if y < vp_rect.bottom() and y + h > vp_rect.top():
                # Calculate crop boundaries for this page
                crop_top = max(0, vp_rect.top() - y)
                crop_bottom = min(h, vp_rect.bottom() - y)
                
                if crop_bottom > crop_top:
                    # Get base image data for this page (might be None if not loaded)
                    base_image_data = self.image_loader.get_image_data(i)
                    
                    if base_image_data is not None:
                        # Process image based on requested options
                        if paint_all:
                            # Only use the complex rendering path when explicitly requested
                            processed_image = self._render_page_with_scene_items(
                                i, base_image_data, paint_all, include_patches, crop_top, crop_bottom
                            )
                        elif include_patches:
                            # Try the rendering path to properly include patches
                            processed_image = self._render_page_with_scene_items(
                                i, base_image_data, False, True, crop_top, crop_bottom
                            )
                        else:
                            # For include_patches=False, just use the base image
                            processed_image = base_image_data[int(crop_top):int(crop_bottom), :]
                        
                        visible_pages_data.append({
                            'page_index': i,
                            'image': processed_image,
                            'scene_y_start': max(vp_rect.top(), y),
                            'scene_y_end': min(vp_rect.bottom(), y + h),
                            'page_crop_top': crop_top,
                            'page_crop_bottom': crop_bottom
                        })
        
        if not visible_pages_data:
            return None, []
        
        # Calculate total height of combined image
        total_h = sum(d['image'].shape[0] for d in visible_pages_data)
        width = visible_pages_data[0]['image'].shape[1]
        channels = visible_pages_data[0]['image'].shape[2] if len(visible_pages_data[0]['image'].shape) > 2 else 1
        dtype = visible_pages_data[0]['image'].dtype
        
        # Create shape tuple
        shape = (total_h, width, channels) if channels > 1 else (total_h, width)
        combined_img = np.zeros(shape, dtype=dtype)

        # Combine all visible page images and create mappings
        current_y, mappings = 0, []
        for data in visible_pages_data:
            img = data['image']
            h_img = img.shape[0]
            
            # Copy image data to combined image
            combined_img[current_y:current_y + h_img] = img
            
            # Create mapping information
            mappings.append({
                'page_index': data['page_index'],
                'combined_y_start': current_y,
                'combined_y_end': current_y + h_img,
                'scene_y_start': data['scene_y_start'],
                'scene_y_end': data['scene_y_end'],
                'page_crop_top': data['page_crop_top'],
                'page_crop_bottom': data['page_crop_bottom']
            })
            current_y += h_img
        
        combined_img = cv2.cvtColor(combined_img, cv2.COLOR_BGR2RGB)
            
        return  combined_img, mappings

    def _render_page_with_scene_items(self, page_index: int, base_image: np.ndarray, 
                                     paint_all: bool, include_patches: bool, 
                                     crop_top: float, crop_bottom: float) -> np.ndarray:
        """Render a page with scene items (text, rectangles, patches) overlaid."""
        # Get the page's image item from the scene
        if page_index not in self.image_loader.image_items:
            # Fallback to just cropping the base image
            return base_image[int(crop_top):int(crop_bottom), :]
        
        page_item = self.image_loader.image_items[page_index]
        page_y_position = self.image_positions[page_index]
        page_height = self.image_heights[page_index]
        
        if paint_all:
            # Create a high-resolution QImage for rendering
            scale_factor = 2  # Increase for higher resolution
            original_size = page_item.pixmap().size()
            scaled_size = original_size * scale_factor

            qimage = QImage(scaled_size, QImage.Format_ARGB32)
            qimage.fill(Qt.transparent)

            # Create a QPainter with antialiasing
            painter = QPainter(qimage)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            # Store original transform and scene settings
            original_transform = self.viewer.transform()
            original_scene_rect = self._scene.sceneRect()
            
            # Reset transform temporarily
            self.viewer.resetTransform()
            
            # Set scene rect to cover this page
            page_scene_rect = QRectF(0, page_y_position, original_size.width(), page_height)
            self._scene.setSceneRect(page_scene_rect)
            
            # Render the scene area for this page
            self._scene.render(painter)
            painter.end()

            # Scale down the image to the original size
            qimage = qimage.scaled(
                original_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )

            # Restore the original transformation and scene rect
            self.viewer.setTransform(original_transform)
            self._scene.setSceneRect(original_scene_rect)
            
        elif include_patches:
            # Create QImage for just the base image and patches
            pixmap = page_item.pixmap()
            qimage = QImage(pixmap.size(), QImage.Format_ARGB32)
            qimage.fill(Qt.transparent)
            painter = QPainter(qimage)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            
            # Draw the base pixmap
            painter.drawPixmap(0, 0, pixmap)
            
            # In webtoon mode, patches are added directly to scene with scene coordinates
            # Calculate this page's bounds in scene coordinates
            page_scene_top = page_y_position
            page_scene_bottom = page_y_position + page_height
            page_scene_left = (self.layout_manager.webtoon_width - pixmap.width()) / 2  # Assuming centered
            page_scene_right = page_scene_left + pixmap.width()
            
            page_scene_bounds = QRectF(page_scene_left, page_scene_top, pixmap.width(), page_height)
            
            for item in self._scene.items():
                if isinstance(item, QGraphicsPixmapItem) and item != page_item:
                    # Check if this is a patch item (has the hash key data)
                    if item.data(0) is not None:  # HASH_KEY = 0 from PatchCommandBase
                        # Get patch bounds in scene coordinates
                        item_scene_pos = item.pos()
                        patch_width = item.pixmap().width()
                        patch_height = item.pixmap().height()
                        patch_scene_bounds = QRectF(item_scene_pos.x(), item_scene_pos.y(), 
                                                   patch_width, patch_height)
                        
                        # Check if this patch overlaps with the current page
                        if page_scene_bounds.intersects(patch_scene_bounds):
                            # Convert scene coordinates to page-local coordinates
                            page_local_x = item_scene_pos.x() - page_scene_left
                            page_local_y = item_scene_pos.y() - page_scene_top
                            
                            # Draw the patch at the converted coordinates
                            painter.drawPixmap(int(page_local_x), int(page_local_y), item.pixmap())
                            
            painter.end()
        else:
            # Just use the base image
            return base_image[int(crop_top):int(crop_bottom), :]

        # Convert QImage to cv2 image
        qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
        width = qimage.width()
        height = qimage.height()
        bytes_per_line = qimage.bytesPerLine()

        # Convert to numpy array
        ptr = qimage.bits()
        arr = np.array(ptr).reshape((height, bytes_per_line))
        # Exclude padding bytes
        arr = arr[:, :width * 3]
        # Reshape to correct dimensions
        arr = arr.reshape((height, width, 3))
        
        # Convert from BGR to RGB (QImage uses RGB format, cv2 expects BGR)
        cv2_img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        
        # Crop to the visible portion
        cropped_image = cv2_img[int(crop_top):int(crop_bottom), :]
        
        return cropped_image

    def remove_pages(self, file_paths_to_remove: List[str]) -> bool:
        """Remove specific pages from the webtoon manager without full reload."""
        try:
            # Find indices of pages to remove
            indices_to_remove = []
            for file_path in file_paths_to_remove:
                try:
                    index = self.image_loader.image_file_paths.index(file_path)
                    indices_to_remove.append(index)
                except ValueError:
                    continue
            
            if not indices_to_remove:
                return True  # Nothing to remove
            
            # Sort indices in descending order to remove from end to beginning
            indices_to_remove.sort(reverse=True)
            
            # Save current page for adjustment
            current_page = self.layout_manager.current_page_index
            
            # CRITICAL: Save scene items for all pages that will have their indices changed
            # Before removing any pages, we need to save all scene items to their file states
            self.scene_item_manager.save_all_scene_items_to_states()
            
            # Remove pages from each component (from highest index to lowest)
            for page_idx in indices_to_remove:
                
                # Force unload the page from memory
                if page_idx in self.image_loader.loaded_pages:
                    # Remove from loaded_pages first to avoid issues
                    self.image_loader.loaded_pages.discard(page_idx)
                    
                    # Remove image item from scene
                    if page_idx in self.image_loader.image_items:
                        self._scene.removeItem(self.image_loader.image_items[page_idx])
                        del self.image_loader.image_items[page_idx]
                        
                    # Remove image data from memory
                    if page_idx in self.image_loader.image_data:
                        del self.image_loader.image_data[page_idx]
                
                # Remove placeholder if it exists
                if page_idx in self.image_loader.placeholder_items:
                    self._scene.removeItem(self.image_loader.placeholder_items[page_idx])
                    del self.image_loader.placeholder_items[page_idx]
                
                # Remove from image_file_paths
                if page_idx < len(self.image_loader.image_file_paths):
                    self.image_loader.image_file_paths.pop(page_idx)
                
                # Remove from layout manager
                if page_idx < len(self.layout_manager.image_positions):
                    self.layout_manager.image_positions.pop(page_idx)
                if page_idx < len(self.layout_manager.image_heights):
                    self.layout_manager.image_heights.pop(page_idx)
                
                # Remove from scene item manager
                if page_idx < len(self.scene_item_manager.image_file_paths):
                    self.scene_item_manager.image_file_paths.pop(page_idx)
            
            # Adjust loaded page indices after removal
            new_loaded_pages = set()
            for old_idx in list(self.image_loader.loaded_pages):
                # Calculate new index after removals
                new_idx = old_idx
                for removed_idx in sorted(indices_to_remove):
                    if removed_idx < old_idx:
                        new_idx -= 1
                if new_idx >= 0:
                    new_loaded_pages.add(new_idx)
            self.image_loader.loaded_pages = new_loaded_pages
            
            # Adjust image items indices
            new_image_items = {}
            for old_idx, item in list(self.image_loader.image_items.items()):
                new_idx = old_idx
                for removed_idx in sorted(indices_to_remove):
                    if removed_idx < old_idx:
                        new_idx -= 1
                if new_idx >= 0:
                    new_image_items[new_idx] = item
            self.image_loader.image_items = new_image_items
            
            # Adjust image data indices
            new_image_data = {}
            for old_idx, data in list(self.image_loader.image_data.items()):
                new_idx = old_idx
                for removed_idx in sorted(indices_to_remove):
                    if removed_idx < old_idx:
                        new_idx -= 1
                if new_idx >= 0:
                    new_image_data[new_idx] = data
            self.image_loader.image_data = new_image_data
            
            # Adjust placeholder indices
            new_placeholder_items = {}
            for old_idx, placeholder in list(self.image_loader.placeholder_items.items()):
                new_idx = old_idx
                for removed_idx in sorted(indices_to_remove):
                    if removed_idx < old_idx:
                        new_idx -= 1
                if new_idx >= 0:
                    new_placeholder_items[new_idx] = placeholder
            self.image_loader.placeholder_items = new_placeholder_items
            
            # Adjust current page index if necessary
            removed_before_current = sum(1 for idx in indices_to_remove if idx < current_page)
            new_current_page = max(0, current_page - removed_before_current)
            
            # Ensure current page is within bounds
            if new_current_page >= len(self.image_loader.image_file_paths):
                new_current_page = max(0, len(self.image_loader.image_file_paths) - 1)
            
            # Update layout positions for remaining pages
            self._recalculate_layout()
            
            # Update current page
            if self.image_loader.image_file_paths:
                self.layout_manager.current_page_index = new_current_page
                
                # Force view update and scrollbar recalculation
                self.viewer.viewport().update()
                
                # Process events to ensure view updates
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
                
                # Scroll to the new current page
                if new_current_page < len(self.image_loader.image_file_paths):
                    self.scroll_to_page(new_current_page)
                else:
                    # If current page is out of bounds, scroll to the last page
                    if self.image_loader.image_file_paths:
                        last_page = len(self.image_loader.image_file_paths) - 1
                        self.layout_manager.current_page_index = last_page
                        self.scroll_to_page(last_page)
                
                print(f"Removed {len(indices_to_remove)} pages. New total: {len(self.image_loader.image_file_paths)}")
                print(f"New scene rect: {self._scene.sceneRect()}")
                print(f"New total height: {self.layout_manager.total_height}")
                
                # CRITICAL: After everything is adjusted, reload scene items for currently loaded pages
                # First, clear all scene items from the scene to avoid duplication
                self._clear_all_scene_items()
                
                # Then reload scene items for currently loaded pages
                # This ensures that scene items for pages with changed indices are properly restored
                for page_idx in list(self.image_loader.loaded_pages):
                    if page_idx < len(self.image_loader.image_file_paths):
                        self.scene_item_manager.load_page_scene_items(page_idx)
            else:
                # No pages left, clear everything
                self.clear()
                return False
            
            return True
            
        except Exception as e:
            print(f"Error removing pages from webtoon manager: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _recalculate_layout(self):
        """Recalculate layout positions after page removal."""
        if not self.image_loader.image_file_paths:
            self.layout_manager.total_height = 0
            self.layout_manager.image_positions.clear()
            self.layout_manager.image_heights.clear()
            self._scene.setSceneRect(0, 0, 0, 0)
            return
        
        # Recalculate positions from scratch
        current_y = 100
        new_positions = []
        
        for i in range(len(self.image_loader.image_file_paths)):
            new_positions.append(current_y)
            # Use existing height if available, otherwise estimate
            height = self.layout_manager.image_heights[i] if i < len(self.layout_manager.image_heights) else 1000
            current_y += height + self.layout_manager.image_spacing
        
        # Update layout manager with new positions
        self.layout_manager.image_positions = new_positions
        
        # Update total height
        self.layout_manager.total_height = current_y - self.layout_manager.image_spacing if new_positions else 0
        
        # Update scene rectangle to new dimensions
        scene_rect = QRectF(0, 0, self.layout_manager.webtoon_width, self.layout_manager.total_height)
        self._scene.setSceneRect(scene_rect)
        
        # Also update the viewer's scene rect to ensure scrollbars are updated
        self.viewer.setSceneRect(scene_rect)
        
        # Update coordinate converter with new layout
        self.coordinate_converter.update_layout(
            self.layout_manager.image_positions,
            self.layout_manager.image_heights,
            self.layout_manager.webtoon_width,
            self.image_loader.image_data
        )
        
        # Update image item positions for loaded pages
        for page_idx in list(self.image_loader.loaded_pages):
            if page_idx < len(self.layout_manager.image_positions) and page_idx in self.image_loader.image_items:
                item = self.image_loader.image_items[page_idx]
                y_pos = self.layout_manager.image_positions[page_idx]
                # Calculate x position (centered)
                if page_idx in self.image_loader.image_data:
                    img_width = self.image_loader.image_data[page_idx].shape[1]
                    x_offset = (self.layout_manager.webtoon_width - img_width) / 2
                else:
                    x_offset = item.pos().x()  # Keep existing x position
                item.setPos(x_offset, y_pos)
        
        # Update placeholder positions if any exist
        for page_idx in list(self.image_loader.placeholder_items.keys()):
            if page_idx < len(self.layout_manager.image_positions):
                placeholder = self.image_loader.placeholder_items[page_idx]
                y_pos = self.layout_manager.image_positions[page_idx]
                placeholder.setPos(0, y_pos)

    def _clear_all_scene_items(self):
        """Clear all scene items (rectangles, text, brush strokes, patches) from the scene to avoid duplication."""
        if not self._scene:
            return
            
        # Get all items from the scene
        all_items = self._scene.items().copy()
        
        for item in all_items:
            # Skip image items and placeholders - we only want to remove scene items
            if item in self.image_loader.image_items.values():
                continue
            if item in self.image_loader.placeholder_items.values():
                continue
                
            # Remove scene items (rectangles, text, brush strokes, patches, etc.)
            # These typically have data or specific types that distinguish them from image items
            try:
                from app.ui.canvas.text_item import TextBlockItem
                from app.ui.canvas.rectangle import MoveableRectItem
                from PySide6.QtWidgets import QGraphicsPathItem
                from PySide6.QtWidgets import QGraphicsPixmapItem
                
                # Remove text items, rectangle items, brush strokes (path items), and patch items
                if (isinstance(item, TextBlockItem) or 
                    isinstance(item, MoveableRectItem) or 
                    isinstance(item, QGraphicsPathItem) or
                    (isinstance(item, QGraphicsPixmapItem) and item.data(0) is not None)):  # Patches have hash data
                    self._scene.removeItem(item)
            except Exception as e:
                # If we can't identify the item type safely, skip it
                print(f"Warning: Could not remove scene item: {e}")
                pass

    def insert_pages(self, new_file_paths: List[str], insert_position: int = None) -> bool:
        """Insert new pages into the webtoon manager at the specified position."""
        try:
            if not new_file_paths:
                return True
                
            # If no position specified, insert at the end
            if insert_position is None:
                insert_position = len(self.image_file_paths)
            else:
                # Ensure insert position is within bounds
                insert_position = max(0, min(insert_position, len(self.image_file_paths)))
            
            # Save current scene items before making changes
            self.scene_item_manager.save_all_scene_items_to_states()
            
            # Insert new file paths
            for i, file_path in enumerate(new_file_paths):
                self.image_loader.image_file_paths.insert(insert_position + i, file_path)
                self.scene_item_manager.image_file_paths.insert(insert_position + i, file_path)
            
            # Estimate layout heights for new pages using better estimation
            new_heights = []
            for file_path in new_file_paths:
                # Try to get actual height from image metadata
                try:
                    import cv2
                    img = cv2.imread(file_path)
                    if img is not None:
                        h, w = img.shape[:2]
                        estimated_height = h
                    else:
                        # Use average height from existing pages if available
                        if self.layout_manager.image_heights:
                            estimated_height = sum(self.layout_manager.image_heights) // len(self.layout_manager.image_heights)
                        else:
                            estimated_height = 1000  # Default fallback
                except:
                    # Use average height from existing pages if available
                    if self.layout_manager.image_heights:
                        estimated_height = sum(self.layout_manager.image_heights) // len(self.layout_manager.image_heights)
                    else:
                        estimated_height = 1000  # Default fallback
                new_heights.append(estimated_height)
            
            # Insert new heights and positions into layout manager
            for i, height in enumerate(new_heights):
                self.layout_manager.image_heights.insert(insert_position + i, height)
            
            # Recalculate all layout positions
            self._recalculate_layout()
            
            # Adjust indices of loaded pages
            new_loaded_pages = set()
            for old_idx in list(self.image_loader.loaded_pages):
                new_idx = old_idx
                if old_idx >= insert_position:
                    new_idx += len(new_file_paths)
                new_loaded_pages.add(new_idx)
            self.image_loader.loaded_pages = new_loaded_pages
            
            # Adjust image items indices
            new_image_items = {}
            for old_idx, item in list(self.image_loader.image_items.items()):
                new_idx = old_idx
                if old_idx >= insert_position:
                    new_idx += len(new_file_paths)
                new_image_items[new_idx] = item
            self.image_loader.image_items = new_image_items
            
            # Adjust image data indices
            new_image_data = {}
            for old_idx, data in list(self.image_loader.image_data.items()):
                new_idx = old_idx
                if old_idx >= insert_position:
                    new_idx += len(new_file_paths)
                new_image_data[new_idx] = data
            self.image_loader.image_data = new_image_data
            
            # Adjust placeholder indices
            new_placeholder_items = {}
            for old_idx, placeholder in list(self.image_loader.placeholder_items.items()):
                new_idx = old_idx
                if old_idx >= insert_position:
                    new_idx += len(new_file_paths)
                new_placeholder_items[new_idx] = placeholder
            self.image_loader.placeholder_items = new_placeholder_items
            
            # Update current page index if necessary
            if self.layout_manager.current_page_index >= insert_position:
                self.layout_manager.current_page_index += len(new_file_paths)
            
            # Update coordinate converter with new layout
            self.coordinate_converter.update_layout(
                self.layout_manager.image_positions,
                self.layout_manager.image_heights,
                self.layout_manager.webtoon_width,
                self.image_loader.image_data
            )
            
            # Clear existing scene items and reload them with correct positions
            self._clear_all_scene_items()
            
            # Reload scene items for currently loaded pages
            for page_idx in list(self.image_loader.loaded_pages):
                if page_idx < len(self.image_loader.image_file_paths):
                    self.scene_item_manager.load_page_scene_items(page_idx)
            
            # Trigger a view update to show the changes
            self.viewer.viewport().update()
            
            # Force scrollbar recalculation by ensuring the scene rect is properly set
            self.viewer.updateSceneRect(self._scene.sceneRect())
            
            # Process events to ensure everything is updated
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            print(f"Inserted {len(new_file_paths)} pages at position {insert_position}. New total: {len(self.image_loader.image_file_paths)}")
            print(f"New scene rect: {self._scene.sceneRect()}")
            print(f"New total height: {self.layout_manager.total_height}")
            
            return True
            
        except Exception as e:
            print(f"Error inserting pages into webtoon manager: {e}")
            import traceback
            traceback.print_exc()
            return False
