"""
Patch Manager for Webtoon Mode

Handles inpaint patches loading/unloading in webtoon mode with lazy loading.
"""

import cv2
from typing import List, Dict
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsPixmapItem
from PySide6.QtGui import QPixmap

from app.ui.commands.base import PatchCommandBase


class PatchManager:
    """Manages inpaint patches for webtoon mode with lazy loading."""
    
    def __init__(self, viewer, layout_manager, coordinate_converter):
        self.viewer = viewer
        self.layout_manager = layout_manager
        self.coordinate_converter = coordinate_converter
        self._scene = viewer._scene
        
        # Main controller reference (set by scene item manager)
        self.main_controller = None
        
        # File path references
        self.image_file_paths: List[str] = []
        
        # Track loaded patch items per page
        self.loaded_patch_items: Dict[int, List[QGraphicsPixmapItem]] = {}
    
    def initialize(self, file_paths: List[str]):
        """Initialize patch manager with file paths."""
        self.image_file_paths = file_paths.copy()
        self.loaded_patch_items.clear()
    
    def load_patches(self, page_idx: int):
        """Load inpaint patches for a specific page."""
        if not self.main_controller or page_idx >= len(self.image_file_paths):
            return
            
        # Use the main controller's image_files as the source of truth for file paths
        # This ensures we're using the most up-to-date paths after deletions
        if self.main_controller.image_files:
            if self.image_file_paths != self.main_controller.image_files:
                self.image_file_paths = self.main_controller.image_files.copy()
        
        file_path = self.image_file_paths[page_idx]

        print(self.image_file_paths)

        # Don't reload if already loaded
        if page_idx in self.loaded_patch_items:
            return
            
        # Create a new list for this page's patch items
        self.loaded_patch_items[page_idx] = []
        
        # Load persistent patches from image_patches
        if file_path in self.main_controller.image_patches:
            patches = self.main_controller.image_patches[file_path]
            
            for patch_data in patches:
                # Create properties dict with png_path for loading
                prop = {
                    'bbox': patch_data['bbox'],
                    'png_path': patch_data['png_path'],
                    'hash': patch_data['hash']
                }
                
                # Always convert from bbox even if scene_pos is available
                # scene pos data may be stale if an image has been deleted
                bbox = prop['bbox']
                page_local_pos = QPointF(bbox[0], bbox[1])
                scene_pos = self.coordinate_converter.page_local_to_scene_position(page_local_pos, page_idx)
                prop['scene_pos'] = [scene_pos.x(), scene_pos.y()]
                prop['page_index'] = page_idx
                
                # Check if this patch item already exists in the scene to avoid duplicates
                if not PatchCommandBase.find_matching_item(self._scene, prop):
                    # Create and position the patch item using scene coordinates
                    patch_item = PatchCommandBase.create_patch_item(prop, self.viewer)
                    if patch_item:
                        self.loaded_patch_items[page_idx].append(patch_item)
                        # Also add to in-memory patches if not already there
                        mem_list = self.main_controller.in_memory_patches.setdefault(file_path, [])
                        if not any(p['hash'] == prop['hash'] for p in mem_list):
                            # Load image for in-memory storage
                            cv_img = cv2.imread(patch_data['png_path'])
                            if cv_img is not None:
                                mem_prop = {
                                    'bbox': patch_data['bbox'],
                                    'cv2_img': cv_img,
                                    'hash': patch_data['hash']
                                }
                                mem_list.append(mem_prop)
    
    def unload_patches(self, page_idx: int):
        """Unload inpaint patches for a specific page."""
        if page_idx not in self.loaded_patch_items:
            return
            
        # Remove patch items from scene
        for patch_item in self.loaded_patch_items[page_idx]:
            if patch_item.scene() == self._scene:
                self._scene.removeItem(patch_item)
        
        # Clear the loaded items list
        del self.loaded_patch_items[page_idx]
    
    def get_patches_in_page_bounds(self, page_idx: int) -> List[QGraphicsPixmapItem]:
        """Get all patch items that belong to a specific page."""
        if page_idx not in self.loaded_patch_items:
            return []
        return self.loaded_patch_items[page_idx].copy()
    
    def clear_all_patches(self):
        """Clear all loaded patch items."""
        for page_idx in list(self.loaded_patch_items.keys()):
            self.unload_patches(page_idx)
    
    def clear(self):
        """Clear all patch management state."""
        self.image_file_paths.clear()
        self.loaded_patch_items.clear()
