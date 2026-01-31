from __future__ import annotations

import os
import imkit as imk
import numpy as np
from typing import TYPE_CHECKING, List
from PySide6 import QtCore, QtWidgets, QtGui

from app.ui.dayu_widgets.clickable_card import ClickMeta
from app.ui.dayu_widgets.message import MMessage
from app.ui.commands.image import SetImageCommand, ToggleSkipImagesCommand
from app.ui.commands.inpaint import PatchInsertCommand
from app.ui.commands.inpaint import PatchCommandBase
from app.ui.commands.box import AddTextItemCommand
from app.ui.list_view_image_loader import ListViewImageLoader

if TYPE_CHECKING:
    from controller import ComicTranslate


class ImageStateController:
    def __init__(self, main: ComicTranslate):
        self.main = main
        
        # Initialize lazy image loader for list view
        self.page_list_loader = ListViewImageLoader(
            self.main.page_list,
            avatar_size=(35, 50)
        )

    def load_initial_image(self, file_paths: List[str]):
        file_paths = self.main.file_handler.prepare_files(file_paths)
        self.main.image_files = file_paths

        if file_paths:
            return self.load_image(file_paths[0])
        return None
    
    def load_image(self, file_path: str) -> np.ndarray:
        if file_path in self.main.image_data:
            return self.main.image_data[file_path]

        # Check if the image has been displayed before
        if file_path in self.main.image_history:
            # Get the current index from the history
            current_index = self.main.current_history_index[file_path]
            
            # Get the temp file path at the current index
            current_temp_path = self.main.image_history[file_path][current_index]
            
            # Load the image from the temp file
            rgb_image = imk.read_image(current_temp_path)
            
            if rgb_image is not None:
                return rgb_image

        # If not in memory and not in history (or failed to load from temp),
        # load from the original file path
        rgb_image = imk.read_image(file_path)
        return rgb_image


    def clear_state(self):
        # Clear existing image data
        self.main.setWindowTitle("Project1.ctpr[*]")
        self.main.image_files = []
        self.main.image_states.clear()
        self.main.image_data.clear()
        self.main.image_history.clear()
        self.main.current_history_index.clear()
        self.main.blk_list = []
        self.main.displayed_images.clear()
        self.main.image_viewer.clear_rectangles(page_switch=True)
        self.main.image_viewer.clear_brush_strokes(page_switch=True)
        self.main.s_text_edit.clear()
        self.main.t_text_edit.clear()
        self.main.image_viewer.clear_text_items()
        self.main.loaded_images = []
        self.main.in_memory_history.clear()
        self.main.undo_stacks.clear()
        self.main.image_patches.clear()
        self.main.in_memory_patches.clear()
        self.main.project_file = None
        self.main.image_cards.clear()
        self.main.current_card = None
        self.main.page_list.blockSignals(True)
        self.main.page_list.clear()
        self.main.page_list.blockSignals(False)
        self.page_list_loader.clear()

        # Reset current_image_index
        self.main.curr_img_idx = -1
        self.main.set_project_clean()

    def thread_load_images(self, paths: List[str]):
        if paths and paths[0].lower().endswith('.ctpr'):
            self.main.project_ctrl.thread_load_project(paths[0])
            return
        self.clear_state()
        self.main.run_threaded(self.load_initial_image, self.on_initial_image_loaded, self.main.default_error_handler, None, paths)

    def thread_insert(self, paths: List[str]):
        if self.main.image_files:
            def on_files_prepared(prepared_files):
                if not prepared_files:
                    return
                # Save current state and determine insert position
                self.save_current_image_state()
                
                # Insert at the end of the list
                insert_position = len(self.main.image_files)
                
                # Insert files into the main image_files list
                for i, file_path in enumerate(prepared_files):
                    self.main.image_files.insert(insert_position + i, file_path)
                    
                    # Initialize image state for new files
                    self.main.image_data[file_path] = None
                    self.main.image_history[file_path] = [file_path]
                    self.main.in_memory_history[file_path] = []
                    self.main.current_history_index[file_path] = 0
                    
                    # Initialize empty image state for new files
                    skip_status = False
                    self.main.image_states[file_path] = {
                        'viewer_state': {},
                        'source_lang': self.main.s_combo.currentText(),
                        'target_lang': self.main.t_combo.currentText(),
                        'brush_strokes': [],
                        'blk_list': [],  # New images start with empty block list
                        'skip': skip_status,
                    }
                    
                    # Create undo stack for new file
                    stack = QtGui.QUndoStack(self.main)
                    stack.cleanChanged.connect(self.main._update_window_modified)
                    self.main.undo_stacks[file_path] = stack
                    self.main.undo_group.addStack(stack)
                
                # Handle webtoon mode specific updates
                if self.main.webtoon_mode:
                    # Use the insert_pages method for webtoon mode
                    success = self.main.image_viewer.webtoon_manager.insert_pages(prepared_files, insert_position)
                    
                    if success:
                        # Update image cards and set selection to the first inserted image
                        self.update_image_cards()
                        self.main.page_list.blockSignals(True)
                        self.main.page_list.setCurrentRow(insert_position)
                        self.highlight_card(insert_position)
                        self.main.page_list.blockSignals(False)
                        
                        # Update current index to the first inserted image
                        self.main.curr_img_idx = insert_position
                    else:
                        # Fallback to full reload if insert failed
                        current_page = max(0, self.main.curr_img_idx)
                        self.main.image_viewer.webtoon_manager.load_images_lazy(self.main.image_files, current_page)
                        self.update_image_cards()
                        self.main.page_list.blockSignals(True)
                        self.main.page_list.setCurrentRow(current_page)
                        self.highlight_card(current_page)
                        self.main.page_list.blockSignals(False)
                else:
                    # Handle normal mode
                    self.update_image_cards()
                    self.main.page_list.setCurrentRow(insert_position)
                    
                    # Load and display the first inserted image
                    path = prepared_files[0]
                    new_index = self.main.image_files.index(path)
                    im = self.load_image(path)
                    self.display_image_from_loaded(im, new_index, False)
                self.main.mark_project_dirty()

            self.main.run_threaded(
                lambda: self.main.file_handler.prepare_files(paths, True),
                on_files_prepared,
                self.main.default_error_handler)
        else:
            self.thread_load_images(paths)

    def on_initial_image_loaded(self, rgb_image: np.ndarray):
        if rgb_image is not None:
            self.main.image_data[self.main.image_files[0]] = rgb_image
            self.main.image_history[self.main.image_files[0]] = [self.main.image_files[0]]
            self.main.in_memory_history[self.main.image_files[0]] = [rgb_image.copy()]
            self.main.current_history_index[self.main.image_files[0]] = 0
            self.save_image_state(self.main.image_files[0])

        for file in self.main.image_files:
            self.save_image_state(file)
            stack = QtGui.QUndoStack(self.main)
            stack.cleanChanged.connect(self.main._update_window_modified)
            try:
                if hasattr(self.main, "search_ctrl") and self.main.search_ctrl is not None:
                    stack.indexChanged.connect(self.main.search_ctrl.on_undo_redo)
            except Exception:
                pass
            self.main.undo_stacks[file] = stack
            self.main.undo_group.addStack(stack)

        if self.main.image_files:
            self.main.page_list.blockSignals(True)
            self.update_image_cards()
            self.main.page_list.blockSignals(False)
            self.main.page_list.setCurrentRow(0)
            self.main.loaded_images.append(self.main.image_files[0])
        else:
            self.main.image_viewer.clear_scene()

        self.main.image_viewer.resetTransform()
        self.main.image_viewer.fitInView()
        if self.main.image_files:
            self.main.mark_project_dirty()

    def update_image_cards(self):
        # Clear existing items
        self.main.page_list.clear()
        self.main.image_cards.clear()
        self.main.current_card = None

        # Add new items
        for index, file_path in enumerate(self.main.image_files):
            file_name = os.path.basename(file_path)
            list_item = QtWidgets.QListWidgetItem(file_name)
            card = ClickMeta(extra=False, avatar_size=(35, 50))
            card.setup_data({
                "title": file_name,
                # Avatar will be loaded lazily
            })
            
            # Set the list item size hint to match the card size
            list_item.setSizeHint(card.sizeHint())
            
            # re-apply strike-through if previously skipped
            if self.main.image_states.get(file_path, {}).get('skip'):
                card.set_skipped(True)
            self.main.page_list.addItem(list_item)
            self.main.page_list.setItemWidget(list_item, card)
            self.main.image_cards.append(card)

        # Initialize lazy loading for the new cards
        self.page_list_loader.set_file_paths(self.main.image_files, self.main.image_cards)

    def on_card_selected(self, current, previous):
        if current:  
            index = self.main.page_list.row(current)
            self.main.curr_tblock_item = None
            # Force load the selected image thumbnail
            self.page_list_loader.force_load_image(index)

            # Avoid circular calls when in webtoon mode
            if getattr(self.main, '_processing_page_change', False):
                return
            
            if self.main.webtoon_mode:
                # In webtoon mode, just scroll to the page using the unified image viewer
                if self.main.image_viewer.hasPhoto():
                    print(f"Card selected: scrolling to page {index}")
                    
                    # Set the current index immediately to avoid confusion
                    self.main.curr_img_idx = index
                    
                    # Scroll to the page (this will set _programmatic_scroll = True)
                    self.main.image_viewer.scroll_to_page(index)
                    # Note: highlighting is now handled by on_selection_changed
                    
                    # Load minimal page state without interfering with the webtoon view
                    file_path = self.main.image_files[index]
                    if file_path in self.main.image_states:
                        state = self.main.image_states[file_path]
                        # Only load language settings in webtoon mode
                        # Block signals to prevent triggering save when loading state
                        self.main.s_combo.blockSignals(True)
                        self.main.t_combo.blockSignals(True)
                        self.main.s_combo.setCurrentText(state.get('source_lang', ''))
                        self.main.t_combo.setCurrentText(state.get('target_lang', ''))
                        self.main.s_combo.blockSignals(False)
                        self.main.t_combo.blockSignals(False)
                        
                    # Clear text edits
                    self.main.text_ctrl.clear_text_edits()
                else:
                    # Webtoon viewer not ready, fall back to regular mode
                    self.main.run_threaded(
                        lambda: self.load_image(self.main.image_files[index]),
                        lambda result: self.display_image_from_loaded(result, index),
                        self.main.default_error_handler
                        # Note: highlighting is now handled by on_selection_changed
                    )
            else:
                # Regular mode - load and display the image
                self.main.run_threaded(
                    lambda: self.load_image(self.main.image_files[index]),
                    lambda result: self.display_image_from_loaded(result, index),
                    self.main.default_error_handler
                    # Note: highlighting is now handled by on_selection_changed
                )

    def navigate_images(self, direction: int):
        if self.main.image_files:
            new_index = self.main.curr_img_idx + direction
            if 0 <= new_index < len(self.main.image_files):
                item = self.main.page_list.item(new_index)
                self.main.page_list.setCurrentItem(item)

    def highlight_card(self, index: int):
        """Highlight a single card (used for programmatic selection when signals are blocked)."""
        # Clear highlights from all cards first
        for card in self.main.image_cards:
            card.set_highlight(False)
            
        # Highlight the specified card
        if 0 <= index < len(self.main.image_cards):
            self.main.image_cards[index].set_highlight(True)
            self.main.current_card = self.main.image_cards[index]
        else:
            self.main.current_card = None

    def on_selection_changed(self, selected_indices: list):
        """Handle selection changes and update visual highlighting for all selected cards."""
        # Clear highlights from all cards first
        for card in self.main.image_cards:
            card.set_highlight(False)
        
        # Highlight all selected cards
        for index in selected_indices:
            if 0 <= index < len(self.main.image_cards):
                self.main.image_cards[index].set_highlight(True)
        
        # Keep track of the current card
        if selected_indices:
            current_index = selected_indices[-1]  # Use the last selected as current
            if 0 <= current_index < len(self.main.image_cards):
                self.main.current_card = self.main.image_cards[current_index]
        else:
            self.main.current_card = None

    def handle_image_deletion(self, file_names: list[str]):
        """Handles the deletion of images based on the provided file names."""

        self.save_current_image_state()
        removed_any = False
        
        # Delete the files first.
        for file_name in file_names:
            # Find the full file path based on the file name
            file_path = next((f for f in self.main.image_files if os.path.basename(f) == file_name), None)
            
            if file_path:
                # Remove from the image_files list
                self.main.image_files.remove(file_path)
                removed_any = True
                
                # Remove associated data
                self.main.image_data.pop(file_path, None)
                self.main.image_history.pop(file_path, None)
                self.main.in_memory_history.pop(file_path, None)
                self.main.current_history_index.pop(file_path, None)
                self.main.image_states.pop(file_path, None)  
                self.main.image_patches.pop(file_path, None)  
                self.main.in_memory_patches.pop(file_path, None)  

                if file_path in self.main.undo_stacks:
                    stack = self.main.undo_stacks[file_path]
                    self.main.undo_group.removeStack(stack)
                
                # Remove from other collections
                self.main.undo_stacks.pop(file_path, None)
                    
                if file_path in self.main.displayed_images:
                    self.main.displayed_images.remove(file_path)
                    
                if file_path in self.main.loaded_images:
                    self.main.loaded_images.remove(file_path)

        # Handle webtoon mode specific updates
        if self.main.webtoon_mode:
            # Use non-destructive page removal in webtoon mode
            if self.main.image_files:
                # Get full file paths of deleted files from the webtoon manager's file paths
                webtoon_file_paths = self.main.image_viewer.webtoon_manager.image_loader.image_file_paths
                deleted_file_paths = []
                for file_name in file_names:
                    # Find matching file paths in webtoon manager
                    matching_paths = [fp for fp in webtoon_file_paths if os.path.basename(fp) == file_name]
                    deleted_file_paths.extend(matching_paths)
                
                # Remove pages non-destructively from webtoon manager
                success = self.main.image_viewer.webtoon_manager.remove_pages(deleted_file_paths)
                
                if success:
                    # Adjust current index if necessary
                    if self.main.curr_img_idx >= len(self.main.image_files):
                        self.main.curr_img_idx = len(self.main.image_files) - 1
                    
                    current_page = max(0, self.main.curr_img_idx)
                    self.update_image_cards()
                    self.main.page_list.blockSignals(True)
                    self.main.page_list.setCurrentRow(current_page)
                    self.highlight_card(current_page)
                    self.main.page_list.blockSignals(False)
                else:
                    # Fallback to full reload if non-destructive removal failed
                    current_page = max(0, self.main.curr_img_idx)
                    self.main.image_viewer.webtoon_manager.load_images_lazy(self.main.image_files, current_page)
                    self.update_image_cards()
                    self.main.page_list.blockSignals(True)
                    self.main.page_list.setCurrentRow(current_page)
                    self.highlight_card(current_page)
                    self.main.page_list.blockSignals(False)
            else:
                # If no images remain, exit webtoon mode and reset to drag browser
                self.main.webtoon_mode = False
                self.main.image_viewer.webtoon_manager.clear()
                self.main.curr_img_idx = -1
                self.main.central_stack.setCurrentWidget(self.main.drag_browser)
                self.update_image_cards()
        else:
            # Handle normal mode
            if self.main.image_files:
                if self.main.curr_img_idx >= len(self.main.image_files):
                    self.main.curr_img_idx = len(self.main.image_files) - 1

                new_index = max(0, self.main.curr_img_idx - 1)
                file = self.main.image_files[new_index]
                im = self.load_image(file)
                self.display_image_from_loaded(im, new_index, False)
                self.update_image_cards()
                self.main.page_list.blockSignals(True)
                self.main.page_list.setCurrentRow(new_index)
                self.highlight_card(new_index)
                self.main.page_list.blockSignals(False)
            else:
                # If no images remain, reset the view to the drag browser.
                self.main.curr_img_idx = -1
                self.main.central_stack.setCurrentWidget(self.main.drag_browser)
                self.update_image_cards()
        if removed_any:
            self.main.mark_project_dirty()


    def handle_toggle_skip_images(self, file_names: list[str], skip_status: bool):
        """
        Handle toggling skip status for images
        
        Args:
            file_names: List of file names to update
            skip_status: If True, mark as skipped; if False, mark as not skipped
        """
        file_paths = []
        for name in file_names:
            path = next((p for p in self.main.image_files if os.path.basename(p) == name), None)
            if path:
                file_paths.append(path)

        if not file_paths:
            return

        changed = False
        for path in file_paths:
            if self.main.image_states.get(path, {}).get('skip', False) != skip_status:
                changed = True
                break
        if not changed:
            return

        command = ToggleSkipImagesCommand(self.main, file_paths, skip_status)
        stack = self.main.undo_group.activeStack()
        if stack:
            stack.push(command)
        else:
            command.redo()
            self.main.mark_project_dirty()

    def display_image_from_loaded(self, rgb_image, index: int, switch_page: bool = True):
        file_path = self.main.image_files[index]
        self.main.image_data[file_path] = rgb_image
        
        # Initialize history for new images
        if file_path not in self.main.image_history:
            self.main.image_history[file_path] = [file_path]
            self.main.in_memory_history[file_path] = [rgb_image.copy()]
            self.main.current_history_index[file_path] = 0

        self.display_image(index, switch_page)

        # Manage loaded images
        if file_path not in self.main.loaded_images:
            self.main.loaded_images.append(file_path)
            if len(self.main.loaded_images) > self.main.max_images_in_memory:
                oldest_image = self.main.loaded_images.pop(0)
                del self.main.image_data[oldest_image]
                self.main.in_memory_history[oldest_image] = []

                self.main.in_memory_patches.pop(oldest_image, None)

    def set_image(self, rgb_img: np.ndarray, push: bool = True):
        if self.main.curr_img_idx >= 0:
            file_path = self.main.image_files[self.main.curr_img_idx]
            
            # Push the command to the appropriate stack
            command = SetImageCommand(self.main, file_path, rgb_img)
            if push:
                self.main.undo_group.activeStack().push(command)
            else:
                command.redo()

    def load_patch_state(self, file_path: str):
        # for every patch in the persistent store:
        mem_list = self.main.in_memory_patches.setdefault(file_path, [])
        for saved in self.main.image_patches.get(file_path, []):
            match = next((m for m in mem_list if m['hash'] == saved['hash']), None)
            if match:
                prop = {
                    'bbox': saved['bbox'],
                    'image': match['image'],
                    'hash': saved['hash']
                }
            else:
                # load into memory
                rgb_img = imk.read_image(saved['png_path'])
                prop = {
                    'bbox': saved['bbox'],
                    'image': rgb_img,
                    'hash': saved['hash']
                }
                self.main.in_memory_patches[file_path].append(prop)
            
            # draw it
            if not PatchCommandBase.find_matching_item(self.main.image_viewer._scene, prop):   
                PatchCommandBase.create_patch_item(prop, self.main.image_viewer)

    def save_current_image(self, file_path: str):
        if self.main.webtoon_mode:
            # In webtoon mode, get the visible area image which combines all visible pages
            final_rgb, _ = self.main.image_viewer.get_visible_area_image(paint_all=True)
        else:
            # In regular mode, get the current single image
            final_rgb = self.main.image_viewer.get_image_array(paint_all=True)

        imk.write_image(file_path, final_rgb)

    def save_image_state(self, file: str):
        # For regular mode only
        skip_status = self.main.image_states.get(file, {}).get('skip', False)
        self.main.image_states[file] = {
            'viewer_state': self.main.image_viewer.save_state(),
            'source_lang': self.main.s_combo.currentText(),
            'target_lang': self.main.t_combo.currentText(),
            'brush_strokes': self.main.image_viewer.save_brush_strokes(),
            'blk_list': self.main.blk_list.copy(),  # Store a copy of the list, not a reference
            'skip': skip_status,
        }

    def save_current_image_state(self):
        if self.main.curr_img_idx >= 0:
            current_file = self.main.image_files[self.main.curr_img_idx]
            self.save_image_state(current_file)

    def load_image_state(self, file_path: str):
        rgb_image = self.main.image_data[file_path]

        self.set_image(rgb_image, push=False) 
        if file_path in self.main.image_states:
            state = self.main.image_states[file_path]
            
            # Skip state loading for newly inserted images (which have empty viewer_state)
            # This prevents loading of incomplete state or invalid transform data.
            # As soon as an image is saved once, it will have a populated viewer_state.
            if state.get('viewer_state'):
                
                push_to_stack = state.get('viewer_state', {}).get('push_to_stack', False)

                self.main.blk_list = state['blk_list'].copy()  # Load a copy of the list, not a reference
                self.main.image_viewer.load_state(state['viewer_state'])
                # Block signals to prevent triggering save when loading state
                self.main.s_combo.blockSignals(True)
                self.main.t_combo.blockSignals(True)
                self.main.s_combo.setCurrentText(state['source_lang'])
                self.main.t_combo.setCurrentText(state['target_lang'])
                self.main.s_combo.blockSignals(False)
                self.main.t_combo.blockSignals(False)
                self.main.image_viewer.load_brush_strokes(state['brush_strokes'])

                if push_to_stack:
                    self.main.undo_stacks[file_path].beginMacro('text_items_rendered')
                    for text_item in self.main.image_viewer.text_items:
                        self.main.text_ctrl.connect_text_item_signals(text_item)
                        command = AddTextItemCommand(self.main, text_item)
                        self.main.undo_stacks[file_path].push(command)
                    self.main.undo_stacks[file_path].endMacro()
                    state['viewer_state'].update({'push_to_stack': False})
                else:
                    for text_item in self.main.image_viewer.text_items:
                        self.main.text_ctrl.connect_text_item_signals(text_item)

                for rect_item in self.main.image_viewer.rectangles:
                    self.main.rect_item_ctrl.connect_rect_item_signals(rect_item)

                self.load_patch_state(file_path)
            else:
                # New image - just set language preferences and clear everything else
                self.main.blk_list = []
                # Block signals to prevent triggering save when loading state
                self.main.s_combo.blockSignals(True)
                self.main.t_combo.blockSignals(True)
                self.main.s_combo.setCurrentText(state.get('source_lang', self.main.s_combo.currentText()))
                self.main.t_combo.setCurrentText(state.get('target_lang', self.main.t_combo.currentText()))
                self.main.s_combo.blockSignals(False)
                self.main.t_combo.blockSignals(False)
                self.main.image_viewer.clear_rectangles(page_switch=True)
                self.main.image_viewer.clear_brush_strokes(page_switch=True)
                self.main.image_viewer.clear_text_items()

        self.main.text_ctrl.clear_text_edits()

    def display_image(self, index: int, switch_page: bool = True):
        if 0 <= index < len(self.main.image_files):
            if switch_page:
                self.save_current_image_state()
            self.main.curr_img_idx = index
            file_path = self.main.image_files[index]

            # Set the active stack for the current image
            file_path = self.main.image_files[index]
            if file_path in self.main.undo_stacks:
                self.main.undo_group.setActiveStack(self.main.undo_stacks[file_path])
            
            # Check if this image has been displayed before
            first_time_display = file_path not in self.main.displayed_images
            
            self.load_image_state(file_path)
            
            # Handle webtoon mode vs regular mode
            if self.main.webtoon_mode:
                # In webtoon mode, scroll to the specific page using the unified viewer
                self.main.image_viewer.scroll_to_page(index)
                self.main.central_stack.setCurrentWidget(self.main.image_viewer)
            else:
                # Regular mode - display single image
                self.main.central_stack.setCurrentWidget(self.main.image_viewer)
                
            self.main.central_stack.layout().activate()
            
            # Fit in view only if it's the first time displaying this image and not in webtoon mode
            if first_time_display and not self.main.webtoon_mode:
                self.main.image_viewer.fitInView()
                self.main.displayed_images.add(file_path)  # Mark this image as displayed

    def on_image_processed(self, index: int, image: np.ndarray, image_path: str):
        file_on_display = self.main.image_files[self.main.curr_img_idx]
        current_batch_file = self.main.selected_batch[index] if self.main.selected_batch else self.main.image_files[index]
        
        if current_batch_file == file_on_display:
            self.set_image(image)
        else:
            command = SetImageCommand(self.main, image_path, image, False)
            self.main.undo_stacks[current_batch_file].push(command)
            self.main.image_data[image_path] = image

    def on_image_skipped(self, image_path: str, skip_reason: str, error: str):
        message = { 
            "Text Blocks": QtCore.QCoreApplication.translate('Messages', 'No Text Blocks Detected.\nSkipping:') + f" {image_path}\n{error}", 
            "OCR": QtCore.QCoreApplication.translate('Messages', 'Could not OCR detected text.\nSkipping:') + f" {image_path}\n{error}",
            "Translator": QtCore.QCoreApplication.translate('Messages', 'Could not get translations.\nSkipping:') + f" {image_path}\n{error}"        
        }

        text = message.get(skip_reason, f"Unknown skip reason: {skip_reason}. Error: {error}")
        
        MMessage.info(
            text=text,
            parent=self.main,
            duration=5,
            closable=True
        )

    def on_inpaint_patches_processed(self, patches: list, file_path: str):
        target_stack = self.main.undo_stacks[file_path]

        # Check if this page is currently visible in webtoon mode
        should_display = False
        if self.main.webtoon_mode:
            # In webtoon mode, display patches for pages that are currently loaded/visible
            loaded_pages = self.main.image_viewer.webtoon_manager.loaded_pages
            page_index = None
            # Find the page index for this file path
            if file_path in self.main.image_files:
                page_index = self.main.image_files.index(file_path)
            if page_index is not None and page_index in loaded_pages:
                should_display = True
        else:
            # Regular mode - check if it's the current file
            file_on_display = self.main.image_files[self.main.curr_img_idx] if self.main.image_files else None
            should_display = (file_path == file_on_display)

        # Create the command for the specific page
        command = PatchInsertCommand(self.main, patches, file_path, display=should_display)
        target_stack.push(command)

    def apply_inpaint_patches(self, patches):
        command = PatchInsertCommand(self.main, patches, self.main.image_files[self.main.curr_img_idx])
        self.main.undo_group.activeStack().push(command)

    def cleanup(self):
        """Clean up resources, including the lazy loader."""
        if hasattr(self, 'page_list_loader'):
            self.page_list_loader.shutdown()
