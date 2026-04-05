from __future__ import annotations

import os
import imkit as imk
import numpy as np
import uuid
from typing import TYPE_CHECKING, List
from PySide6 import QtCore, QtWidgets, QtGui

from app.ui.dayu_widgets.clickable_card import ClickMeta
from app.ui.dayu_widgets.message import MMessage
from app.ui.messages import Messages
from app.ui.commands.image import SetImageCommand, ToggleSkipImagesCommand
from app.ui.commands.inpaint import PatchInsertCommand
from app.ui.commands.inpaint import PatchCommandBase
from app.ui.commands.box import AddTextItemCommand
from app.ui.list_view_image_loader import ListViewImageLoader
from app.thread_worker import GenericWorker
from app.path_materialization import ensure_path_materialized
from app.projects.project_state_v2 import remap_lazy_blob_paths

if TYPE_CHECKING:
    from controller import ComicTranslate


class ImageStateController:
    def __init__(self, main: ComicTranslate):
        self.main = main
        self._nav_request_id = 0
        self._nav_worker: GenericWorker | None = None
        self._original_nav_worker: GenericWorker | None = None
        self._page_skip_errors: dict[str, dict] = {}
        self._active_page_error_message: MMessage | None = None
        self._active_page_error_path: str | None = None
        self._suppress_dismiss_message_ids: set[int] = set()
        self._active_transient_skip_message: MMessage | None = None
        self._highlighted_card_indices: set[int] = set()
        self._original_image_cache: dict[str, np.ndarray] = {}
        self._original_loaded_images: list[str] = []
        self._max_original_images_in_memory = 5
        self._pending_text_stack_restore: set[str] = set()
        
        # Initialize lazy image loader for list view
        self.page_list_loader = ListViewImageLoader(
            self.main.page_list,
            avatar_size=(35, 50)
        )

    def _is_content_flagged_error(self, error: str) -> bool:
        lowered = (error or "").lower()
        return (
            "flagged as unsafe" in lowered
            or "content was flagged" in lowered
            or "safety filters" in lowered
        )

    def _resolve_skip_message_type(self, skip_reason: str, error: str) -> str:
        if self._is_content_flagged_error(error):
            return MMessage.ErrorType
        if skip_reason == "Text Blocks":
            return MMessage.InfoType
        return MMessage.WarningType

    def _summarize_skip_error(self, error: str) -> str:
        if not error:
            return ""
        # If the error is a short, custom message (like a translation), return it fully
        # instead of stripping everything after the first newline.
        if "Traceback" not in error and len(error) < 500:
            return error.strip()

        for raw_line in error.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("traceback"):
                break
            if line.startswith('File "') or line.startswith("File '"):
                continue
            if line.startswith("During handling of the above exception"):
                continue
            return line
        return ""

    def _build_skip_message(self, image_path: str, skip_reason: str, error: str) -> str:
        file_name = os.path.basename(image_path)
        reason = self._summarize_skip_error(error)
        t = QtCore.QCoreApplication.translate

        message_map = {
            "Text Blocks": t("Messages", "No Text Blocks Detected.\nSkipping:"),
            "OCR": t("Messages", "Could not recognize detected text.\nSkipping:"),
            "Translator": t("Messages", "Could not get translations.\nSkipping:"),
            "OCR Chunk Failed": t("Messages", "Could not recognize webtoon chunk.\nSkipping:"),
            "Translation Chunk Failed": t("Messages", "Could not translate webtoon chunk.\nSkipping:"),
        }

        base = message_map.get(
            skip_reason,
            t("Messages", "Page processing failed.\nSkipping:")
        )
        text = f"{base} {file_name}"
        if reason:
            text += f"\n{reason}"
        return text

    def _close_transient_skip_notice(self):
        msg = self._active_transient_skip_message
        if msg is None:
            return
        try:
            msg.close()
        except Exception:
            pass
        self._active_transient_skip_message = None

    def _show_transient_skip_notice(self, text: str, dayu_type: str):
        self._close_transient_skip_notice()
        show_func = {
            MMessage.InfoType: MMessage.info,
            MMessage.WarningType: MMessage.warning,
            MMessage.ErrorType: MMessage.error,
        }.get(dayu_type, MMessage.warning)
        self._active_transient_skip_message = show_func(
            text=text,
            parent=self.main,
            duration=6,
            closable=True,
        )

    def _hide_active_page_skip_error(self):
        msg = self._active_page_error_message
        if msg is None:
            self._active_page_error_path = None
            return
        self._suppress_dismiss_message_ids.add(id(msg))
        try:
            msg.close()
        except Exception:
            pass
        self._active_page_error_message = None
        self._active_page_error_path = None

    def _on_page_error_closed(self, file_path: str, message: MMessage):
        msg_id = id(message)
        if msg_id in self._suppress_dismiss_message_ids:
            self._suppress_dismiss_message_ids.discard(msg_id)
        else:
            state = self._page_skip_errors.get(file_path)
            if state:
                state["dismissed"] = True
        if self._active_page_error_message is message:
            self._active_page_error_message = None
            self._active_page_error_path = None

    def _show_page_skip_error_for_file(self, file_path: str):
        state = self._page_skip_errors.get(file_path)
        if not state or state.get("dismissed"):
            return
        if (
            self._active_page_error_path == file_path
            and self._active_page_error_message is not None
            and self._active_page_error_message.isVisible()
        ):
            return

        self._hide_active_page_skip_error()
        show_func = {
            MMessage.InfoType: MMessage.info,
            MMessage.WarningType: MMessage.warning,
            MMessage.ErrorType: MMessage.error,
        }.get(state.get("dayu_type"), MMessage.warning)
        message = show_func(
            text=state.get("text", ""),
            parent=self.main,
            duration=None,
            closable=True,
        )
        message.sig_closed.connect(
            lambda fp=file_path, msg=message: self._on_page_error_closed(fp, msg)
        )
        self._active_page_error_message = message
        self._active_page_error_path = file_path

    def handle_webtoon_page_focus(self, file_path: str, explicit_navigation: bool):
        """Apply page-skip popup policy for webtoon navigation.

        explicit_navigation=True means deliberate jump (page list/report),
        False means passive scroll-driven page change.
        """
        if explicit_navigation:
            self._show_page_skip_error_for_file(file_path)
        else:
            self._hide_active_page_skip_error()

    def _clear_page_skip_error(self, file_path: str):
        self._page_skip_errors.pop(file_path, None)
        if self._active_page_error_path == file_path:
            self._hide_active_page_skip_error()

    def clear_page_skip_errors_for_paths(self, file_paths: List[str]):
        for file_path in file_paths:
            self._clear_page_skip_error(file_path)

    def _current_file_path(self) -> str | None:
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            return self.main.image_files[self.main.curr_img_idx]
        return None

    def load_initial_image(self, file_paths: List[str]):
        file_paths = self.main.file_handler.prepare_files(file_paths)
        self.main.image_files = file_paths

        if file_paths:
            return self.load_image(file_paths[0])
        return None

    def load_image(self, file_path: str) -> np.ndarray:
        if file_path in self.main.image_data and self.main.image_data[file_path] is not None:
            return self.main.image_data[file_path]

        # Check if the image has been displayed before
        if file_path in self.main.image_history:
            # Get the current index from the history
            current_index = self.main.current_history_index[file_path]
            
            # Get the temp file path at the current index
            current_temp_path = self.main.image_history[file_path][current_index]
            ensure_path_materialized(current_temp_path)
            
            # Load the image from the temp file
            rgb_image = imk.read_image(current_temp_path)
            
            if rgb_image is not None:
                return rgb_image

        # If not in memory and not in history (or failed to load from temp),
        # load from the original file path
        ensure_path_materialized(file_path)
        rgb_image = imk.read_image(file_path)
        return rgb_image

    def load_original_image(self, file_path: str) -> np.ndarray:
        cached_image = self._get_cached_original_image(file_path)
        if cached_image is not None:
            return cached_image

        ensure_path_materialized(file_path)
        rgb_image = imk.read_image(file_path)
        if rgb_image is None:
            return None

        self._original_image_cache[file_path] = rgb_image
        if file_path in self._original_loaded_images:
            self._original_loaded_images.remove(file_path)
        self._original_loaded_images.append(file_path)

        while len(self._original_loaded_images) > self._max_original_images_in_memory:
            oldest_image = self._original_loaded_images.pop(0)
            self._original_image_cache.pop(oldest_image, None)

        return rgb_image

    def _get_cached_original_image(self, file_path: str) -> np.ndarray | None:
        cached_image = self._original_image_cache.get(file_path)
        if cached_image is None:
            return None
        if file_path in self._original_loaded_images:
            self._original_loaded_images.remove(file_path)
        self._original_loaded_images.append(file_path)
        return cached_image

    def _ordered_selected_page_paths(self) -> list[str]:
        selected_paths = set(self.main.get_selected_page_paths())
        if not selected_paths:
            current_path = self._current_file_path()
            return [current_path] if current_path else []
        return [
            file_path for file_path in self.main.image_files
            if file_path in selected_paths
        ]

    def _show_page_for_undo_redo(self, file_path: str, refresh_original_preview: bool) -> bool:
        try:
            index = self.main.image_files.index(file_path)
        except ValueError:
            return False

        image = self.load_image(file_path)
        self.display_image_from_loaded(
            image,
            index,
            switch_page=False,
            refresh_original_preview=refresh_original_preview,
        )
        return True

    def mark_text_stack_restore_pending(self):
        self._pending_text_stack_restore = {
            file_path
            for file_path, state in self.main.image_states.items()
            if (state.get("viewer_state", {}) or {}).get("text_items_state")
        }

    def _restore_text_items_to_stack_if_needed(self, file_path: str, viewer) -> None:
        if file_path not in self._pending_text_stack_restore:
            return

        stack = self.main.undo_stacks.get(file_path)
        if stack is None:
            self._pending_text_stack_restore.discard(file_path)
            return

        viewer_state = self.main.image_states.get(file_path, {}).get("viewer_state", {})
        if not viewer_state or not viewer_state.get("text_items_state") or not viewer.text_items:
            self._pending_text_stack_restore.discard(file_path)
            return

        was_project_clean = not self.main.has_unsaved_changes()
        stack.beginMacro('text_items_restored')
        for text_item in viewer.text_items:
            command = AddTextItemCommand(self.main, text_item)
            stack.push(command)
        stack.endMacro()
        if was_project_clean:
            self.main.set_project_clean()
        self._pending_text_stack_restore.discard(file_path)

    def apply_undo_redo_to_selected(self, redo: bool) -> None:
        ordered_paths = self._ordered_selected_page_paths()
        if not ordered_paths:
            return

        current_path = self._current_file_path()
        try:
            self.main.text_ctrl._commit_pending_text_command()
        except Exception:
            pass

        if current_path:
            self.save_current_image_state()

        operation = "redo" if redo else "undo"
        can_apply = "canRedo" if redo else "canUndo"
        processed_any = False

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for file_path in ordered_paths:
                stack = self.main.undo_stacks.get(file_path)
                if stack is None:
                    continue
                needs_text_restore = (not redo) and (file_path in self._pending_text_stack_restore)
                if needs_text_restore:
                    if not self._show_page_for_undo_redo(
                        file_path,
                        refresh_original_preview=False,
                    ):
                        continue
                    self.main.undo_group.setActiveStack(stack)
                if not getattr(stack, can_apply)():
                    continue
                if not needs_text_restore:
                    if not self._show_page_for_undo_redo(
                        file_path,
                        refresh_original_preview=False,
                    ):
                        continue

                self.main.undo_group.setActiveStack(stack)
                getattr(stack, operation)()
                self.save_current_image_state()
                processed_any = True
        finally:
            restore_path = current_path if current_path in self.main.image_files else None
            if restore_path is None and ordered_paths:
                for file_path in ordered_paths:
                    if file_path in self.main.image_files:
                        restore_path = file_path
                        break

            if restore_path:
                self._show_page_for_undo_redo(restore_path, refresh_original_preview=True)
                restore_stack = self.main.undo_stacks.get(restore_path)
                if restore_stack is not None:
                    self.main.undo_group.setActiveStack(restore_stack)

            QtWidgets.QApplication.restoreOverrideCursor()

        if processed_any:
            self.main.refresh_fullscreen_preview()
            self.main.update_page_position_label()

    @staticmethod
    def _remap_dict_keys(data: dict, path_mapping: dict[str, str]) -> dict:
        return {
            path_mapping.get(key, key): value
            for key, value in data.items()
        }

    def _remap_state_after_archive_renumber(self, path_mapping: dict[str, str]) -> None:
        if not path_mapping:
            return

        self.main.image_files = [
            path_mapping.get(path, path) for path in self.main.image_files
        ]
        self.main.file_handler.file_paths = self.main.image_files.copy()
        self.main.image_data = self._remap_dict_keys(self.main.image_data, path_mapping)
        self.main.current_history_index = self._remap_dict_keys(
            self.main.current_history_index,
            path_mapping,
        )
        self.main.image_states = self._remap_dict_keys(self.main.image_states, path_mapping)
        self.main.image_patches = self._remap_dict_keys(self.main.image_patches, path_mapping)
        self.main.in_memory_patches = self._remap_dict_keys(
            self.main.in_memory_patches,
            path_mapping,
        )
        self.main.undo_stacks = self._remap_dict_keys(self.main.undo_stacks, path_mapping)
        self._page_skip_errors = self._remap_dict_keys(self._page_skip_errors, path_mapping)
        self._original_image_cache = self._remap_dict_keys(
            self._original_image_cache,
            path_mapping,
        )
        self._pending_text_stack_restore = {
            path_mapping.get(path, path) for path in self._pending_text_stack_restore
        }

        remapped_history = {}
        for key, history in self.main.image_history.items():
            new_key = path_mapping.get(key, key)
            remapped_history[new_key] = [
                path_mapping.get(path, path) for path in history
            ]
        self.main.image_history = remapped_history

        self.main.in_memory_history = self._remap_dict_keys(
            self.main.in_memory_history,
            path_mapping,
        )
        self.main.displayed_images = {
            path_mapping.get(path, path) for path in self.main.displayed_images
        }
        self.main.loaded_images = [
            path_mapping.get(path, path) for path in self.main.loaded_images
        ]
        self._original_loaded_images = [
            path_mapping.get(path, path) for path in self._original_loaded_images
        ]

        if self._active_page_error_path in path_mapping:
            self._active_page_error_path = path_mapping[self._active_page_error_path]

    def _apply_temp_path_renames(self, rename_pairs: list[tuple[str, str]]) -> None:
        if not rename_pairs:
            return

        temp_pairs: list[tuple[str | None, str]] = []
        for old_path, new_path in rename_pairs:
            temp_path = None
            if os.path.exists(old_path):
                temp_path = os.path.join(
                    os.path.dirname(old_path),
                    f".ct_renumber_{uuid.uuid4().hex}{os.path.splitext(new_path)[1]}",
                )
                os.replace(old_path, temp_path)
            temp_pairs.append((temp_path, new_path))

        for temp_path, new_path in temp_pairs:
            if temp_path and os.path.exists(temp_path):
                os.replace(temp_path, new_path)

    def _renumber_project_loaded_pages(self, remaining_paths: list[str]) -> dict[str, str]:
        temp_root = getattr(self.main, "temp_dir", "")
        if not temp_root:
            return {}

        unique_images_root = os.path.abspath(os.path.join(temp_root, "unique_images"))
        if not os.path.isdir(unique_images_root):
            return {}

        candidate_paths = [
            path for path in remaining_paths
            if os.path.abspath(path).startswith(unique_images_root + os.sep)
        ]
        if not candidate_paths:
            return {}

        digit_width = 1
        for path in candidate_paths:
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem.isdigit():
                digit_width = max(digit_width, len(stem))

        path_mapping: dict[str, str] = {}
        rename_pairs: list[tuple[str, str]] = []

        for index, old_path in enumerate(candidate_paths, start=1):
            ext = os.path.splitext(old_path)[1].lower() or ".png"
            new_path = os.path.join(
                os.path.dirname(old_path),
                f"{index:0{digit_width}d}{ext}",
            )
            if old_path == new_path:
                continue
            path_mapping[old_path] = new_path
            rename_pairs.append((old_path, new_path))

        self._apply_temp_path_renames(rename_pairs)
        remap_lazy_blob_paths(path_mapping)
        return path_mapping



    def clear_state(self):
        # Clear existing image data
        self.main.setWindowTitle("Project1.ctpr[*]")
        self._close_transient_skip_notice()
        self._hide_active_page_skip_error()
        self._page_skip_errors.clear()
        self._suppress_dismiss_message_ids.clear()
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
        self.main.original_image_viewer.clear_scene()
        self.main.fullscreen_preview.close()
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
        self._highlighted_card_indices.clear()
        self._original_image_cache.clear()
        self._original_loaded_images.clear()
        self._pending_text_stack_restore.clear()
        try:
            if hasattr(self.main, "batch_report_ctrl") and self.main.batch_report_ctrl is not None:
                self.main.batch_report_ctrl.reset()
        except Exception:
            pass

        # Reset current_image_index
        self.main.curr_img_idx = -1
        self.main.update_page_position_label()
        self.main.set_project_clean()

    def thread_load_images(self, paths: List[str]):
        if paths and paths[0].lower().endswith('.ctpr'):
            self.main.project_ctrl.thread_load_project(paths[0])
            return

        # If autosave is active and a project file is already chosen, preserve
        # the association so the title and autosave target survive the state reset.
        try:
            autosave_enabled = bool(
                hasattr(self.main, 'title_bar')
                and self.main.title_bar.autosave_switch.isChecked()
            )
        except Exception:
            autosave_enabled = False
        prev_project_file = self.main.project_file if autosave_enabled else None

        self.main.project_ctrl.clear_recovery_checkpoint()
        self.clear_state()
        if prev_project_file:
            self.main.project_file = prev_project_file
            self.main.setWindowTitle(f"{os.path.basename(prev_project_file)}[*]")
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
                    stack.indexChanged.connect(self.main._bump_dirty_revision)
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
            stack.indexChanged.connect(self.main._bump_dirty_revision)
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
            self.main.update_page_position_label()

        self.main.image_viewer.resetTransform()
        self.main.image_viewer.fitInView()
        if self.main.image_files:
            self.main.refresh_original_preview(
                self.main.image_files[0],
                original_image=self.load_original_image(self.main.image_files[0]),
            )
        if self.main.image_files:
            self.main.mark_project_dirty()

    def update_image_cards(self):
        # Clear existing items
        self.main.page_list.clear()
        self.main.image_cards.clear()
        self.main.current_card = None
        self._highlighted_card_indices.clear()

        # Add new items
        for index, file_path in enumerate(self.main.image_files):
            file_name = os.path.basename(file_path)
            list_item = QtWidgets.QListWidgetItem(file_name)
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, file_path)
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

    def _resolve_reordered_paths(self, ordered_items: list[str]) -> list[str] | None:
        current_files = self.main.image_files
        if len(ordered_items) != len(current_files):
            return None

        current_set = set(current_files)
        name_to_paths: dict[str, list[str]] = {}
        for path in current_files:
            name_to_paths.setdefault(os.path.basename(path), []).append(path)

        resolved: list[str] = []
        used: set[str] = set()

        for token in ordered_items:
            chosen = None

            if token in current_set and token not in used:
                chosen = token
            else:
                candidates = name_to_paths.get(token, [])
                while candidates and candidates[0] in used:
                    candidates.pop(0)
                if candidates:
                    chosen = candidates.pop(0)

            if not chosen:
                return None

            used.add(chosen)
            resolved.append(chosen)

            chosen_name = os.path.basename(chosen)
            remaining = name_to_paths.get(chosen_name, [])
            if chosen in remaining:
                remaining.remove(chosen)

        if set(resolved) != current_set:
            return None
        return resolved

    def handle_image_reorder(self, ordered_items: list[str]):
        if not self.main.image_files:
            return

        new_order = self._resolve_reordered_paths(ordered_items)
        if not new_order or new_order == self.main.image_files:
            return

        current_file = self._current_file_path()
        if current_file:
            self.save_current_image_state()

        self.main.image_files = new_order

        if current_file in self.main.image_files:
            self.main.curr_img_idx = self.main.image_files.index(current_file)
        elif self.main.image_files:
            self.main.curr_img_idx = 0
        else:
            self.main.curr_img_idx = -1

        if self.main.webtoon_mode and hasattr(self.main.image_viewer, "webtoon_manager"):
            manager = self.main.image_viewer.webtoon_manager
            try:
                manager.scene_item_manager.save_all_scene_items_to_states()
            except Exception:
                pass
            current_page = max(0, self.main.curr_img_idx)
            manager.load_images_lazy(self.main.image_files, current_page)

        self.main.page_list.blockSignals(True)
        self.update_image_cards()
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            self.main.page_list.setCurrentRow(self.main.curr_img_idx)
            self.highlight_card(self.main.curr_img_idx)
            self.page_list_loader.force_load_image(self.main.curr_img_idx)
            current_path = self.main.image_files[self.main.curr_img_idx]
            if current_path in self.main.undo_stacks:
                self.main.undo_group.setActiveStack(self.main.undo_stacks[current_path])
        self.main.page_list.blockSignals(False)

        self.main.mark_project_dirty()

    def on_card_selected(self, current, previous):
        if not current:
            self._hide_active_page_skip_error()
            return

        file_path = current.data(QtCore.Qt.ItemDataRole.UserRole)
        index = self.main.page_list.row(current)
        if not (0 <= index < len(self.main.image_files)):
            self._hide_active_page_skip_error()
            return
        if not isinstance(file_path, str) or self.main.image_files[index] != file_path:
            file_path = self.main.image_files[index]
        self.main.curr_tblock_item = None
        # Force load the selected image thumbnail
        self.page_list_loader.force_load_image(index)
        self._hide_active_page_skip_error()

        # Avoid circular calls when in webtoon mode
        if getattr(self.main, '_processing_page_change', False):
            self._show_page_skip_error_for_file(file_path)
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
                self._run_async_nav_load(index)
        else:
            # Regular mode - load and display the image
            self._run_async_nav_load(index)

        self._show_page_skip_error_for_file(file_path)

    def navigate_images(self, direction: int):
        if self.main.image_files:
            new_index = self.main.curr_img_idx + direction
            if 0 <= new_index < len(self.main.image_files):
                item = self.main.page_list.item(new_index)
                self.main.page_list.setCurrentItem(item)

    def _run_async_nav_load(self, index: int):
        """Load a selected image asynchronously without entering the batch queue.

        This keeps page switching responsive while batch processing is ongoing.
        """
        if not (0 <= index < len(self.main.image_files)):
            return

        self._nav_request_id += 1
        req_id = self._nav_request_id
        file_path = self.main.image_files[index]

        def _bg_load():
            img = self.load_image(file_path)
            original = self._get_cached_original_image(file_path)
            # Preload inpaint patches into memory so that load_patch_state
            # doesn't hit disk on the main thread.
            if req_id == self._nav_request_id:
                self._preload_patches(file_path, request_id=req_id)
            return img, original

        worker = GenericWorker(_bg_load)

        def _on_result(result):
            # Ignore stale loads when user switched pages rapidly.
            if req_id != self._nav_request_id:
                return
            edited_image, original_image = result
            self.display_image_from_loaded(
                edited_image,
                index,
                original_image=original_image,
                refresh_original_preview=original_image is not None,
            )
            if original_image is None:
                self._run_async_original_preview_load(index, req_id)

        worker.signals.result.connect(
            lambda result: QtCore.QTimer.singleShot(0, lambda: _on_result(result))
        )
        worker.signals.error.connect(
            lambda error: QtCore.QTimer.singleShot(0, lambda: self.main.default_error_handler(error))
        )
        self._nav_worker = worker
        self.main.threadpool.start(worker)

    def _run_async_original_preview_load(self, index: int, req_id: int):
        if not (0 <= index < len(self.main.image_files)):
            return

        file_path = self.main.image_files[index]

        def _bg_load_original():
            return self.load_original_image(file_path)

        worker = GenericWorker(_bg_load_original)

        def _on_result(original_image):
            if req_id != self._nav_request_id:
                return
            current_file = self._current_file_path()
            if current_file != file_path:
                return
            self.main.refresh_original_preview(file_path, original_image=original_image)

        worker.signals.result.connect(
            lambda result: QtCore.QTimer.singleShot(0, lambda: _on_result(result))
        )
        worker.signals.error.connect(
            lambda error: QtCore.QTimer.singleShot(0, lambda: self.main.default_error_handler(error))
        )
        self._original_nav_worker = worker
        self.main.threadpool.start(worker)

    def _preload_patches(self, file_path: str, request_id: int | None = None):
        """Read patch images from disk into in_memory_patches on a worker thread.

        This prevents load_patch_state from blocking the main thread with
        synchronous disk reads when the user switches pages.
        """
        saved_patches = self.main.image_patches.get(file_path)
        if not saved_patches:
            return
        mem_list = self.main.in_memory_patches.get(file_path, [])
        mem_hashes = {m['hash'] for m in mem_list}
        loaded = []
        for saved in saved_patches:
            # Stop stale preload work when user already switched to another page.
            if request_id is not None and request_id != self._nav_request_id:
                return
            if saved['hash'] not in mem_hashes:
                ensure_path_materialized(saved['png_path'])
                rgb_img = imk.read_image(saved['png_path'])
                if rgb_img is not None:
                    loaded.append({
                        'bbox': saved['bbox'],
                        'image': rgb_img,
                        'hash': saved['hash'],
                    })
        if loaded:
            self.main.in_memory_patches.setdefault(file_path, []).extend(loaded)

    def highlight_card(self, index: int):
        """Highlight a single card (used for programmatic selection when signals are blocked)."""
        highlighted = {index} if 0 <= index < len(self.main.image_cards) else set()
        self._set_highlighted_cards(highlighted, current_index=index if highlighted else None)

    def on_selection_changed(self, selected_indices: list):
        """Handle selection changes and update visual highlighting for all selected cards."""
        highlighted = {
            index for index in selected_indices if 0 <= index < len(self.main.image_cards)
        }
        current_index = selected_indices[-1] if selected_indices else None
        self._set_highlighted_cards(highlighted, current_index=current_index)

    def _set_highlighted_cards(
        self,
        highlighted_indices: set[int],
        current_index: int | None = None,
    ):
        removed = self._highlighted_card_indices - highlighted_indices
        added = highlighted_indices - self._highlighted_card_indices

        for index in removed:
            if 0 <= index < len(self.main.image_cards):
                self.main.image_cards[index].set_highlight(False)

        for index in added:
            if 0 <= index < len(self.main.image_cards):
                self.main.image_cards[index].set_highlight(True)

        self._highlighted_card_indices = highlighted_indices

        if current_index is not None and 0 <= current_index < len(self.main.image_cards):
            self.main.current_card = self.main.image_cards[current_index]
        else:
            self.main.current_card = None

    def handle_image_deletion(self, file_names: list[str]):
        """Handles the deletion of images based on the provided file names."""

        original_paths = list(self.main.image_files)
        original_current_path = self._current_file_path()
        original_current_index = self.main.curr_img_idx
        self.save_current_image_state()
        removed_any = False
        deleted_webtoon_paths: list[str] = []
        deleted_paths: list[str] = []

        def resolve_path(ref: str) -> str | None:
            if ref in self.main.image_files:
                return ref
            return next((f for f in self.main.image_files if os.path.basename(f) == ref), None)
        
        # Delete the files first.
        for file_name in file_names:
            file_path = resolve_path(file_name)
            
            if file_path:
                deleted_paths.append(file_path)
                # Remove from the image_files list
                self.main.image_files.remove(file_path)
                removed_any = True
                self._clear_page_skip_error(file_path)
                
                # Remove associated data
                self.main.image_data.pop(file_path, None)
                self.main.image_history.pop(file_path, None)
                self.main.in_memory_history.pop(file_path, None)
                self.main.current_history_index.pop(file_path, None)
                self.main.image_states.pop(file_path, None)  
                self.main.image_patches.pop(file_path, None)  
                self.main.in_memory_patches.pop(file_path, None)  
                self._original_image_cache.pop(file_path, None)
                if file_path in self._original_loaded_images:
                    self._original_loaded_images.remove(file_path)

                if file_path in self.main.undo_stacks:
                    stack = self.main.undo_stacks[file_path]
                    self.main.undo_group.removeStack(stack)
                
                # Remove from other collections
                self.main.undo_stacks.pop(file_path, None)
                    
                if file_path in self.main.displayed_images:
                    self.main.displayed_images.remove(file_path)
                    
                if file_path in self.main.loaded_images:
                    self.main.loaded_images.remove(file_path)

        if self.main.webtoon_mode and self.main.image_files:
            webtoon_file_paths = self.main.image_viewer.webtoon_manager.image_loader.image_file_paths
            for file_name in file_names:
                resolved = resolve_path(file_name)
                matching_paths = [resolved] if resolved and resolved in webtoon_file_paths else []
                if not matching_paths:
                    matching_paths = [
                        fp for fp in webtoon_file_paths if os.path.basename(fp) == file_name
                    ]
                deleted_webtoon_paths.extend(matching_paths)

        path_mapping = {}
        if removed_any:
            path_mapping.update(
                self.main.file_handler.renumber_archive_pages(self.main.image_files)
            )
            path_mapping.update(
                self._renumber_project_loaded_pages(self.main.image_files)
            )
        self._remap_state_after_archive_renumber(path_mapping)

        target_path = None
        if self.main.image_files:
            if original_current_path and original_current_path not in deleted_paths:
                target_path = path_mapping.get(original_current_path, original_current_path)
            elif original_paths:
                if original_current_index >= 0:
                    candidates = [
                        path for idx, path in enumerate(original_paths)
                        if path not in deleted_paths and idx >= original_current_index
                    ]
                    if candidates:
                        target_path = path_mapping.get(candidates[0], candidates[0])
                    else:
                        remaining_before = [
                            path for idx, path in enumerate(original_paths)
                            if path not in deleted_paths and idx < original_current_index
                        ]
                        if remaining_before:
                            target_path = path_mapping.get(remaining_before[-1], remaining_before[-1])
                if target_path is None:
                    target_path = path_mapping.get(self.main.image_files[0], self.main.image_files[0])

        # Handle webtoon mode specific updates
        if self.main.webtoon_mode:
            # Use non-destructive page removal in webtoon mode
            if self.main.image_files:
                if target_path in self.main.image_files:
                    self.main.curr_img_idx = self.main.image_files.index(target_path)
                # Remove pages non-destructively from webtoon manager
                success = self.main.image_viewer.webtoon_manager.remove_pages(deleted_webtoon_paths)
                
                if success:
                    self.main.image_viewer.webtoon_manager.image_loader.image_file_paths = (
                        self.main.image_files.copy()
                    )
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
                    if target_path in self.main.image_files:
                        self.main.curr_img_idx = self.main.image_files.index(target_path)
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
                try:
                    self.main.show_home_screen()
                except Exception:
                    pass
                self.update_image_cards()
        else:
            # Handle normal mode
            if self.main.image_files:
                if target_path in self.main.image_files:
                    new_index = self.main.image_files.index(target_path)
                else:
                    if self.main.curr_img_idx >= len(self.main.image_files):
                        self.main.curr_img_idx = len(self.main.image_files) - 1
                    new_index = max(0, self.main.curr_img_idx)
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
                try:
                    self.main.show_home_screen()
                except Exception:
                    pass
                self.update_image_cards()

        # If the project has been emptied via deletion, drop stale crash recovery data.
        if not self.main.image_files:
            self.main.project_ctrl.clear_recovery_checkpoint()

        if removed_any:
            self.main.mark_project_dirty()


    def handle_toggle_skip_images(self, file_names: list[str], skip_status: bool):
        """
        Handle toggling skip status for images
        
        Args:
            file_names: List of file names to update
            skip_status: If True, mark as skipped; if False, mark as not skipped
        """
        file_paths: list[str] = []
        seen: set[str] = set()
        for name in file_names:
            path = name if name in self.main.image_files else None
            if path is None:
                path = next((p for p in self.main.image_files if os.path.basename(p) == name), None)
            if path and path not in seen:
                file_paths.append(path)
                seen.add(path)

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

    def display_image_from_loaded(
        self,
        rgb_image,
        index: int,
        switch_page: bool = True,
        original_image=None,
        refresh_original_preview: bool = True,
    ):
        file_path = self.main.image_files[index]
        self.main.image_data[file_path] = rgb_image
        
        # Initialize history for new images
        if file_path not in self.main.image_history:
            self.main.image_history[file_path] = [file_path]
            self.main.in_memory_history[file_path] = [rgb_image.copy()]
            self.main.current_history_index[file_path] = 0

        self.display_image(
            index,
            switch_page,
            original_image=original_image,
            refresh_original_preview=refresh_original_preview,
        )

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
        mem_by_hash = {patch['hash']: patch for patch in mem_list}
        scene_hashes = {
            item.data(PatchCommandBase.HASH_KEY)
            for item in self.main.image_viewer._scene.items()
            if item.data(PatchCommandBase.HASH_KEY) is not None
        }
        for saved in self.main.image_patches.get(file_path, []):
            patch_hash = saved['hash']
            match = mem_by_hash.get(patch_hash)
            if match is None:
                # load into memory
                ensure_path_materialized(saved['png_path'])
                rgb_img = imk.read_image(saved['png_path'])
                match = {
                    'bbox': saved['bbox'],
                    'image': rgb_img,
                    'hash': patch_hash,
                }
                mem_list.append(match)
                mem_by_hash[patch_hash] = match

            if patch_hash in scene_hashes:
                continue

            prop = {
                'bbox': saved['bbox'],
                'image': match['image'],
                'hash': patch_hash,
            }
            if 'scene_pos' in saved:
                prop['scene_pos'] = saved['scene_pos']
            if 'page_index' in saved:
                prop['page_index'] = saved['page_index']

            if PatchCommandBase.create_patch_item(prop, self.main.image_viewer) is not None:
                scene_hashes.add(patch_hash)

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
        viewer = self.main.image_viewer

        # Avoid repeated repaints while restoring many items during page switches.
        viewer.setUpdatesEnabled(False)
        viewer.set_view_state_notifications_enabled(False)
        try:
            # Display the image directly instead of going through SetImageCommand.
            # Page switching doesn't modify the image, so we skip the
            # update_image_history overhead (load_image + np.array_equal + potential
            # temp-file write that runs in SetImageCommand.__init__).
            # Always skip fitInView here: for revisited pages load_state restores
            # the saved transform, and for first-time pages display_image calls
            # fitInView after this method returns.
            viewer.display_image_array(rgb_image, fit=False)

            if file_path in self.main.image_states:
                state = self.main.image_states[file_path]

                # Skip state loading for newly inserted images (which have empty viewer_state)
                # This prevents loading of incomplete state or invalid transform data.
                # As soon as an image is saved once, it will have a populated viewer_state.
                if state.get('viewer_state'):

                    push_to_stack = state.get('viewer_state', {}).get('push_to_stack', False)
                    restore_to_stack = file_path in self._pending_text_stack_restore

                    self.main.blk_list = state['blk_list'].copy()  # Load a copy of the list, not a reference
                    viewer.load_state(state['viewer_state'])
                    # Block signals to prevent triggering save when loading state
                    self.main.s_combo.blockSignals(True)
                    self.main.t_combo.blockSignals(True)
                    if self.main.s_combo.currentText() != state['source_lang']:
                        self.main.s_combo.setCurrentText(state['source_lang'])
                    if self.main.t_combo.currentText() != state['target_lang']:
                        self.main.t_combo.setCurrentText(state['target_lang'])
                    self.main.s_combo.blockSignals(False)
                    self.main.t_combo.blockSignals(False)
                    viewer.load_brush_strokes(state['brush_strokes'])

                    # add_text_item/add_rectangle used by load_state already emit the
                    # viewer's connect_* signals, so no extra signal wiring is needed here.
                    if push_to_stack:
                        self.main.undo_stacks[file_path].beginMacro('text_items_rendered')
                        for text_item in viewer.text_items:
                            command = AddTextItemCommand(self.main, text_item)
                            self.main.undo_stacks[file_path].push(command)
                        self.main.undo_stacks[file_path].endMacro()
                        state['viewer_state'].update({'push_to_stack': False})
                    elif restore_to_stack:
                        self._restore_text_items_to_stack_if_needed(file_path, viewer)

                    self.load_patch_state(file_path)
                else:
                    # New image - just set language preferences and clear everything else
                    self.main.blk_list = []
                    # Block signals to prevent triggering save when loading state
                    self.main.s_combo.blockSignals(True)
                    self.main.t_combo.blockSignals(True)
                    source_lang = state.get('source_lang', self.main.s_combo.currentText())
                    target_lang = state.get('target_lang', self.main.t_combo.currentText())
                    if self.main.s_combo.currentText() != source_lang:
                        self.main.s_combo.setCurrentText(source_lang)
                    if self.main.t_combo.currentText() != target_lang:
                        self.main.t_combo.setCurrentText(target_lang)
                    self.main.s_combo.blockSignals(False)
                    self.main.t_combo.blockSignals(False)
                    viewer.clear_rectangles(page_switch=True)
                    viewer.clear_brush_strokes(page_switch=True)
                    viewer.clear_text_items()

            self.main.text_ctrl.clear_text_edits()
        finally:
            viewer.set_view_state_notifications_enabled(True)
            viewer.setUpdatesEnabled(True)
            viewer.viewport().update()

    def display_image(
        self,
        index: int,
        switch_page: bool = True,
        original_image=None,
        refresh_original_preview: bool = True,
    ):
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
                self.main.central_stack.setCurrentWidget(self.main.viewer_page)
            else:
                # Regular mode - display single image
                self.main.central_stack.setCurrentWidget(self.main.viewer_page)

            # If the outer stack is still on the home screen, transition to the editor
            try:
                if self.main._center_stack.currentWidget() is self.main.startup_home:
                    self.main.show_main_page()
            except Exception:
                pass

            self.main.central_stack.layout().activate()
            
            # Fit in view only if it's the first time displaying this image and not in webtoon mode
            if first_time_display and not self.main.webtoon_mode:
                self.main.image_viewer.fitInView()
                self.main.displayed_images.add(file_path)  # Mark this image as displayed

            if refresh_original_preview:
                self.main.refresh_original_preview(file_path, original_image=original_image)
            elif not self.main.webtoon_mode:
                self.main.original_image_viewer.clear_scene()
            self.main.refresh_fullscreen_preview()
            self.main.update_page_position_label()

    def on_image_processed(self, index: int, image: np.ndarray, image_path: str):
        file_on_display = self.main.image_files[self.main.curr_img_idx]
        current_batch_file = self.main.selected_batch[index] if self.main.selected_batch else self.main.image_files[index]
        self._clear_page_skip_error(current_batch_file)
        if image_path != current_batch_file:
            self._clear_page_skip_error(image_path)
        
        if current_batch_file == file_on_display:
            self.set_image(image)
        else:
            command = SetImageCommand(self.main, image_path, image, False)
            self.main.undo_stacks[current_batch_file].push(command)
            self.main.image_data[image_path] = image

    def on_render_state_ready(self, file_path: str):
        """Refresh the currently visible page when batch render state is finalized.

        This closes a race where page selection occurs mid-batch: inpaint patches
        may appear first, while text items become available slightly later in
        image_states. We reload the current page state once the render payload is ready.
        """
        if self.main.webtoon_mode:
            return
        if self.main.curr_img_idx < 0 or self.main.curr_img_idx >= len(self.main.image_files):
            return
        current_file = self.main.image_files[self.main.curr_img_idx]
        if current_file != file_path:
            return

        viewer_state = self.main.image_states.get(file_path, {}).get('viewer_state', {})
        if not viewer_state or not viewer_state.get('text_items_state'):
            return

        # Cancel pending async nav loads so stale callbacks can't overwrite this refresh.
        self._nav_request_id += 1

        # Only refresh text items; do not call display_image/load_state because that
        # reapplies saved transform and causes visible zoom/pan jumps.
        viewer = self.main.image_viewer
        viewer.setUpdatesEnabled(False)
        try:
            viewer.clear_text_items()
            self.main.curr_tblock_item = None
            self.main.curr_tblock = None
            self.main.text_ctrl.clear_text_edits()

            # Reload blk_list so that clicking a text item can find the
            # corresponding TextBlock (with OCR text) for s_text_edit.
            stored_blk_list = self.main.image_states.get(file_path, {}).get('blk_list', [])
            self.main.blk_list = stored_blk_list.copy() if stored_blk_list else []

            viewer.set_bulk_text_restore(True)
            try:
                for data in viewer_state.get('text_items_state', []):
                    viewer.add_text_item(data)
            finally:
                viewer.set_bulk_text_restore(False)

            if viewer_state.get('push_to_stack', False):
                stack = self.main.undo_stacks.get(file_path)
                if stack:
                    stack.beginMacro('text_items_rendered')
                    for text_item in viewer.text_items:
                        command = AddTextItemCommand(self.main, text_item)
                        stack.push(command)
                    stack.endMacro()
                viewer_state['push_to_stack'] = False
        finally:
            viewer.setUpdatesEnabled(True)
            viewer.viewport().update()
            self.main.refresh_fullscreen_preview()

    def on_image_skipped(self, image_path: str, skip_reason: str, error: str):
        summarized_error = self._summarize_skip_error(error)
        if hasattr(self.main, "register_batch_skip"):
            self.main.register_batch_skip(image_path, skip_reason, summarized_error)

        if self._is_content_flagged_error(error):
            reason = summarized_error.split(": ")[-1] if ": " in summarized_error else summarized_error
            file_name = os.path.basename(image_path)
            flagged_msg = Messages.get_content_flagged_text(
                details=reason,
                context=skip_reason,
            )
            skip_prefix = QtCore.QCoreApplication.translate("Messages", "Skipping:")
            text = f"{skip_prefix} {file_name}\n{flagged_msg}"
        else:
            text = self._build_skip_message(image_path, skip_reason, summarized_error)
        dayu_type = self._resolve_skip_message_type(skip_reason, error)
        self._page_skip_errors[image_path] = {
            "text": text,
            "dayu_type": dayu_type,
            "dismissed": False,
        }

        if getattr(self.main, "_batch_active", False):
            return

        # If user is currently on this page, show the page-scoped message immediately
        # with no duration; keep transient behavior for all other pages.
        if self._current_file_path() == image_path:
            self._hide_active_page_skip_error()
            self._show_page_skip_error_for_file(image_path)
            return

        self._show_transient_skip_notice(text, dayu_type)
        if self._active_page_error_path == image_path:
            self._hide_active_page_skip_error()
            self._show_page_skip_error_for_file(image_path)

    def on_inpaint_patches_processed(self, patches: list, file_path: str):
        target_stack = self.main.undo_stacks[file_path]

        # Decide visibility against the viewer's *actual* mode state.
        # During webtoon->regular transitions, main.webtoon_mode may flip
        # before the viewer scene is fully switched.
        should_display = False
        if self.main.image_viewer.webtoon_mode:
            # In webtoon mode, display patches for pages that are currently loaded/visible
            loaded_pages = self.main.image_viewer.webtoon_manager.loaded_pages
            page_index = None
            # Find the page index for this file path
            if file_path in self.main.image_files:
                page_index = self.main.image_files.index(file_path)
            if page_index is not None and page_index in loaded_pages:
                should_display = True
        else:
            # Regular mode: only draw when page navigation is stable.
            # If user clicks pages rapidly, currentRow can point to a page
            # that hasn't finished async loading yet; drawing during that
            # transition can place patches on the wrong scene/page.
            current_row = self.main.page_list.currentRow()
            nav_stable = current_row == self.main.curr_img_idx
            file_on_display = (
                self.main.image_files[self.main.curr_img_idx]
                if (0 <= self.main.curr_img_idx < len(self.main.image_files))
                else None
            )
            should_display = (
                nav_stable and
                file_path == file_on_display and
                self.main.central_stack.currentWidget() == self.main.viewer_page and
                self.main.image_viewer.hasPhoto()
            )

        # Create the command for the specific page
        command = PatchInsertCommand(self.main, patches, file_path, display=should_display)
        target_stack.push(command)

    def apply_inpaint_patches(self, patches):
        command = PatchInsertCommand(self.main, patches, self.main.image_files[self.main.curr_img_idx])
        self.main.undo_group.activeStack().push(command)

    def clear_translation_cache_for_pages(self, selected_refs: list[str]) -> None:
        if not selected_refs:
            return

        resolved_paths: list[str] = []
        seen: set[str] = set()
        for ref in selected_refs:
            file_path = ref if ref in self.main.image_files else None
            if file_path is None:
                file_path = next(
                    (path for path in self.main.image_files if os.path.basename(path) == ref),
                    None,
                )
            if file_path and file_path not in seen:
                resolved_paths.append(file_path)
                seen.add(file_path)

        if not resolved_paths:
            return

        images = [self.load_image(file_path) for file_path in resolved_paths]
        removed = self.main.pipeline.cache_manager.clear_translation_cache_for_images(images)
        if removed:
            MMessage.info(
                text=self.main.tr(
                    f"Cleared translation cache for {len(resolved_paths)} selected pages."
                ),
                parent=self.main,
                duration=4,
                closable=True,
            )
        else:
            MMessage.info(
                text=self.main.tr("No translation cache entries were found for the selected pages."),
                parent=self.main,
                duration=4,
                closable=True,
            )

    def cleanup(self):
        """Clean up resources, including the lazy loader."""
        self._close_transient_skip_notice()
        self._hide_active_page_skip_error()
        if hasattr(self, 'page_list_loader'):
            self.page_list_loader.shutdown()
