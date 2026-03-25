import os
from collections import deque
from typing import Set
import imkit as imk
from PIL import Image
from PySide6.QtCore import QTimer, QThread, QObject, Signal, QSize, Qt, QPoint
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QListWidget
from app.path_materialization import ensure_path_materialized


class ImageLoadWorker(QObject):
    """Worker thread for loading images in the background."""
    
    image_loaded = Signal(int, str, QPixmap)  # index, file_path, pixmap
    
    def __init__(self):
        super().__init__()
        self.load_queue = deque()
        self.should_stop = False
        
        # Timer for processing queue
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.process_queue)
        self.process_timer.start(50)  # Process every 50ms
        
    def add_to_queue(self, index: int, file_path: str, target_size: QSize):
        """Add an image to the loading queue."""
        # Avoid duplicates
        for queued_index, _, _ in self.load_queue:
            if queued_index == index:
                return
        self.load_queue.append((index, file_path, target_size))
    
    def clear_queue(self):
        """Clear the loading queue."""
        self.load_queue.clear()
        
    def stop(self):
        """Stop the worker."""
        self.should_stop = True
        self.process_timer.stop()
        
    def process_queue(self):
        """Process the loading queue."""
        if not self.load_queue or self.should_stop:
            return
            
        index, file_path, target_size = self.load_queue.popleft()
        
        # Load and resize image
        pixmap = self._load_and_resize_image(file_path, target_size)
        if pixmap and not pixmap.isNull():
            self.image_loaded.emit(index, file_path, pixmap)
                
    def _load_and_resize_image(self, file_path: str, target_size: QSize) -> QPixmap:
        """Load and resize an image to the target size."""
        try:
            ensure_path_materialized(file_path)
            image = imk.read_image(file_path)
            if image is None:
                return QPixmap()
            
            # Resize maintaining aspect ratio
            height, width = image.shape[:2]
            target_width, target_height = target_size.width(), target_size.height()
            
            # Calculate scaling factor to fit within target size
            scale_x = target_width / width
            scale_y = target_height / height
            scale = min(scale_x, scale_y)
            
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            resized_image = imk.resize(image, (new_width, new_height), mode=Image.Resampling.LANCZOS)
            
            # Convert to QPixmap
            h, w, ch = resized_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(resized_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            return QPixmap.fromImage(qt_image)
            
        except Exception as e:
            print(f"Error processing image {file_path}: {e}")
            return QPixmap()


class ListViewImageLoader:
    """
    Lazy image loader for QListWidget that loads thumbnails only when visible.
    """
    
    def __init__(self, list_widget: QListWidget, avatar_size: tuple = (60, 80)):
        self.list_widget = list_widget
        self.avatar_size = QSize(avatar_size[0], avatar_size[1])
        
        # Track loaded images and visible items
        self.loaded_images: dict[int, QPixmap] = {}
        self.visible_items: Set[int] = set()
        self.file_paths: list[str] = []
        
        # Worker thread for background loading
        self.worker_thread = QThread()
        self.worker = ImageLoadWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker.image_loaded.connect(self._on_image_loaded)
        self.worker_thread.start()  # Start thread immediately
        
        # Timer for debouncing scroll events
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._update_visible_items)
        
        # Connect to list widget scroll events
        if hasattr(self.list_widget, 'verticalScrollBar'):
            scrollbar = self.list_widget.verticalScrollBar()
            if scrollbar:
                scrollbar.valueChanged.connect(self._on_scroll)
        
        # Configuration
        self.max_loaded_images = 20  # Maximum images to keep in memory
        self.preload_buffer = 2  # Number of items to preload outside visible area
        
    def set_file_paths(self, file_paths: list[str]):
        """Set the file paths for lazy loading."""
        self.clear()
        self.file_paths = file_paths.copy()
        
        # Start the worker thread if not already running
        if not self.worker_thread.isRunning():
            self.worker_thread.start()
            
        # Initial update
        self._schedule_update()
        
    def clear(self):
        """Clear all loaded images and reset state."""
        self.loaded_images.clear()
        self.visible_items.clear()
        self.file_paths.clear()
        if self.list_widget:
            for row in range(self.list_widget.count()):
                item = self.list_widget.item(row)
                if item:
                    item.setData(Qt.ItemDataRole.DecorationRole, None)
        
        if self.worker:
            self.worker.clear_queue()

    def remove_indices(self, removed_indices: list[int], file_paths: list[str]):
        """Remap loader state after rows have been removed from the list."""
        removed = sorted(set(removed_indices))
        if not removed:
            self.file_paths = file_paths.copy()
            return

        self.file_paths = file_paths.copy()
        self.visible_items = {
            new_idx for new_idx in (
                self._remap_index(idx, removed)
                for idx in self.visible_items
            ) if new_idx is not None
        }
        self.loaded_images = {
            new_idx: pixmap for old_idx, pixmap in self.loaded_images.items()
            for new_idx in [self._remap_index(old_idx, removed)]
            if new_idx is not None
        }

        if self.worker:
            self.worker.clear_queue()

        self._schedule_update()
            
    def _on_scroll(self):
        """Handle scroll events with debouncing."""
        self._schedule_update()
        
    def _schedule_update(self):
        """Schedule an update of visible items."""
        self.update_timer.start(100)  # 100ms debounce
        
    def _update_visible_items(self):
        """Update which items are visible and manage loading/unloading."""
        if not self.list_widget or not self.file_paths:
            return
            
        # Get visible item indices
        new_visible_items = self._get_visible_item_indices()
        
        # Determine which items need loading
        items_to_load = set()
        for index in new_visible_items:
            # Add visible items and buffer items
            start_idx = max(0, index - self.preload_buffer)
            end_idx = min(len(self.file_paths), index + self.preload_buffer + 1)
            items_to_load.update(range(start_idx, end_idx))
        
        # Load new items
        for index in items_to_load:
            if index not in self.loaded_images and 0 <= index < len(self.file_paths):
                self._queue_image_load(index)
        
        # Unload items that are no longer needed
        self._manage_memory(items_to_load)
        
        self.visible_items = new_visible_items
        
    def _get_visible_item_indices(self) -> Set[int]:
        """Get indices of currently visible items."""
        visible_indices = set()
        
        if not self.list_widget:
            return visible_indices
            
        # Get the viewport rect
        viewport_rect = self.list_widget.viewport().rect()

        probe_x = max(1, viewport_rect.center().x())
        top_item = self._find_visible_item(probe_x, viewport_rect.top(), 1, viewport_rect.bottom())
        bottom_item = self._find_visible_item(probe_x, max(0, viewport_rect.bottom() - 1), -1, viewport_rect.top())

        if top_item is None:
            return visible_indices

        top_index = self.list_widget.row(top_item)
        if bottom_item is not None:
            bottom_index = self.list_widget.row(bottom_item)
        else:
            row_height = max(1, self.list_widget.sizeHintForRow(top_index))
            visible_rows = max(1, (viewport_rect.height() // row_height) + 1)
            bottom_index = min(self.list_widget.count() - 1, top_index + visible_rows)

        visible_indices.update(range(top_index, bottom_index + 1))
        return visible_indices

    def _find_visible_item(self, x: int, start_y: int, step: int, limit_y: int):
        """Probe vertically within the viewport until a row is found."""
        y = start_y
        while (y <= limit_y) if step > 0 else (y >= limit_y):
            item = self.list_widget.itemAt(QPoint(x, y))
            if item is not None:
                return item
            y += step
        return None
        
    def _queue_image_load(self, index: int):
        """Queue an image for loading."""
        if 0 <= index < len(self.file_paths):
            file_path = self.file_paths[index]
            if ensure_path_materialized(file_path) or os.path.exists(file_path):
                self.worker.add_to_queue(index, file_path, self.avatar_size)
                
                # Start worker thread and process queue if not already running
                if not self.worker_thread.isRunning():
                    self.worker_thread.start()
                
                # Process the queue
                QTimer.singleShot(0, self.worker.process_queue)
                
    def _on_image_loaded(self, index: int, file_path: str, pixmap: QPixmap):
        """Handle when an image has been loaded."""
        if (
            0 <= index < self.list_widget.count()
            and index < len(self.file_paths)
            and self.file_paths[index] == file_path
        ):
            # Store the loaded pixmap
            self.loaded_images[index] = pixmap
            list_item = self.list_widget.item(index)
            if list_item:
                list_item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
                self.list_widget.viewport().update(self.list_widget.visualItemRect(list_item))
                
    def _manage_memory(self, needed_items: Set[int]):
        """Manage memory by unloading images that are no longer needed."""
        if len(self.loaded_images) <= self.max_loaded_images:
            return
            
        # Find items to unload (not in needed_items)
        items_to_unload = []
        for index in list(self.loaded_images.keys()):
            if index not in needed_items:
                items_to_unload.append(index)
                
        # Unload excess items
        excess_count = len(self.loaded_images) - self.max_loaded_images
        items_to_unload.sort()  # Unload in order
        
        for i, index in enumerate(items_to_unload):
            if i >= excess_count:
                break
                
            # Remove from memory
            del self.loaded_images[index]

            if 0 <= index < self.list_widget.count():
                item = self.list_widget.item(index)
                if item:
                    item.setData(Qt.ItemDataRole.DecorationRole, None)
                    
    def force_load_image(self, index: int):
        """Force load an image immediately (for current selection)."""
        if (0 <= index < len(self.file_paths) and 
            index not in self.loaded_images):
            self._queue_image_load(index)
            
    def shutdown(self):
        """Shutdown the loader and clean up resources."""
        if self.worker:
            self.worker.stop()
            
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(5000)  # Wait up to 5 seconds
            
        self.clear()

    @staticmethod
    def _remap_index(old_idx: int, removed_indices: list[int]) -> int | None:
        if old_idx in removed_indices:
            return None
        removed_before = sum(1 for rem_idx in removed_indices if rem_idx < old_idx)
        return old_idx - removed_before

