import numpy as np
from typing import List, Dict, Set, Optional
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem
from PySide6.QtCore import QTimer, QPointF
from PySide6.QtGui import QPixmap, QColor, QPen, QBrush


class LazyImageLoader:
    """Memory-efficient image loader with lazy loading capabilities."""
    
    def __init__(self, viewer, layout_manager):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self._scene = viewer._scene
        
        # Configuration
        self.max_loaded_pages = 10  # Maximum pages in memory
        
        # Loaded content tracking
        self.loaded_pages: Set[int] = set()
        self.image_items: Dict[int, QGraphicsPixmapItem] = {}  # page_index -> item
        self.image_data: Dict[int, np.ndarray] = {}  # page_index -> cv2 image
        self.placeholder_items: Dict[int, QGraphicsRectItem] = {}  # page_index -> placeholder
        
        # File path references (for loading actual images)
        self.image_file_paths: List[str] = []
        
        # Timers for debounced loading
        self.load_timer = QTimer()
        self.load_timer.timeout.connect(self._process_load_queue)
        
        # Loading queue and state
        self.load_queue: List[int] = []
        self.loading_pages: Set[int] = set()
        
        # Main controller reference (set by lazy webtoon manager)
        self.main_controller = None
        self.webtoon_manager = None  # Reference to the lazy webtoon manager
    
    def initialize_images(self, file_paths: List[str], current_page: int = 0):
        """Initialize image loading with file paths."""
        self.image_file_paths = file_paths.copy()
        
        # Create placeholders for all pages
        self._create_placeholders()
        
        # Load initial pages centered around current page
        self._initial_load(current_page)
    
    def _create_placeholders(self):
        """Create placeholder rectangles for all pages."""
        for i in range(len(self.image_file_paths)):
            height = self.layout_manager.image_heights[i] if i < len(self.layout_manager.image_heights) else 1000
            placeholder = QGraphicsRectItem(0, 0, self.layout_manager.webtoon_width, height)
            placeholder.setBrush(QBrush(QColor(50, 50, 50)))  # Dark placeholder
            placeholder.setPen(QPen(QColor(80, 80, 80)))
            
            # Position placeholder
            y_pos = self.layout_manager.image_positions[i] if i < len(self.layout_manager.image_positions) else 0
            placeholder.setPos(0, y_pos)
            
            # Add loading text
            text_item = self._scene.addText(f"Loading page {i+1}...", self.viewer.font() if hasattr(self.viewer, 'font') else None)
            text_item.setDefaultTextColor(QColor(150, 150, 150))
            text_item.setPos(self.layout_manager.webtoon_width / 2 - 50, y_pos + height / 2)
            
            self._scene.addItem(placeholder)
            self.placeholder_items[i] = placeholder
    
    def _initial_load(self, current_page: int):
        """Load initial pages centered around current page."""
        # Load pages around the current page instead of always starting from 0
        start_page = max(0, current_page - 1)
        end_page = min(len(self.image_file_paths), current_page + 2)
        initial_pages = set(range(start_page, end_page))
        
        # Also determine what should be visible in the current viewport
        visible_pages = self.layout_manager.get_visible_pages()
        
        # Combine initial and visible pages
        pages_to_load = initial_pages | visible_pages
        
        # Queue initial pages for loading
        for page_idx in pages_to_load:
            self._queue_page_load(page_idx)
            
        # Start the loading timer
        self.load_timer.start(50)  # Process queue every 50ms
    
    def _queue_page_load(self, page_idx: int):
        """Queue a page for loading."""
        if (page_idx not in self.loaded_pages and 
            page_idx not in self.loading_pages and 
            page_idx not in self.load_queue and
            0 <= page_idx < len(self.image_file_paths)):
            
            self.load_queue.append(page_idx)
    
    def _process_load_queue(self):
        """Process the loading queue (one page at a time to keep UI responsive)."""
        if not self.load_queue:
            self.load_timer.stop()
            return
            
        # Load one page per timer tick for responsiveness
        page_idx = self.load_queue.pop(0)
        self._load_single_page(page_idx)
        
        # Continue processing if queue not empty
        if not self.load_queue:
            self.load_timer.stop()
    
    def _load_single_page(self, page_idx: int):
        """Load a single page's image and content."""
        if page_idx in self.loaded_pages or page_idx in self.loading_pages:
            return
            
        self.loading_pages.add(page_idx)
        
        try:
            # Load the actual image
            import cv2
            file_path = self.image_file_paths[page_idx]
            print(f"Loading image from: {file_path}")
            cv2_img = cv2.imread(file_path)
            
            if cv2_img is not None:
                cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
                
                # Convert to QPixmap
                h, w, c = cv2_img.shape
                qimage = self.viewer.qimage_from_cv2(cv2_img)
                pixmap = QPixmap.fromImage(qimage)
                
                # Create graphics item
                item = QGraphicsPixmapItem(pixmap)
                item.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
                
                # Position the item
                x_offset = (self.layout_manager.webtoon_width - w) / 2
                y_pos = self.layout_manager.image_positions[page_idx] if page_idx < len(self.layout_manager.image_positions) else 0
                item.setPos(x_offset, y_pos)
                
                # Update actual dimensions if different from estimate
                if page_idx < len(self.layout_manager.image_heights) and h != self.layout_manager.image_heights[page_idx]:
                    height_diff = self.layout_manager.adjust_layout_for_actual_size(page_idx, h)
                    if height_diff != 0:
                        self._adjust_subsequent_items(page_idx, height_diff)
                
                # Replace placeholder with actual image
                if page_idx in self.placeholder_items:
                    self._scene.removeItem(self.placeholder_items[page_idx])
                    del self.placeholder_items[page_idx]
                
                self._scene.addItem(item)
                self.image_items[page_idx] = item
                self.image_data[page_idx] = cv2_img
                self.loaded_pages.add(page_idx)
                
                # Also store in main controller's image_data for compatibility
                if self.main_controller and hasattr(self.main_controller, 'image_data'):
                    self.main_controller.image_data[file_path] = cv2_img
                
                # Notify webtoon manager that image is loaded (for scene item loading)
                if self.webtoon_manager and hasattr(self.webtoon_manager, 'on_image_loaded'):
                    self.webtoon_manager.on_image_loaded(page_idx, cv2_img)
                
                # If this is the current page being loaded, ensure proper view setup
                if page_idx == self.layout_manager.current_page_index and len(self.loaded_pages) == 1:
                    QTimer.singleShot(100, lambda: self.layout_manager.ensure_current_page_visible(self.image_items))
                    # Also emit page change signal to ensure UI is synchronized
                    QTimer.singleShot(150, lambda: self.viewer.page_changed.emit(page_idx))
                
        except Exception as e:
            import traceback
            print(f"DEBUG: Full traceback for page {page_idx}:")
            print(traceback.format_exc())
        finally:
            self.loading_pages.discard(page_idx)
            
        # Check if we need to unload old pages
        self._manage_memory()
    
    def _adjust_subsequent_items(self, page_idx: int, height_diff: int):
        """Adjust positions of subsequent loaded items after layout change."""
        for i in range(page_idx + 1, len(self.image_file_paths)):
            # Move any loaded items
            if i in self.image_items:
                item = self.image_items[i]
                pos = item.pos()
                item.setPos(pos.x(), pos.y() + height_diff)
                
            # Move placeholders
            if i in self.placeholder_items:
                item = self.placeholder_items[i]
                pos = item.pos()
                item.setPos(pos.x(), pos.y() + height_diff)
    
    def update_loaded_pages(self):
        """Update which pages should be loaded based on current viewport."""
        visible_pages = self.layout_manager.get_visible_pages()
        
        # Queue visible pages that aren't loaded
        for page_idx in visible_pages:
            if page_idx not in self.loaded_pages:
                self._queue_page_load(page_idx)
                
        # Start loading if queue has items
        if self.load_queue and not self.load_timer.isActive():
            self.load_timer.start(50)
    
    def _manage_memory(self):
        """Unload pages that are no longer needed to manage memory."""
        if len(self.loaded_pages) <= self.max_loaded_pages:
            return
            
        # Get currently visible pages
        visible_pages = self.layout_manager.get_visible_pages()
        
        # Find pages to unload (loaded but not visible)
        pages_to_unload = []
        for page_idx in self.loaded_pages:
            if page_idx not in visible_pages:
                pages_to_unload.append(page_idx)
                
        # Sort by distance from current viewport to unload farthest first
        current_center = self.viewer.mapToScene(self.viewer.viewport().rect().center()).y()
        pages_to_unload.sort(key=lambda p: abs(self.layout_manager.image_positions[p] - current_center), reverse=True)
        
        # Unload excess pages
        while len(self.loaded_pages) > self.max_loaded_pages and pages_to_unload:
            page_to_unload = pages_to_unload.pop(0)
            self._unload_page(page_to_unload)
    
    def _unload_page(self, page_idx: int):
        """Unload a specific page from memory."""
        if page_idx not in self.loaded_pages:
            return
            
        # Remove image item from scene
        if page_idx in self.image_items:
            self._scene.removeItem(self.image_items[page_idx])
            del self.image_items[page_idx]
            
        # Remove image data from memory
        if page_idx in self.image_data:
            del self.image_data[page_idx]
            
        # Recreate placeholder
        height = self.layout_manager.image_heights[page_idx] if page_idx < len(self.layout_manager.image_heights) else 1000
        placeholder = QGraphicsRectItem(0, 0, self.layout_manager.webtoon_width, height)
        placeholder.setBrush(QBrush(QColor(50, 50, 50)))
        placeholder.setPen(QPen(QColor(80, 80, 80)))
        y_pos = self.layout_manager.image_positions[page_idx] if page_idx < len(self.layout_manager.image_positions) else 0
        placeholder.setPos(0, y_pos)
        
        self._scene.addItem(placeholder)
        self.placeholder_items[page_idx] = placeholder
        
        self.loaded_pages.remove(page_idx)
            
        # Notify webtoon manager that image is unloaded (for scene item unloading)
        if self.webtoon_manager and hasattr(self.webtoon_manager, 'on_image_unloaded'):
            self.webtoon_manager.on_image_unloaded(page_idx)
            
        print(f"Unloaded page {page_idx + 1}")
    
    def set_timer_interval(self, interval: int):
        """Set the load timer interval."""
        self.load_timer.setInterval(interval)
    
    def get_timer_interval(self) -> int:
        """Get the current load timer interval."""
        return self.load_timer.interval()
    
    def is_timer_active(self) -> bool:
        """Check if the load timer is active."""
        return self.load_timer.isActive()
    
    def queue_page_for_loading(self, page_idx: int):
        """Public interface to queue a page for loading."""
        self._queue_page_load(page_idx)
        
        # Start loading if queue has items
        if self.load_queue and not self.load_timer.isActive():
            self.load_timer.start(50)
    
    def get_loaded_pages_count(self) -> int:
        """Get the number of currently loaded pages."""
        return len(self.loaded_pages)
    
    def is_page_loaded(self, page_idx: int) -> bool:
        """Check if a page is currently loaded."""
        return page_idx in self.loaded_pages
    
    def get_image_data(self, page_idx: int) -> Optional[np.ndarray]:
        """Get the image data for a specific page if loaded."""
        return self.image_data.get(page_idx)
    
    def clear(self):
        """Clear all image loading state."""
        # Stop timers
        self.load_timer.stop()
        
        # Clear all data structures
        self.loaded_pages.clear()
        self.image_items.clear()
        self.image_data.clear()
        self.placeholder_items.clear()
        self.load_queue.clear()
        self.loading_pages.clear()
        
        # Clear collections
        self.image_file_paths.clear()
