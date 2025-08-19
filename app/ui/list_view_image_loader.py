import os
import cv2
from typing import Set
from PySide6.QtCore import QTimer, QThread, QObject, Signal, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QListWidget


class ImageLoadWorker(QObject):
    """Worker thread for loading images in the background."""
    
    image_loaded = Signal(int, QPixmap)  # index, pixmap
    
    def __init__(self):
        super().__init__()
        self.load_queue = []
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
            
        index, file_path, target_size = self.load_queue.pop(0)
        
        try:
            # Load and resize image
            pixmap = self._load_and_resize_image(file_path, target_size)
            if pixmap and not pixmap.isNull():
                self.image_loaded.emit(index, pixmap)
        except Exception as e:
            print(f"Error loading image {file_path}: {e}")
                
    def _load_and_resize_image(self, file_path: str, target_size: QSize) -> QPixmap:
        """Load and resize an image to the target size."""
        try:
            # Use OpenCV to load the image for better performance
            cv2_image = cv2.imread(file_path)
            if cv2_image is None:
                return QPixmap()
                
            # Convert from BGR to RGB
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
            
            # Resize maintaining aspect ratio
            height, width = cv2_image.shape[:2]
            target_width, target_height = target_size.width(), target_size.height()
            
            # Calculate scaling factor to fit within target size
            scale_x = target_width / width
            scale_y = target_height / height
            scale = min(scale_x, scale_y)
            
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            resized_image = cv2.resize(cv2_image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
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
        self.cards = []  # Reference to the actual card widgets
        
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
        
    def set_file_paths(self, file_paths: list[str], cards: list):
        """Set the file paths and card references for lazy loading."""
        # Store cards reference before clearing (to avoid clearing the passed list)
        cards_copy = cards.copy() if cards else []
        
        self.clear()
        self.file_paths = file_paths.copy()
        self.cards = cards_copy  # Use the copy instead of the original reference
        
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
        self.cards.clear()
        
        if self.worker:
            self.worker.clear_queue()
            
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
        
        # Check each item to see if it's visible
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                item_rect = self.list_widget.visualItemRect(item)
                if viewport_rect.intersects(item_rect):
                    visible_indices.add(i)
                    
        return visible_indices
        
    def _queue_image_load(self, index: int):
        """Queue an image for loading."""
        if 0 <= index < len(self.file_paths):
            file_path = self.file_paths[index]
            if os.path.exists(file_path):
                self.worker.add_to_queue(index, file_path, self.avatar_size)
                
                # Start worker thread and process queue if not already running
                if not self.worker_thread.isRunning():
                    self.worker_thread.start()
                
                # Process the queue
                QTimer.singleShot(0, self.worker.process_queue)
                
    def _on_image_loaded(self, index: int, pixmap: QPixmap):
        """Handle when an image has been loaded."""
        if 0 <= index < len(self.cards):
            # Store the loaded pixmap
            self.loaded_images[index] = pixmap
            
            # Update the card's avatar
            card = self.cards[index]
            if card and hasattr(card, '_avatar'):
                card._avatar.set_dayu_image(pixmap)
                card._avatar.setVisible(True)
                
                # Update the list item size hint to ensure proper display
                list_item = self.list_widget.item(index)
                if list_item:
                    list_item.setSizeHint(card.sizeHint())
                
    def _manage_memory(self, needed_items: Set[int]):
        """Manage memory by unloading images that are no longer needed."""
        if len(self.loaded_images) <= self.max_loaded_images:
            return
            
        # Find items to unload (not in needed_items)
        items_to_unload = []
        for index in self.loaded_images.keys():
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
            
            # Hide avatar in card
            if 0 <= index < len(self.cards):
                card = self.cards[index]
                if card and hasattr(card, '_avatar'):
                    card._avatar.setVisible(False)
                    
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
