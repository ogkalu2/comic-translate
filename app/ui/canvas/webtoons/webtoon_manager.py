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
        
        # Initialize specialized components and establish ownership
        self.layout_manager = WebtoonLayoutManager(viewer)
        self.image_loader = LazyImageLoader(viewer, self.layout_manager)
        self.coordinate_converter = CoordinateConverter(self.layout_manager, self.image_loader)
        self.scene_item_manager = SceneItemManager(viewer, self.layout_manager, self.coordinate_converter, self.image_loader)
        
        # Set up cross-references between all components
        self.image_loader.scene_item_manager = self.scene_item_manager
        self.image_loader.coordinate_converter = self.coordinate_converter
        self.image_loader.webtoon_manager = self

        self.layout_manager.image_loader = self.image_loader
        self.layout_manager.coordinate_converter = self.coordinate_converter
        self.layout_manager.on_page_detection_enabled = self._on_page_detection_enabled

        self.scene_item_manager.image_loader = self.image_loader
        
        # Connect components to main controller (will be set later)
        self.main_controller = None
        self.image_loader.main_controller = None
        self.scene_item_manager.main_controller = None
        
        # Scroll handling for lazy loading
        self.scroll_timer = QTimer()
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self._update_loaded_pages)

    def load_images_lazy(self, file_paths: List[str], current_page: int = 0) -> bool:
        """Initialize webtoon mode with lazy loading."""
        try:
            if self.main_controller:
                self.main_controller.blk_list.clear()
            self.viewer.clear_scene()
            
            if not file_paths:
                self.viewer.empty = True
                return True
                
            self.viewer.empty = False
            
            # Set current page before any loading operations
            current_page = max(0, min(current_page, len(file_paths) - 1))
            self.layout_manager.current_page_index = current_page
            
            # Estimate layout first
            if not self.layout_manager.estimate_layout(file_paths):
                return False
                
            # Initialize image loader and scene item manager
            self.image_loader.initialize_images(file_paths, current_page)
            self.scene_item_manager.initialize() # No longer needs file_paths
            
            # Set up the view properly for webtoon mode
            if self.layout_manager.current_page_index == 0:
                self.viewer.fitInView()
            
            # Center the view on the current page if it's not page 0
            if self.layout_manager.current_page_index > 0:
                page_center_y = self.layout_manager.image_positions[current_page] + (self.layout_manager.image_heights[current_page] / 2)
                self.viewer.setSceneRect(0, 0, self.layout_manager.webtoon_width, self.layout_manager.total_height)
                self.viewer.centerOn(self.layout_manager.webtoon_width / 2, page_center_y)
            
            # Enable page detection after a delay to let viewport settle
            self.layout_manager.enable_page_detection_after_delay()
            
            return True
            
        except Exception as e:
            print(f"Error in lazy webtoon loading: {e}")
            if self.main_controller:
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
        return self.image_loader.scroll_to_page(page_index, position)

    def update_page_on_click(self, scene_pos: QPointF):
        """Check if a click occurred on a new page and update current page."""
        if self.layout_manager.update_page_on_click(scene_pos):
            # Page changed, emit signal
            self.viewer.page_changed.emit(self.layout_manager.current_page_index)

    def clear(self):
        """Clear all webtoon state."""
        self.scroll_timer.stop()
        
        # Clear all components in the correct order
        self.image_loader.clear()
        self.layout_manager.clear()
        self.scene_item_manager.clear()
        
    # Component access for enhanced controller
    def set_main_controller(self, controller):
        """Set the main controller reference for all components."""
        self.main_controller = controller
        self.image_loader.main_controller = controller
        self.scene_item_manager.set_main_controller(controller)

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

    # PROXY PROPERTIES to access data from the correct owner

    @property
    def image_positions(self) -> List[float]:
        """Get image positions from LayoutManager."""
        return self.layout_manager.image_positions
    
    @property
    def image_heights(self) -> List[float]:
        """Get image heights from LayoutManager."""
        return self.layout_manager.image_heights
    
    @property
    def total_height(self) -> float:
        """Get total height from LayoutManager."""
        return self.layout_manager.total_height
    
    @property
    def webtoon_width(self) -> float:
        """Get webtoon width from LayoutManager."""
        return self.layout_manager.webtoon_width
    
    @property
    def image_spacing(self) -> int:
        """Get image spacing from LayoutManager."""
        return self.layout_manager.image_spacing
    
    @property
    def loaded_pages(self) -> Set[int]:
        """Get loaded pages from ImageLoader."""
        return self.image_loader.loaded_pages
    
    @property
    def image_items(self) -> Dict[int, QGraphicsPixmapItem]:
        """Get image items from ImageLoader."""
        return self.image_loader.image_items
    
    @property
    def image_data(self) -> Dict[int, np.ndarray]:
        """Get image data from ImageLoader."""
        return self.image_loader.image_data
    
    @property
    def image_file_paths(self) -> List[str]:
        """Get image file paths from ImageLoader."""
        return self.image_loader.image_file_paths

    # Event handling methods (called from the enhanced controller)
    def on_image_loaded(self, page_idx: int, cv2_img: np.ndarray):
        """Handle when an image is loaded - load scene items for this page."""
        self.scene_item_manager.load_page_scene_items(page_idx)

    def on_image_unloaded(self, page_idx: int):
        """Handle when an image is unloaded - unload scene items for this page."""
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
        delay = getattr(self, '_scroll_timer_delay', 200)
        self.scroll_timer.start(delay)
    
    def set_enhanced_controller(self, controller):
        """Set enhanced controller reference for callbacks."""
        self.enhanced_controller = controller
        if hasattr(self.image_loader, 'enhanced_controller'):
            self.image_loader.enhanced_controller = controller

    def _on_page_detection_enabled(self):
        """Called when page detection is enabled - notify enhanced controller."""
        if hasattr(self, 'enhanced_controller') and self.enhanced_controller:
            self.enhanced_controller._on_lazy_manager_ready()

    def get_cv2_image(self, page_index: int = None) -> np.ndarray:
        """Get CV2 image data for a specific page."""
        page_index = page_index if page_index is not None else self.layout_manager.current_page_index
        return self.image_loader.get_image_data(page_index)
        
    def get_visible_area_image(self, paint_all=False, include_patches=True) -> tuple[np.ndarray, list]:
        """Proxy method to get combined image of all visible pages."""
        return self.image_loader.get_visible_area_image(paint_all, include_patches)

    def remove_pages(self, file_paths_to_remove: List[str]) -> bool:
        """Proxy method to remove specific pages from the webtoon manager."""
        return self.image_loader.remove_pages(file_paths_to_remove)

    def insert_pages(self, new_file_paths: List[str], insert_position: int = None) -> bool:
        """Proxy method to insert new pages into the webtoon manager."""
        return self.image_loader.insert_pages(new_file_paths, insert_position)