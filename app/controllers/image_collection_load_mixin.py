from __future__ import annotations

import os
from functools import partial
from typing import List

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.dayu_widgets.clickable_card import ClickMeta


class ImageCollectionLoadMixin:
    def thread_load_images(self, paths: List[str]):
        if paths and paths[0].lower().endswith(".ctpr"):
            self.main.project_ctrl.thread_load_project(paths[0])
            return

        try:
            autosave_enabled = bool(
                hasattr(self.main, "title_bar")
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
        self.main.run_threaded(
            self.load_initial_image,
            self.on_initial_image_loaded,
            self.main.default_error_handler,
            None,
            paths,
        )

    def thread_insert(self, paths: List[str]):
        if not self.main.image_files:
            self.thread_load_images(paths)
            return

        def on_files_prepared(prepared_files):
            if not prepared_files:
                return

            self.save_current_image_state()
            insert_position = len(self.main.image_files)

            for i, file_path in enumerate(prepared_files):
                self.main.image_files.insert(insert_position + i, file_path)
                self.main.image_data[file_path] = None
                self.main.image_history[file_path] = [file_path]
                self.main.in_memory_history[file_path] = []
                self.main.current_history_index[file_path] = 0
                self.main.image_states[file_path] = {
                    "viewer_state": {},
                    "target_render_states": {},
                    "target_lang": self.main.t_combo.currentText(),
                    "brush_strokes": [],
                    "inpaint_cache": [],
                    "blk_list": [],
                    "skip": False,
                    "pipeline_state": {
                        "completed_stages": [],
                        "target_lang": "",
                        "inpaint_hash": "",
                        "translator_key": "",
                        "extra_context_hash": "",
                    },
                }

                stack = QtGui.QUndoStack(self.main)
                stack.cleanChanged.connect(self.main._update_window_modified)
                stack.indexChanged.connect(self.main._bump_dirty_revision)
                self.main.undo_stacks[file_path] = stack
                self.main.undo_group.addStack(stack)

            if self.main.webtoon_mode:
                success = self.main.image_viewer.webtoon_manager.insert_pages(prepared_files, insert_position)
                if success:
                    self.update_image_cards()
                    self.main.page_list.blockSignals(True)
                    self.main.page_list.setCurrentRow(insert_position)
                    self.highlight_card(insert_position)
                    self.main.page_list.blockSignals(False)
                    self.main.curr_img_idx = insert_position
                else:
                    current_page = max(0, self.main.curr_img_idx)
                    self.main.image_viewer.webtoon_manager.load_images_lazy(self.main.image_files, current_page)
                    self.update_image_cards()
                    self.main.page_list.blockSignals(True)
                    self.main.page_list.setCurrentRow(current_page)
                    self.highlight_card(current_page)
                    self.main.page_list.blockSignals(False)
            else:
                self.update_image_cards()
                self.main.page_list.setCurrentRow(insert_position)
                path = prepared_files[0]
                new_index = self.main.image_files.index(path)
                image = self.load_image(path)
                self.display_image_from_loaded(image, new_index, False)

            self.main.mark_project_dirty()

        self.main.run_threaded(
            partial(self.main.file_handler.prepare_files, paths, True),
            on_files_prepared,
            self.main.default_error_handler,
        )

    def on_initial_image_loaded(self, rgb_image: np.ndarray):
        if rgb_image is not None:
            self.main.image_data[self.main.image_files[0]] = rgb_image
            self.main.image_history[self.main.image_files[0]] = [self.main.image_files[0]]
            self.main.in_memory_history[self.main.image_files[0]] = [rgb_image.copy()]
            self.main.current_history_index[self.main.image_files[0]] = 0
            self.save_image_state(self.main.image_files[0])

        for file_path in self.main.image_files:
            self.save_image_state(file_path)
            stack = QtGui.QUndoStack(self.main)
            stack.cleanChanged.connect(self.main._update_window_modified)
            stack.indexChanged.connect(self.main._bump_dirty_revision)
            try:
                if hasattr(self.main, "search_ctrl") and self.main.search_ctrl is not None:
                    stack.indexChanged.connect(self.main.search_ctrl.on_undo_redo)
            except Exception:
                pass
            self.main.undo_stacks[file_path] = stack
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
            self.main.mark_project_dirty()

    def update_image_cards(self):
        self.main.page_list.clear()
        self.main.image_cards.clear()
        self.main.current_card = None
        self._highlighted_card_indices.clear()

        for file_path in self.main.image_files:
            file_name = os.path.basename(file_path)
            list_item = QtWidgets.QListWidgetItem(file_name)
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, file_path)
            card = ClickMeta(extra=False, avatar_size=(35, 50))
            card.setup_data({"title": file_name})
            list_item.setSizeHint(card.sizeHint())
            if self.main.image_states.get(file_path, {}).get("skip"):
                card.set_skipped(True)
            self.main.page_list.addItem(list_item)
            self.main.page_list.setItemWidget(list_item, card)
            self.main.image_cards.append(card)

        self.page_list_loader.set_file_paths(self.main.image_files, self.main.image_cards)
