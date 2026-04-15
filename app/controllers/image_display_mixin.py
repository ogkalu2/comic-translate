from __future__ import annotations

from functools import partial
from typing import List

import imkit as imk
import numpy as np
from PySide6 import QtCore

from app.path_materialization import ensure_path_materialized
from app.thread_worker import GenericWorker
from app.ui.commands.image import SetImageCommand
from pipeline.render_state import get_target_render_states


class ImageDisplayMixin:
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

        if file_path in self.main.image_history:
            current_index = self.main.current_history_index[file_path]
            current_temp_path = self.main.image_history[file_path][current_index]
            ensure_path_materialized(current_temp_path)
            rgb_image = imk.read_image(current_temp_path)
            if rgb_image is not None:
                return rgb_image

        ensure_path_materialized(file_path)
        return imk.read_image(file_path)

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
        self.page_list_loader.force_load_image(index)
        self._hide_active_page_skip_error()

        if getattr(self.main, "_processing_page_change", False):
            self._show_page_skip_error_for_file(file_path)
            return

        if self.main.webtoon_mode:
            if self.main.image_viewer.hasPhoto():
                self.main.curr_img_idx = index
                self.main.image_viewer.scroll_to_page(index)
                if file_path in self.main.image_states:
                    get_target_render_states(self.main.image_states[file_path])
                self.main.text_ctrl.clear_text_edits()
            else:
                self._run_async_nav_load(index)
        else:
            self._run_async_nav_load(index)

        self._show_page_skip_error_for_file(file_path)

    def navigate_images(self, direction: int):
        if self.main.image_files:
            new_index = self.main.curr_img_idx + direction
            if 0 <= new_index < len(self.main.image_files):
                item = self.main.page_list.item(new_index)
                self.main.page_list.setCurrentItem(item)

    def _run_async_nav_load(self, index: int):
        if not (0 <= index < len(self.main.image_files)):
            return

        self._nav_request_id += 1
        req_id = self._nav_request_id
        file_path = self.main.image_files[index]

        def _bg_load():
            img = self.load_image(file_path)
            original = self._get_cached_original_image(file_path)
            if req_id == self._nav_request_id:
                self._preload_patches(file_path, request_id=req_id)
            return img, original

        worker = GenericWorker(_bg_load)

        def _on_result(result):
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

        worker.signals.result.connect(partial(self._dispatch_result, _on_result))
        worker.signals.error.connect(partial(self._dispatch_error, self.main.default_error_handler))
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

        worker.signals.result.connect(partial(self._dispatch_result, _on_result))
        worker.signals.error.connect(partial(self._dispatch_error, self.main.default_error_handler))
        self._original_nav_worker = worker
        self.main.threadpool.start(worker)

    def _preload_patches(self, file_path: str, request_id: int | None = None):
        saved_patches = self.main.image_patches.get(file_path)
        if not saved_patches:
            return
        mem_list = self.main.in_memory_patches.get(file_path, [])
        mem_hashes = {m["hash"] for m in mem_list}
        loaded = []
        for saved in saved_patches:
            if request_id is not None and request_id != self._nav_request_id:
                return
            if saved["hash"] not in mem_hashes:
                ensure_path_materialized(saved["png_path"])
                rgb_img = imk.read_image(saved["png_path"])
                if rgb_img is not None:
                    loaded.append({
                        "bbox": saved["bbox"],
                        "image": rgb_img,
                        "hash": saved["hash"],
                    })
        if loaded:
            self.main.in_memory_patches.setdefault(file_path, []).extend(loaded)

    def highlight_card(self, index: int):
        highlighted = {index} if 0 <= index < len(self.main.image_cards) else set()
        self._set_highlighted_cards(highlighted, current_index=index if highlighted else None)

    def on_selection_changed(self, selected_indices: list):
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

        if file_path not in self.main.loaded_images:
            self.main.loaded_images.append(file_path)
            if len(self.main.loaded_images) > self.main.max_images_in_memory:
                oldest_image = self.main.loaded_images.pop(0)
                self.main.image_data.pop(oldest_image, None)
                self.main.in_memory_history[oldest_image] = []
                self.main.in_memory_patches.pop(oldest_image, None)

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

            if file_path in self.main.undo_stacks:
                self.main.undo_group.setActiveStack(self.main.undo_stacks[file_path])

            first_time_display = file_path not in self.main.displayed_images
            self.load_image_state(file_path)

            if self.main.webtoon_mode:
                self.main.image_viewer.scroll_to_page(index)
                self.main.central_stack.setCurrentWidget(self.main.viewer_page)
            else:
                self.main.central_stack.setCurrentWidget(self.main.viewer_page)

            try:
                if self.main._center_stack.currentWidget() is self.main.startup_home:
                    self.main.show_main_page()
            except Exception:
                pass

            self.main.central_stack.layout().activate()
            self.main.stage_nav_ctrl.restore_current_page_view()

            if first_time_display and not self.main.webtoon_mode:
                self.main.image_viewer.fitInView()
                self.main.displayed_images.add(file_path)

            if refresh_original_preview:
                self.main.refresh_original_preview(file_path, original_image=original_image)
            elif not self.main.webtoon_mode:
                self.main.original_image_viewer.clear_scene()
            self.main.refresh_fullscreen_preview()
            self.main.update_page_position_label()

    def on_image_processed(self, index: int, image: np.ndarray, image_path: str):
        file_on_display = self.main.image_files[self.main.curr_img_idx]
        current_batch_file = (
            self.main.selected_batch[index]
            if self.main.selected_batch
            else self.main.image_files[index]
        )
        self._clear_page_skip_error(current_batch_file)
        if image_path != current_batch_file:
            self._clear_page_skip_error(image_path)

        if current_batch_file == file_on_display:
            self.set_image(image)
        else:
            SetImageCommand(self.main, image_path, image, False)
            self.main.image_data[image_path] = image
