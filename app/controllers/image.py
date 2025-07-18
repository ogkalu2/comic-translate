from __future__ import annotations

import os
import cv2
from PIL import Image
import numpy as np
from typing import TYPE_CHECKING, List
from PySide6 import QtCore, QtWidgets, QtGui

from app.ui.dayu_widgets.clickable_card import ClickMeta
from app.ui.dayu_widgets.message import MMessage
from app.ui.commands.image import SetImageCommand
from app.ui.commands.inpaint import PatchInsertCommand
from app.ui.commands.inpaint import PatchCommandBase
from app.ui.commands.box import AddTextItemCommand

if TYPE_CHECKING:
    from controller import ComicTranslate


class ImageStateController:
    def __init__(self, main: ComicTranslate):
        self.main = main

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
            cv2_image = cv2.imread(current_temp_path)
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
            
            if cv2_image is not None:
                return cv2_image

        # If not in memory and not in history (or failed to load from temp),
        # load from the original file path
        try:
            cv2_image = cv2.imread(file_path)
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
            return cv2_image
        except Exception as e:
            print(f"Error loading image {file_path}: {str(e)}")
            return None

    def clear_state(self):
        # Clear existing image data
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

        # Reset current_image_index
        self.main.curr_img_idx = -1

    def thread_load_images(self, paths: List[str]):
        if paths and paths[0].lower().endswith('.ctpr'):
            self.main.project_ctrl.thread_load_project(paths[0])
            return
        self.clear_state()
        self.main.run_threaded(self.load_initial_image, self.on_initial_image_loaded, self.main.default_error_handler, None, paths)

    def thread_insert(self, paths: List[str]):
        if self.main.image_files:
            def on_files_prepared(prepared_files):
                self.main.image_files.extend(prepared_files)
                path = prepared_files[0]
                new_index = self.main.image_files.index(path)
                self.update_image_cards()
                self.main.page_list.setCurrentRow(new_index)

            self.main.run_threaded(
                lambda: self.main.file_handler.prepare_files(paths, True),
                on_files_prepared,
                self.main.default_error_handler)
        else:
            self.thread_load_images(paths)

    def on_initial_image_loaded(self, cv2_image: np.ndarray):
        if cv2_image is not None:
            self.main.image_data[self.main.image_files[0]] = cv2_image
            self.main.image_history[self.main.image_files[0]] = [self.main.image_files[0]]
            self.main.in_memory_history[self.main.image_files[0]] = [cv2_image.copy()]
            self.main.current_history_index[self.main.image_files[0]] = 0
            self.save_image_state(self.main.image_files[0])

        for file in self.main.image_files:
            self.save_image_state(file)
            stack = QtGui.QUndoStack(self.main)
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
                #"avatar": MPixmap(file_path)
            })
            # re-apply strike-through if previously skipped
            if self.main.image_states.get(file_path, {}).get('skip'):
                card.set_skipped(True)
            self.main.page_list.addItem(list_item)
            self.main.page_list.setItemWidget(list_item, card)
            self.main.image_cards.append(card)

    def on_card_selected(self, current, previous):
        if current:  
            index = self.main.page_list.row(current)
            self.main.curr_tblock_item = None
            
            self.main.run_threaded(
                lambda: self.load_image(self.main.image_files[index]),
                lambda result: self.display_image_from_loaded(result, index),
                self.main.default_error_handler,
                lambda: self.highlight_card(index)
            )

    def navigate_images(self, direction: int):
        if self.main.image_files:
            new_index = self.main.curr_img_idx + direction
            if 0 <= new_index < len(self.main.image_files):
                item = self.main.page_list.item(new_index)
                self.main.page_list.setCurrentItem(item)

    def highlight_card(self, index: int):
        if 0 <= index < len(self.main.image_cards):
            # Remove highlight from the previously highlighted card
            if self.main.current_card:
                self.main.current_card.set_highlight(False)
            
            # Highlight the new card
            self.main.image_cards[index].set_highlight(True)
            self.main.current_card = self.main.image_cards[index]

    def handle_image_deletion(self, file_names: list[str]):
        """Handles the deletion of images based on the provided file names."""

        self.save_current_image_state()
        
        # Delete the files first.
        for file_name in file_names:
            # Find the full file path based on the file name
            file_path = next((f for f in self.main.image_files if os.path.basename(f) == file_name), None)
            
            if file_path:
                # Remove from the image_files list
                self.main.image_files.remove(file_path)
                
                # Remove associated data
                self.main.image_data.pop(file_path, None)
                self.main.image_history.pop(file_path, None)
                self.main.in_memory_history.pop(file_path, None)
                self.main.current_history_index.pop(file_path, None)

                if file_path in self.main.undo_stacks:
                    stack = self.main.undo_stacks[file_path]
                    self.main.undo_group.removeStack(stack)
                    self.main.undo_stacks.pop(file_path, None)
                    
                if file_path in self.main.displayed_images:
                    self.main.displayed_images.remove(file_path)
                    
                if file_path in self.main.loaded_images:
                    self.main.loaded_images.remove(file_path)

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


    def handle_toggle_skip_images(self, file_names: list[str], skip_status: bool):
        """
        Handle toggling skip status for images
        
        Args:
            file_names: List of file names to update
            skip_status: If True, mark as skipped; if False, mark as not skipped
        """
        for name in file_names:
            # find full path
            path = next((p for p in self.main.image_files if os.path.basename(p) == name), None)
            if not path:
                continue

            # update skip status in state dictionary
            self.main.image_states.get(path, {})['skip'] = skip_status

            # update item appearance
            idx = self.main.image_files.index(path)
            item = self.main.page_list.item(idx)
            fnt = item.font()
            fnt.setStrikeOut(skip_status)
            item.setFont(fnt)

            # update card 
            card = self.main.page_list.itemWidget(item)
            if card:
                card.set_skipped(skip_status)

    def display_image_from_loaded(self, cv2_image, index: int, switch_page: bool = True):
        file_path = self.main.image_files[index]
        self.main.image_data[file_path] = cv2_image
        
        # Initialize history for new images
        if file_path not in self.main.image_history:
            self.main.image_history[file_path] = [file_path]
            self.main.in_memory_history[file_path] = [cv2_image.copy()]
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

    def set_cv2_image(self, cv2_img: np.ndarray, push: bool = True):
        if self.main.curr_img_idx >= 0:
            file_path = self.main.image_files[self.main.curr_img_idx]
            
            # Push the command to the appropriate stack
            command = SetImageCommand(self.main, file_path, cv2_img)
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
                    'cv2_img': match['cv2_img'],
                    'hash': saved['hash']
                }
            else:
                # load into memory
                cv_img = cv2.imread(saved['png_path'])
                prop = {
                    'bbox':     saved['bbox'],
                    'cv2_img':  cv_img,
                    'hash':     saved['hash']
                }
                self.main.in_memory_patches[file_path].append(prop)
            
            # draw it
            if not PatchCommandBase.find_matching_item(self.main.image_viewer._scene, prop):   
                PatchCommandBase.create_patch_item(prop, self.main.image_viewer.photo)

    def save_current_image(self, file_path: str):
        final_bgr = self.main.image_viewer.get_cv2_image(paint_all=True)
        final_rgb = cv2.cvtColor(final_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(final_rgb)
        pil_img.save(file_path)

    def save_image_state(self, file: str):
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
        cv2_image = self.main.image_data[file_path]

        self.set_cv2_image(cv2_image, push=False)
        if file_path in self.main.image_states:
            state = self.main.image_states[file_path]
            push_to_stack = state.get('viewer_state', {}).get('push_to_stack', False)

            self.main.blk_list = state['blk_list']
            self.main.image_viewer.load_state(state['viewer_state'])
            self.main.s_combo.setCurrentText(state['source_lang'])
            self.main.t_combo.setCurrentText(state['target_lang'])
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
            self.main.central_stack.setCurrentWidget(self.main.image_viewer)
            self.main.central_stack.layout().activate()
            
            # Fit in view only if it's the first time displaying this image
            if first_time_display:
                self.main.image_viewer.fitInView()
                self.main.displayed_images.add(file_path)  # Mark this image as displayed

    def on_image_processed(self, index: int, image: np.ndarray, image_path: str):
        file_on_display = self.main.image_files[self.main.curr_img_idx]
        current_batch_file = self.main.selected_batch[index] if self.main.selected_batch else self.main.image_files[index]
        
        if current_batch_file == file_on_display:
            self.set_cv2_image(image)
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

    def on_inpaint_patches_processed(self, index: int, patches: list, image_path: str):
        file_on_display = self.main.image_files[self.main.curr_img_idx]
        current_batch_file = self.main.selected_batch[index] if self.main.selected_batch else self.main.image_files[index]

        if current_batch_file == file_on_display:
            self.apply_inpaint_patches(patches)
        else:
            command = PatchInsertCommand(self.main, patches, image_path, False)
            self.main.undo_stacks[current_batch_file].push(command)

    def apply_inpaint_patches(self, patches):
        command = PatchInsertCommand(self.main, patches, self.main.image_files[self.main.curr_img_idx])
        self.main.undo_group.activeStack().push(command)