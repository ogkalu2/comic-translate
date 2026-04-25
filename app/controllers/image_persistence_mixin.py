from __future__ import annotations

import copy
import logging
import os

import imkit as imk
import numpy as np
from PySide6 import QtCore
from app.ui.dayu_widgets.message import MMessage
from app.ui.commands.image import SetImageCommand
from app.ui.commands.inpaint import PatchCommandBase, PatchInsertCommand
from app.path_materialization import ensure_path_materialized
from pipeline.page_state import (
    get_active_viewer_state,
    get_runtime_patches,
    has_runtime_patches as page_has_runtime_patches,
    resolve_page_target_lang,
)
from pipeline.render_state import (
    RENDER_STYLE_OVERRIDES_KEY,
    set_target_snapshot,
    update_render_style_overrides,
)
from pipeline.stage_state import activate_target_lang

logger = logging.getLogger(__name__)


class ImagePersistenceMixin:
    def _resolve_ui_stage_for_save(self, file_path: str, existing: dict) -> str:
        if (
            0 <= self.main.curr_img_idx < len(self.main.image_files)
            and self.main.image_files[self.main.curr_img_idx] == file_path
            and self.main.image_viewer.hasPhoto()
        ):
            current_tool = getattr(self.main.image_viewer, "current_tool", None)
            if current_tool in {"brush", "eraser"}:
                return "clean"
            if current_tool == "box":
                return "text"

        try:
            return self.main.stage_nav_ctrl.get_ui_stage(file_path)
        except Exception:
            return existing.get("ui_stage", "")

    def set_image(self, rgb_img: np.ndarray, push: bool = True):
        if self.main.curr_img_idx >= 0:
            file_path = self.main.image_files[self.main.curr_img_idx]
            SetImageCommand(self.main, file_path, rgb_img, False)
            self.main.image_data[file_path] = rgb_img

    def load_patch_state(self, file_path: str):
        saved_patches = self.main.image_patches.get(file_path, [])
        if not saved_patches:
            return

        mem_list = self.main.in_memory_patches.setdefault(file_path, [])
        mem_by_hash = {patch["hash"]: patch for patch in mem_list}
        scene_hashes = {
            item.data(PatchCommandBase.HASH_KEY)
            for item in self.main.image_viewer._scene.items()
            if item.data(PatchCommandBase.HASH_KEY) is not None
        }
        for saved in saved_patches:
            patch_hash = saved["hash"]
            match = mem_by_hash.get(patch_hash)
            if match is None:
                ensure_path_materialized(saved["png_path"])
                rgb_img = imk.read_image(saved["png_path"])
                match = {
                    "bbox": saved["bbox"],
                    "image": rgb_img,
                    "hash": patch_hash,
                }
                mem_list.append(match)
                mem_by_hash[patch_hash] = match

            if patch_hash in scene_hashes:
                continue

            prop = {
                "bbox": saved["bbox"],
                "image": match["image"],
                "hash": patch_hash,
            }
            if "scene_pos" in saved:
                prop["scene_pos"] = saved["scene_pos"]
            if "page_index" in saved:
                prop["page_index"] = saved["page_index"]

            if PatchCommandBase.create_patch_item(prop, self.main.image_viewer) is not None:
                scene_hashes.add(patch_hash)

    def save_current_image(self, file_path: str):
        if self.main.webtoon_mode:
            final_rgb, _ = self.main.image_viewer.get_visible_area_image(paint_all=True)
        else:
            final_rgb = self.main.image_viewer.get_image_array(paint_all=True)

        imk.write_image(file_path, final_rgb)

    def save_image_state(self, file: str, target_lang: str | None = None):
        existing = self.main.image_states.get(file, {})
        skip_status = existing.get("skip", False)
        current_target = target_lang if target_lang is not None else self.main.t_combo.currentText()
        active_target = current_target or resolve_page_target_lang(
            existing,
            pipeline_state=existing.get("pipeline_state"),
        )
        pipeline_state, active_target = activate_target_lang(
            existing,
            active_target,
            has_runtime_patches=page_has_runtime_patches(
                existing,
                self.main.image_patches,
                file,
            ),
        )
        current_scene_state = self.main.image_viewer.save_state() if self.main.image_viewer.hasPhoto() else {}
        viewer_state = copy.deepcopy(existing.get("viewer_state", {}) or {})
        for key in ("transform", "center", "scene_rect"):
            if current_scene_state.get(key) is not None:
                viewer_state[key] = current_scene_state.get(key)
        target_render_states = copy.deepcopy(existing.get("target_render_states", {}) or {})
        inpaint_cache = copy.deepcopy(
            get_runtime_patches(existing, self.main.image_patches, file)
        )
        blk_list = self.main.blk_list.copy() if (
            0 <= self.main.curr_img_idx < len(self.main.image_files)
            and self.main.image_files[self.main.curr_img_idx] == file
        ) else copy.deepcopy(existing.get("blk_list", []) or [])

        viewer_state["rectangles"] = self.main.stage_nav_ctrl._serialize_rectangles_from_blocks(blk_list)
        state_payload = {
            "viewer_state": viewer_state,
            "target_render_states": target_render_states,
            "target_lang": active_target,
            "ui_stage": self._resolve_ui_stage_for_save(file, existing),
            "brush_strokes": self.main.image_viewer.save_brush_strokes(),
            "inpaint_cache": inpaint_cache,
            "blk_list": blk_list,
            "skip": skip_status,
            "pipeline_state": pipeline_state,
            RENDER_STYLE_OVERRIDES_KEY: copy.deepcopy(existing.get(RENDER_STYLE_OVERRIDES_KEY, {}) or {}),
        }

        current_stage = pipeline_state.get("current_stage", "")
        current_text_items = current_scene_state.get("text_items_state")
        has_current_text_items = isinstance(current_text_items, list) and bool(current_text_items)
        if (current_stage == "render" or has_current_text_items) and current_text_items is not None:
            viewer_state["text_items_state"] = copy.deepcopy(current_text_items or [])
            if active_target:
                set_target_snapshot(state_payload, active_target, viewer_state)
                update_render_style_overrides(state_payload, viewer_state)
        elif active_target and active_target in state_payload["target_render_states"]:
            for key in ("transform", "center", "scene_rect"):
                if current_scene_state.get(key) is not None:
                    state_payload["target_render_states"][active_target][key] = current_scene_state.get(key)
        self.main.image_states[file] = state_payload
        if current_stage == "render":
            self._reconcile_render_snapshot_state(file, active_target)

    def save_current_image_state(self, target_lang: str | None = None):
        if self.main.curr_img_idx >= 0:
            current_file = self.main.image_files[self.main.curr_img_idx]
            self.save_image_state(current_file, target_lang=target_lang)

    def load_image_state(self, file_path: str):
        rgb_image = self.main.image_data[file_path]
        viewer = self.main.image_viewer

        viewer.setUpdatesEnabled(False)
        viewer.set_view_state_notifications_enabled(False)
        try:
            viewer.display_image_array(rgb_image, fit=False)

            if file_path in self.main.image_states:
                state = self.main.image_states[file_path]
                stored_blks = state.get("blk_list", [])
                stored_brush_strokes = state.get("brush_strokes", [])
                current_target = self.main.t_combo.currentText()
                viewer_state = get_active_viewer_state(
                    state,
                    preferred_target=current_target,
                    fallback_to_viewer_state=True,
                )

                rectangles_state = viewer_state.get("rectangles", [])
                if stored_blks and rectangles_state:
                    needs_uid_migration = any(not rect.get("block_uid") for rect in rectangles_state)
                    if needs_uid_migration:
                        for rect_data, blk in zip(rectangles_state, stored_blks):
                            if not rect_data.get("block_uid"):
                                rect_data["block_uid"] = getattr(blk, "block_uid", "")

                if viewer_state:
                    self.main.blk_list = state["blk_list"].copy()
                    viewer.load_state(viewer_state)
                    state["viewer_state"] = viewer_state
                    viewer.load_brush_strokes(state["brush_strokes"])
                    viewer_state["push_to_stack"] = False
                    self.load_patch_state(file_path)
                else:
                    self.main.blk_list = stored_blks.copy()
                    if stored_blks:
                        logger.info(
                            "Loaded page state without viewer_state but with %d stored blocks: %s",
                            len(stored_blks),
                            os.path.basename(file_path),
                        )

                    if stored_brush_strokes:
                        viewer.load_brush_strokes(stored_brush_strokes)

                    if self.main.blk_list:
                        self.main.pipeline.load_box_coords(self.main.blk_list)

                    self.load_patch_state(file_path)

            self.main.text_ctrl.clear_text_edits()
        finally:
            viewer.set_view_state_notifications_enabled(True)
            viewer.setUpdatesEnabled(True)
            viewer.viewport().update()

    def on_inpaint_patches_processed(self, patches: list, file_path: str):
        target_stack = self.main.undo_stacks[file_path]

        should_display = False
        if self.main.image_viewer.webtoon_mode:
            loaded_pages = self.main.image_viewer.webtoon_manager.loaded_pages
            page_index = None
            if file_path in self.main.image_files:
                page_index = self.main.image_files.index(file_path)
            if page_index is not None and page_index in loaded_pages:
                should_display = True
        else:
            current_row = self.main.page_list.currentRow()
            nav_stable = current_row == self.main.curr_img_idx
            file_on_display = (
                self.main.image_files[self.main.curr_img_idx]
                if (0 <= self.main.curr_img_idx < len(self.main.image_files))
                else None
            )
            should_display = (
                nav_stable
                and file_path == file_on_display
                and self.main.central_stack.currentWidget() == self.main.viewer_page
                and self.main.image_viewer.hasPhoto()
                and self.main.stage_nav_ctrl.get_ui_stage(file_path) in {"clean", "render"}
            )

        command = PatchInsertCommand(self.main, patches, file_path, display=should_display)
        target_stack.push(command)

        state = self.main.image_states.get(file_path)
        if state is not None:
            state["inpaint_cache"] = copy.deepcopy(self.main.image_patches.get(file_path, []))
            self.main.stage_nav_ctrl.mark_clean_ready(file_path)

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
