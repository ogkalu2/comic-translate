from __future__ import annotations

import os
import numpy as np
from typing import TYPE_CHECKING
from PySide6 import QtCore, QtWidgets

from app.controllers.image_collection_load_mixin import ImageCollectionLoadMixin
from app.controllers.image_collection_mutation_mixin import ImageCollectionMutationMixin
from app.controllers.image_display_mixin import ImageDisplayMixin
from app.controllers.image_error_mixin import ImageErrorMixin
from app.controllers.image_persistence_mixin import ImagePersistenceMixin
from app.ui.dayu_widgets.message import MMessage
from app.ui.commands.image import ToggleSkipImagesCommand
from app.ui.list_view_image_loader import ListViewImageLoader
from app.thread_worker import GenericWorker

if TYPE_CHECKING:
    from controller import ComicTranslate


class ImageStateController(
    ImageDisplayMixin,
    ImageCollectionLoadMixin,
    ImageCollectionMutationMixin,
    ImageErrorMixin,
    ImagePersistenceMixin,
):
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
        self._pending_text_stack_restore = set()

    def _restore_text_items_to_stack_if_needed(self, file_path: str, viewer) -> None:
        self._pending_text_stack_restore.discard(file_path)

    def apply_undo_redo_to_selected(self, redo: bool) -> None:
        current_path = self._current_file_path()
        if not current_path:
            return

        try:
            self.main.text_ctrl._commit_pending_text_command()
        except Exception:
            pass

        self.save_current_image_state()

        stack = self.main.undo_stacks.get(current_path)
        if stack is None:
            return

        operation = "redo" if redo else "undo"
        can_apply = "canRedo" if redo else "canUndo"
        if not getattr(stack, can_apply)():
            return

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            if not self._show_page_for_undo_redo(
                current_path,
                refresh_original_preview=False,
            ):
                return
            self.main.undo_group.setActiveStack(stack)
            getattr(stack, operation)()
            self.save_current_image_state()
        finally:
            self._show_page_for_undo_redo(current_path, refresh_original_preview=True)
            self.main.undo_group.setActiveStack(stack)
            QtWidgets.QApplication.restoreOverrideCursor()

        self.main.stage_nav_ctrl.restore_current_page_view()
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

    def clear_state(self):
        # Clear existing image data
        self.main.setWindowTitle("Project1.ctpr[*]")
        self._close_transient_skip_notice()
        self._hide_active_page_skip_error()
        self._page_skip_errors.clear()
        self._suppress_dismiss_message_ids.clear()
        self.main.curr_img_idx = -1
        self.main.image_files = []
        self.main.image_states.clear()
        self.main.image_data.clear()
        self.main.image_history.clear()
        self.main.current_history_index.clear()
        self.main.blk_list = []
        self.main.displayed_images.clear()
        self.main.image_viewer.clear_scene()
        self.main.image_viewer.resetTransform()
        self.main.image_viewer.webtoon_view_state = {}
        self.main.image_viewer._programmatic_scroll = False
        self.main.image_viewer.empty = True
        self.main.s_text_edit.clear()
        self.main.t_text_edit.clear()
        self.main.original_image_viewer.clear_scene()
        self.main.original_image_viewer.resetTransform()
        self.main.fullscreen_preview.close()
        self.main.loaded_images = []
        self.main.in_memory_history.clear()
        self.main.undo_stacks.clear()
        self.main.image_patches.clear()
        self.main.in_memory_patches.clear()
        try:
            self.main.pipeline.cache_manager.clear_all_caches()
        except Exception:
            pass
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

        self.main.update_page_position_label()
        self.main.set_project_clean()

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
        command.redo()
        self.main.mark_project_dirty()

    def cleanup(self):
        self._close_transient_skip_notice()
        self._hide_active_page_skip_error()
        if hasattr(self, "page_list_loader"):
            self.page_list_loader.shutdown()
