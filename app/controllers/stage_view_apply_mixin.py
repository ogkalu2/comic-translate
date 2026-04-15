from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem

from app.controllers.stage_view_model import build_stage_view_model
from app.controllers.stage_view_state_mixin import STAGE_TOOL_MAP, UI_STAGE_ORDER
from app.ui.canvas.rectangle import MoveableRectItem
from app.ui.canvas.text_item import TextBlockItem
from pipeline.stage_state import set_current_stage


class StageViewApplyMixin:
    def _apply_regular_stage_view(self, file_path: str, ui_stage: str) -> None:
        image = self.main.image_ctrl.load_original_image(file_path)
        if image is None:
            image = self.main.image_ctrl.load_image(file_path)
        if image is None:
            return

        state = self._get_state(file_path)
        view_state, strokes, load_patches = self._build_regular_view_state(file_path, ui_stage)
        viewer = self.main.image_viewer

        viewer.setUpdatesEnabled(False)
        viewer.set_view_state_notifications_enabled(False)
        try:
            viewer.display_image_array(image, fit=False)
            viewer.load_state(view_state)

            if load_patches:
                self.main.image_ctrl.load_patch_state(file_path)
            if strokes:
                viewer.load_brush_strokes(strokes)
        finally:
            viewer.set_view_state_notifications_enabled(True)
            viewer.setUpdatesEnabled(True)
            viewer.viewport().update()

        self.main.blk_list = list(state.get("blk_list") or [])
        self.main.curr_tblock = None
        self.main.curr_tblock_item = None
        self.main.text_ctrl.clear_text_edits()
        self.main.set_tool(STAGE_TOOL_MAP.get(ui_stage))
        self.main.refresh_fullscreen_preview()

    def _clear_webtoon_page_items(self, page_idx: int) -> None:
        manager = getattr(self.main.image_viewer, "webtoon_manager", None)
        if manager is None or page_idx >= len(self.main.image_files):
            return
        if page_idx not in manager.loaded_pages:
            return

        page_y = manager.image_positions[page_idx]
        page_bottom = page_y + manager.image_heights[page_idx]
        scene = self.main.image_viewer._scene

        for item in list(scene.items()):
            if item in manager.image_items.values() or item in manager.placeholder_items.values():
                continue

            remove_item = False
            if isinstance(item, MoveableRectItem):
                item_top = item.pos().y()
                item_bottom = item_top + item.rect().height()
                remove_item = not (item_bottom < page_y or item_top > page_bottom)
                if remove_item and item in self.main.image_viewer.rectangles:
                    self.main.image_viewer.rectangles.remove(item)
                    if self.main.image_viewer.selected_rect is item:
                        self.main.image_viewer.selected_rect = None
            elif isinstance(item, TextBlockItem):
                item_top = item.pos().y()
                item_bottom = item_top + item.boundingRect().height()
                remove_item = not (item_bottom < page_y or item_top > page_bottom)
                if remove_item and item in self.main.image_viewer.text_items:
                    self.main.image_viewer.text_items.remove(item)
            elif isinstance(item, QGraphicsPathItem):
                bounds = item.mapRectToScene(item.boundingRect())
                remove_item = not (bounds.bottom() < page_y or bounds.top() > page_bottom)
                if remove_item:
                    self.main.image_viewer.unregister_brush_stroke(item)
            elif isinstance(item, QGraphicsPixmapItem) and item.data(0) is not None:
                item_top = item.pos().y()
                item_bottom = item_top + item.boundingRect().height()
                remove_item = not (item_bottom < page_y or item_top > page_bottom)

            if remove_item:
                scene.removeItem(item)

        self.main.blk_list = [
            blk
            for blk in self.main.blk_list
            if getattr(blk, "xyxy", None) is not None and (blk.xyxy[3] < page_y or blk.xyxy[1] > page_bottom)
        ]

    def _apply_webtoon_stage_view(self, file_path: str, ui_stage: str) -> None:
        page_idx = self.main.curr_img_idx
        manager = getattr(self.main.image_viewer, "webtoon_manager", None)
        if manager is None or page_idx not in manager.loaded_pages:
            return

        page_ctx = self._get_page_context(file_path)
        state = page_ctx.state
        scene_mgr = manager.scene_item_manager
        self._clear_webtoon_page_items(page_idx)
        scene_mgr.text_block_manager.load_text_blocks(page_idx)

        rectangles = []
        text_items_state = []
        brush_strokes = []

        if ui_stage == "text":
            rectangles = self._serialize_rectangles_from_blocks(state.get("blk_list") or [])
        elif ui_stage == "render":
            snapshot = self._get_target_snapshot(state, page_ctx.target_lang)
            text_items_state = snapshot.get("text_items_state", []) or []
        elif ui_stage == "clean":
            brush_strokes = self._get_segment_strokes(
                file_path,
                state,
                seed_from_blocks=not page_ctx.has_runtime_patches,
            )

        view_model = build_stage_view_model(
            ui_stage,
            rectangles=rectangles,
            text_items_state=text_items_state,
            brush_strokes=brush_strokes,
        )
        temp_state = {
            "viewer_state": view_model.viewer_state,
            "brush_strokes": view_model.brush_strokes,
        }

        scene_mgr.rectangle_manager.load_rectangles(temp_state, page_idx)
        scene_mgr.text_item_manager.load_text_items(temp_state, page_idx)
        if view_model.load_patches:
            scene_mgr.patch_manager.unload_patches(page_idx)
            scene_mgr.patch_manager.load_patches(page_idx)
        else:
            scene_mgr.patch_manager.unload_patches(page_idx)
        scene_mgr.brush_stroke_manager.load_brush_strokes(temp_state, page_idx)

        self.main.curr_tblock = None
        self.main.curr_tblock_item = None
        self.main.text_ctrl.clear_text_edits()
        self.main.set_tool(STAGE_TOOL_MAP.get(ui_stage))
        self.main.image_viewer.viewport().update()
        self.main.refresh_fullscreen_preview()

    def apply_stage_view(self, file_path: str, ui_stage: str) -> None:
        if not file_path or ui_stage not in UI_STAGE_ORDER:
            return
        page_ctx = self._get_page_context(file_path)
        state = page_ctx.state
        target_lang = page_ctx.target_lang
        has_runtime_patches = page_ctx.has_runtime_patches
        internal_stage = self._preferred_internal_stage(
            state,
            ui_stage,
            target_lang=target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        if internal_stage:
            set_current_stage(
                state,
                internal_stage,
                target_lang=target_lang,
                has_runtime_patches=has_runtime_patches,
            )
        self._set_ui_stage(state, ui_stage)

        if self.main.webtoon_mode:
            self._apply_webtoon_stage_view(file_path, ui_stage)
        else:
            self._apply_regular_stage_view(file_path, ui_stage)
        self.refresh_stage_buttons(file_path)
