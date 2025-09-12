import numpy as np
from typing import Set, Optional
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem
from PySide6.QtCore import QTimer, QRectF, Qt
from PySide6.QtGui import QPixmap, QColor, QPen, QBrush, QImage, QPainter
import imkit as imk


class LazyImageLoader:
    """
    Memory-efficient image loader with lazy loading capabilities.
    This class is the single source of truth for image file paths and loaded image data.
    """
    
    def __init__(self, viewer, layout_manager):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self._scene = viewer._scene
        
        # Configuration
        self.max_loaded_pages = 10  # Maximum pages in memory
        
        # File path references (Owner of this data)
        self.image_file_paths: list[str] = []
        
        # Loaded content tracking (Owner of this data)
        self.loaded_pages: Set[int] = set()
        self.image_items: dict[int, QGraphicsPixmapItem] = {}  # page_index -> item
        self.image_data: dict[int, np.ndarray] = {}  # page_index -> RGB image
        self.placeholder_items: dict[int, QGraphicsRectItem] = {}  # page_index -> placeholder
        
        # Timers for debounced loading
        self.load_timer = QTimer()
        self.load_timer.timeout.connect(self._process_load_queue)
        
        # Loading queue and state
        self.load_queue: list[int] = []
        self.loading_pages: Set[int] = set()
        
        # References to other managers (will be set by LazyWebtoonManager)
        self.main_controller = None
        self.webtoon_manager = None  
        self.scene_item_manager = None
        self.coordinate_converter = None
    
    def initialize_images(self, file_paths: list[str], current_page: int = 0):
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
            file_path = self.image_file_paths[page_idx]
            img = imk.read_image(file_path)
            
            if img is not None:
                
                # Convert to QPixmap
                h, w, c = img.shape
                qimage = self.viewer.qimage_from_array(img)
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
                self.image_data[page_idx] = img
                self.loaded_pages.add(page_idx)
                
                # Also store in main controller's image_data for compatibility
                if self.main_controller and hasattr(self.main_controller, 'image_data'):
                    self.main_controller.image_data[file_path] = img
                
                # Notify webtoon manager that image is loaded (for scene item loading)
                if self.webtoon_manager and hasattr(self.webtoon_manager, 'on_image_loaded'):
                    self.webtoon_manager.on_image_loaded(page_idx, img)
                
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
        self.image_file_paths.clear()
        self.loaded_pages.clear()
        self.image_items.clear()
        self.image_data.clear()
        self.placeholder_items.clear()
        self.load_queue.clear()
        self.loading_pages.clear()

    def get_visible_area_image(self, paint_all=False, include_patches=True) -> tuple[np.ndarray, list]:
        """Get combined image of all visible pages and their mappings.
        
        Args:
            paint_all: If True, render all scene items (text, rectangles, etc.) onto the image
            include_patches: If True, include patch pixmap items in the output
        """
        if not self.layout_manager.image_positions:
            return None, []
        
        # Get viewport rectangle in scene coordinates
        vp_rect = self.viewer.mapToScene(self.viewer.viewport().rect()).boundingRect()
        visible_pages_data = []
        
        # Find all pages that are visible in the viewport
        for i, (y, h) in enumerate(zip(self.layout_manager.image_positions, self.layout_manager.image_heights)):
            if y < vp_rect.bottom() and y + h > vp_rect.top():
                # Calculate crop boundaries for this page
                crop_top = max(0, vp_rect.top() - y)
                crop_bottom = min(h, vp_rect.bottom() - y)
                
                if crop_bottom > crop_top:
                    # Get base image data for this page (might be None if not loaded)
                    base_image_data = self.get_image_data(i)
                    
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
        
        return combined_img, mappings

    def _render_page_with_scene_items(self, page_index: int, base_image: np.ndarray, 
                                     paint_all: bool, include_patches: bool, 
                                     crop_top: float, crop_bottom: float) -> np.ndarray:
        """Render a page with scene items (text, rectangles, patches) overlaid."""
        # Get the page's image item from the scene
        if page_index not in self.image_items:
            # Fallback to just cropping the base image
            return base_image[int(crop_top):int(crop_bottom), :]
        
        page_item = self.image_items[page_index]
        page_y_position = self.layout_manager.image_positions[page_index]
        page_height = self.layout_manager.image_heights[page_index]
        
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

        # Convert QImage to RGB numpy array
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
        
        # QImage uses RGB format, which matches our RGB workflow
        img = arr
        
        # Crop to the visible portion
        cropped_image = img[int(crop_top):int(crop_bottom), :]
        
        return cropped_image

    def scroll_to_page(self, page_index: int, position: str = 'top'):
        """Scroll to a specific page, loading it if necessary."""
        # Queue the target page for immediate loading
        self.queue_page_for_loading(page_index)
        
        # Delegate to layout manager
        success = self.layout_manager.scroll_to_page(page_index, position)
        
        if success:
            # Trigger loading update
            self._update_loaded_pages()
        
        return success
    
    def _update_loaded_pages(self):
        """Update which pages should be loaded based on current viewport."""
        # Delegate to image loader
        self.update_loaded_pages()
        
        # Update current page if we have loaded some pages
        if self.get_loaded_pages_count() > 2:
            # Check if page changed and emit signal if it did
            page_changed = self.layout_manager.update_current_page(self.get_loaded_pages_count())
            if page_changed:
                self.viewer.page_changed.emit(self.layout_manager.current_page_index)

    def remove_pages(self, file_paths_to_remove: list[str]) -> bool:
        """Remove specific pages from the webtoon manager without full reload."""
        try:
            # Find indices of pages to remove
            indices_to_remove = []
            for file_path in file_paths_to_remove:
                try:
                    index = self.image_file_paths.index(file_path)
                    indices_to_remove.append(index)
                except ValueError:
                    continue
            
            if not indices_to_remove:
                return True  # Nothing to remove
            
            # Sort indices in descending order to remove from end to beginning
            indices_to_remove.sort(reverse=True)
            
            # Save current page for adjustment
            current_page = self.layout_manager.current_page_index
            
            # Save scene items for all pages before removing any pages
            self.scene_item_manager.save_all_scene_items_to_states()
            
            # Remove pages from each component (from highest index to lowest)
            for page_idx in indices_to_remove:
                
                # Force unload the page from memory
                if page_idx in self.loaded_pages:
                    self.loaded_pages.discard(page_idx)
                    if page_idx in self.image_items:
                        self._scene.removeItem(self.image_items[page_idx])
                        del self.image_items[page_idx]
                    if page_idx in self.image_data:
                        del self.image_data[page_idx]
                
                # Remove placeholder if it exists
                if page_idx in self.placeholder_items:
                    self._scene.removeItem(self.placeholder_items[page_idx])
                    del self.placeholder_items[page_idx]
                
                # Remove from OWNED data structures
                if page_idx < len(self.image_file_paths):
                    self.image_file_paths.pop(page_idx)
                
                # Remove from layout manager's OWNED data
                if page_idx < len(self.layout_manager.image_positions):
                    self.layout_manager.image_positions.pop(page_idx)
                if page_idx < len(self.layout_manager.image_heights):
                    self.layout_manager.image_heights.pop(page_idx)
            
            # Adjust indices of all tracked items
            new_loaded_pages = {self._recalculate_index(old_idx, indices_to_remove) for old_idx in self.loaded_pages}
            self.loaded_pages = {idx for idx in new_loaded_pages if idx is not None}
            
            self.image_items = {self._recalculate_index(k, indices_to_remove): v for k, v in self.image_items.items() if self._recalculate_index(k, indices_to_remove) is not None}
            self.image_data = {self._recalculate_index(k, indices_to_remove): v for k, v in self.image_data.items() if self._recalculate_index(k, indices_to_remove) is not None}
            self.placeholder_items = {self._recalculate_index(k, indices_to_remove): v for k, v in self.placeholder_items.items() if self._recalculate_index(k, indices_to_remove) is not None}
            
            # Adjust current page index
            removed_before_current = sum(1 for idx in indices_to_remove if idx < current_page)
            new_current_page = max(0, current_page - removed_before_current)
            if new_current_page >= len(self.image_file_paths):
                new_current_page = max(0, len(self.image_file_paths) - 1)
            
            # Update layout positions for remaining pages
            self.layout_manager._recalculate_layout()
            
            # Update current page
            if self.image_file_paths:
                self.layout_manager.current_page_index = new_current_page
                
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
                
                # Scroll to the new current page
                if new_current_page < len(self.image_file_paths):
                    self.scroll_to_page(new_current_page)
                
                print(f"Removed {len(indices_to_remove)} pages. New total: {len(self.image_file_paths)}")
                
                # Reload scene items for currently loaded pages
                self.scene_item_manager._clear_all_scene_items()
                for page_idx in list(self.loaded_pages):
                    if page_idx < len(self.image_file_paths):
                        self.scene_item_manager.load_page_scene_items(page_idx)
            else:
                self.clear()
                self.layout_manager.clear()
                return False
            
            return True
            
        except Exception as e:
            print(f"Error removing pages from webtoon manager: {e}")
            import traceback
            traceback.print_exc()
            return False

    def insert_pages(self, new_file_paths: list[str], insert_position: int = None) -> bool:
        """Insert new pages into the webtoon manager at the specified position."""
        try:
            if not new_file_paths:
                return True
                
            if insert_position is None:
                insert_position = len(self.image_file_paths)
            else:
                insert_position = max(0, min(insert_position, len(self.image_file_paths)))
            
            # Save current scene items before making changes
            self.scene_item_manager.save_all_scene_items_to_states()
            
            # Insert new file paths into OWNED list
            for i, file_path in enumerate(new_file_paths):
                self.image_file_paths.insert(insert_position + i, file_path)
            
            # Estimate layout heights for new pages
            new_heights = []
            for file_path in new_file_paths:
                try:
                    img = imk.read_image(file_path)
                    estimated_height = img.shape[0] if img is not None else 1000
                except:
                    estimated_height = 1000
                new_heights.append(estimated_height)
            
            # Insert new heights into layout manager's OWNED list
            for i, height in enumerate(new_heights):
                self.layout_manager.image_heights.insert(insert_position + i, height)
            
            # Adjust indices of all tracked items
            num_inserted = len(new_file_paths)
            self.loaded_pages = {idx + num_inserted if idx >= insert_position else idx for idx in self.loaded_pages}
            self.image_items = {k + num_inserted if k >= insert_position else k: v for k, v in self.image_items.items()}
            self.image_data = {k + num_inserted if k >= insert_position else k: v for k, v in self.image_data.items()}
            self.placeholder_items = {k + num_inserted if k >= insert_position else k: v for k, v in self.placeholder_items.items()}
            
            # Adjust current page index
            if self.layout_manager.current_page_index >= insert_position:
                self.layout_manager.current_page_index += num_inserted

            # Recalculate all layout positions and update scene
            self.layout_manager._recalculate_layout()
            
            # Clear existing scene items and reload them with correct positions
            self.scene_item_manager._clear_all_scene_items()
            for page_idx in list(self.loaded_pages):
                if page_idx < len(self.image_file_paths):
                    self.scene_item_manager.load_page_scene_items(page_idx)
            
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            print(f"Inserted {len(new_file_paths)} pages. New total: {len(self.image_file_paths)}")
            
            return True
            
        except Exception as e:
            print(f"Error inserting pages into webtoon manager: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _recalculate_index(self, old_idx: int, removed_indices: list[int]) -> Optional[int]:
        """Calculates the new index of an item after removals."""
        if old_idx in removed_indices:
            return None
        removed_before = sum(1 for rem_idx in removed_indices if rem_idx < old_idx)
        return old_idx - removed_before
