from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass
from PySide6.QtCore import QTimer


if TYPE_CHECKING:
    from controller import ComicTranslate

@dataclass
class LazyLoadingConfig:
    enabled: bool = True
    max_loaded_pages: int = 10
    viewport_buffer: int = 2
    load_timer_interval: int = 50
    scroll_debounce_delay: int = 150


class WebtoonController:
    """Webtoon controller with lazy loading support."""
    
    def __init__(self, main: ComicTranslate):
        self.main = main
        self._initialization_complete = False  # Track initialization state
        
        # Load lazy loading configuration
        config = LazyLoadingConfig()
        self.lazy_config = config
        self.lazy_loading_enabled = self.lazy_config.enabled
        
    @property
    def image_viewer(self):
        return self.main.image_viewer
        
    @property
    def image_files(self):
        return self.main.image_files
        
    @property
    def image_states(self):
        return self.main.image_states

    @property
    def current_file_path(self):
        """Get the current file path based on curr_img_idx."""
        curr_idx = self.main.curr_img_idx
        if 0 <= curr_idx < len(self.image_files):
            return self.image_files[curr_idx]
        return None

    def switch_to_webtoon_mode(self) -> bool:
        """Enhanced webtoon mode switch with lazy loading option."""
        if not self.image_files:
            print("No images loaded, cannot switch to webtoon mode")
            return False
            
        print(f"Switching to webtoon mode with {len(self.image_files)} images")
        return self._switch_to_lazy_webtoon_mode()

    def _switch_to_lazy_webtoon_mode(self) -> bool:
        """Switch to memory-efficient lazy loading webtoon mode."""

        self.main.image_ctrl.save_current_image_state()
        self.image_viewer.webtoon_manager.set_main_controller(self.main)
        
        # Get current page for initialization
        curr_img_idx = self.main.curr_img_idx
        current_page = max(0, min(curr_img_idx, len(self.image_files) - 1))
        
        # Load with lazy strategy, starting from current page
        success = self.image_viewer.load_images_webtoon(self.image_files, current_page)
        if not success:
            print("Failed to initialize lazy webtoon mode")
            return False
        
        # Apply configuration
        manager = self.image_viewer.webtoon_manager
        manager.max_loaded_pages = self.lazy_config.max_loaded_pages
        manager.viewport_buffer = self.lazy_config.viewport_buffer
        manager.load_timer.setInterval(self.lazy_config.load_timer_interval)
        manager.scroll_timer.setInterval(self.lazy_config.scroll_debounce_delay)
        
        manager.main = self.main
        manager.set_enhanced_controller(self)
        self.image_viewer.page_changed.connect(self.on_page_changed)
        manager.enhanced_controller = self
        manager.scene_item_manager.merge_clipped_items_back()
        self._setup_lazy_scene_items()
        self._connect_lazy_loading_events()
        self.image_viewer.webtoon_manager.restore_view_state()

        return True

    def _setup_lazy_scene_items(self):
        """Set up scene item management for lazy loading."""  
        # Clear scene items temporarily - they'll be reloaded when lazy pages load
        self.main.blk_list.clear()
        self.image_viewer.rectangles.clear()
        self.image_viewer.text_items.clear()
        
    def _connect_lazy_loading_events(self):
        """Connect events for lazy loading triggers."""
        # Connect scroll events to trigger lazy loading
        original_wheel_event = self.image_viewer.wheelEvent
        
        def enhanced_wheel_event(event):
            result = original_wheel_event(event)
            # Trigger lazy loading check after scroll
            if self.image_viewer.webtoon_manager:
                self.image_viewer.webtoon_manager.on_scroll()
            return result
        
        self.image_viewer.wheelEvent = enhanced_wheel_event
        
        # Also connect to viewport change events
        original_resizeEvent = self.image_viewer.resizeEvent
        
        def enhanced_resizeEvent(event):
            result = original_resizeEvent(event)
            # Trigger lazy loading update on viewport resize
            if self.image_viewer.webtoon_manager:
                self.image_viewer.webtoon_manager.on_scroll()
            return result
            
        self.image_viewer.resizeEvent = enhanced_resizeEvent

    def switch_to_regular_mode(self):
        """Switch back to regular mode with proper cleanup."""
        print("Switching to regular mode")
        
        if self.lazy_loading_enabled and hasattr(self.image_viewer, 'webtoon_manager'):
            self.image_viewer.webtoon_manager.save_view_state()
            # Disconnect page change signal
            try:
                self.image_viewer.page_changed.disconnect(self.on_page_changed)
            except:
                pass  # May not be connected
            
            # Transfer lazy-loaded items back to unified state before switching
            self._consolidate_lazy_items()
            
            # Clear lazy loading manager
            self.image_viewer.webtoon_manager.clear()
        
        # Continue with existing regular mode logic
        self._switch_to_regular_mode_existing()

    def _consolidate_lazy_items(self):
        """Consolidate lazy-loaded items back to unified scene state."""
        manager = self.image_viewer.webtoon_manager
        
        # Consolidate image data back to main controller
        for page_idx, img_array in manager.image_data.items():
            if page_idx < len(self.image_files):
                file_path = self.image_files[page_idx]
                self.main.image_data[file_path] = img_array
        
        # Save all currently visible scene items to their appropriate page states
        # This is crucial to ensure items from multiple pages are saved correctly
        manager.scene_item_manager.save_all_scene_items_to_states()
        
    def _switch_to_regular_mode_existing(self):
        """Use existing regular mode switch logic."""
        
        # Clear the scene to remove multi-page items
        self.main.blk_list.clear()
        self.image_viewer.clear_scene()
        
        # Make sure the image viewer is the current widget
        self.main.central_stack.setCurrentWidget(self.image_viewer)
        
        # Ensure the image viewer has focus
        self.image_viewer.setFocus()
        
        # Display the current image in regular mode (this will load only the current page's items)
        curr_img_idx = self.main.curr_img_idx
        if 0 <= curr_img_idx < len(self.image_files):
            self.main.image_ctrl.display_image(curr_img_idx, switch_page=False)

    # Page change handler for lazy loading
    def on_page_changed(self, page_index: int):
        """Handle page changes in lazy loading webtoon mode."""
        # Only respond if we're actually in lazy webtoon mode and not already processing a page change
        if (self.image_viewer.webtoon_mode and
            0 <= page_index < len(self.image_files) and
            not getattr(self.main, '_processing_page_change', False) and
            getattr(self, '_initialization_complete', False)):
            
            # Ignore rapid successive changes to the same page
            if (hasattr(self.main, '_last_page_change_index') and 
                self.main._last_page_change_index == page_index):
                return
                
            # Set flag to prevent recursive calls
            self.main._processing_page_change = True
            self.main._last_page_change_index = page_index
            
            try:
                # Update the current image index
                old_index = self.main.curr_img_idx
                self.main.curr_img_idx = page_index
                
                # Update the page list selection without triggering signals
                self.main.page_list.blockSignals(True)
                self.main.page_list.setCurrentRow(page_index)
                self.main.image_ctrl.highlight_card(page_index)
                self.main.page_list.blockSignals(False)
                
                # In lazy webtoon mode, do minimal state management to avoid interfering with scrolling
                # Only load language settings and basic state
                file_path = self.image_files[page_index]
                if file_path in self.image_states:
                    state = self.image_states[file_path]
                    # Only load language settings, don't load full image state
                    # Block signals to prevent triggering save when loading state
                    self.main.s_combo.blockSignals(True)
                    self.main.t_combo.blockSignals(True)
                    self.main.s_combo.setCurrentText(state.get('source_lang', ''))
                    self.main.t_combo.setCurrentText(state.get('target_lang', ''))
                    self.main.s_combo.blockSignals(False)
                    self.main.t_combo.blockSignals(False)
                    
                # Clear text edits
                self.main.text_ctrl.clear_text_edits()

                # Page-skip popup policy:
                # - show on explicit programmatic jumps (page list/report)
                # - hide during passive scrolling page changes
                explicit_navigation = bool(getattr(self.image_viewer, "_programmatic_scroll", False))
                self.main.image_ctrl.handle_webtoon_page_focus(file_path, explicit_navigation)
                    
            finally:
                # Use a timer to reset the processing flag to avoid blocking legitimate changes
                QTimer.singleShot(100, self._reset_page_change_flag)

    def _reset_page_change_flag(self):
        """Reset the page change processing flag."""
        self.main._processing_page_change = False

    def _on_lazy_manager_ready(self):
        """Called when the lazy manager has completed initialization."""
        self._initialization_complete = True

    def toggle_webtoon_mode(self):
        """Toggle between regular image viewer and webtoon mode."""
        requested_mode = self.main.webtoon_toggle.isChecked()
        
        # Don't do anything if we're already in the requested mode
        if self.main.webtoon_mode == requested_mode:
            return
            
        if requested_mode:
            # Switch to webtoon mode
            success = self.switch_to_webtoon_mode()
            if success:
                self.main.webtoon_mode = True
                self.main.mark_project_dirty()
            else:
                # Failed to switch, revert toggle
                self.main.webtoon_toggle.blockSignals(True)
                self.main.webtoon_toggle.setChecked(False)
                self.main.webtoon_toggle.blockSignals(False)
        else:
            # Switch back to regular mode
            self.main.webtoon_mode = False
            self.switch_to_regular_mode()
            self.main.mark_project_dirty()
