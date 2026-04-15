from __future__ import annotations

import os
import uuid

from app.projects.project_state_v2 import remap_lazy_blob_paths


class ImageCollectionMutationMixin:
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

    def handle_image_deletion(self, file_names: list[str]):
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

        for file_name in file_names:
            file_path = resolve_path(file_name)
            if not file_path:
                continue

            deleted_paths.append(file_path)
            self.main.image_files.remove(file_path)
            removed_any = True
            self._clear_page_skip_error(file_path)

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
                    matching_paths = [fp for fp in webtoon_file_paths if os.path.basename(fp) == file_name]
                deleted_webtoon_paths.extend(matching_paths)

        path_mapping = {}
        if removed_any:
            path_mapping.update(self.main.file_handler.renumber_archive_pages(self.main.image_files))
            path_mapping.update(self._renumber_project_loaded_pages(self.main.image_files))
        self._remap_state_after_archive_renumber(path_mapping)

        target_path = None
        if self.main.image_files:
            if original_current_path and original_current_path not in deleted_paths:
                target_path = path_mapping.get(original_current_path, original_current_path)
            elif original_paths:
                if original_current_index >= 0:
                    candidates = [
                        path
                        for idx, path in enumerate(original_paths)
                        if path not in deleted_paths and idx >= original_current_index
                    ]
                    if candidates:
                        target_path = path_mapping.get(candidates[0], candidates[0])
                    else:
                        remaining_before = [
                            path
                            for idx, path in enumerate(original_paths)
                            if path not in deleted_paths and idx < original_current_index
                        ]
                        if remaining_before:
                            target_path = path_mapping.get(remaining_before[-1], remaining_before[-1])
                if target_path is None:
                    target_path = path_mapping.get(self.main.image_files[0], self.main.image_files[0])

        if self.main.webtoon_mode:
            if self.main.image_files:
                if target_path in self.main.image_files:
                    self.main.curr_img_idx = self.main.image_files.index(target_path)
                success = self.main.image_viewer.webtoon_manager.remove_pages(deleted_webtoon_paths)

                if success:
                    self.main.image_viewer.webtoon_manager.image_loader.image_file_paths = self.main.image_files.copy()
                    if self.main.curr_img_idx >= len(self.main.image_files):
                        self.main.curr_img_idx = len(self.main.image_files) - 1

                    current_page = max(0, self.main.curr_img_idx)
                    self.update_image_cards()
                    self.main.page_list.blockSignals(True)
                    self.main.page_list.setCurrentRow(current_page)
                    self.highlight_card(current_page)
                    self.main.page_list.blockSignals(False)
                else:
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
            if self.main.image_files:
                if target_path in self.main.image_files:
                    new_index = self.main.image_files.index(target_path)
                else:
                    if self.main.curr_img_idx >= len(self.main.image_files):
                        self.main.curr_img_idx = len(self.main.image_files) - 1
                    new_index = max(0, self.main.curr_img_idx)
                file_path = self.main.image_files[new_index]
                image = self.load_image(file_path)
                self.display_image_from_loaded(image, new_index, False)
                self.update_image_cards()
                self.main.page_list.blockSignals(True)
                self.main.page_list.setCurrentRow(new_index)
                self.highlight_card(new_index)
                self.main.page_list.blockSignals(False)
            else:
                self.main.curr_img_idx = -1
                self.main.central_stack.setCurrentWidget(self.main.drag_browser)
                try:
                    self.main.show_home_screen()
                except Exception:
                    pass
                self.update_image_cards()

        if not self.main.image_files:
            self.main.project_ctrl.clear_recovery_checkpoint()

        if removed_any:
            self.main.mark_project_dirty()

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
            path
            for path in remaining_paths
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
