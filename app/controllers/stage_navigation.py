from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QPainterPath, QTransform
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem

from app.ui.dayu_widgets.push_button import MPushButton
from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.rectangle import MoveableRectItem
from pipeline.render_state import ensure_target_snapshot, get_target_snapshot
from pipeline.stage_state import (
    resolve_target_lang,
    ensure_pipeline_state,
    get_current_stage,
    invalidate_after_box_edit,
    invalidate_after_format_edit,
    invalidate_after_segmentation_edit,
    invalidate_after_source_text_edit,
    invalidate_after_translated_text_edit,
    is_stage_available,
    mark_clean_ready,
    set_current_stage,
)

if TYPE_CHECKING:
    from controller import ComicTranslate


BUTTON_STAGE_MAP = {
    0: "text",
    1: "clean",
    2: "render",
}

UI_STAGE_ORDER = ("text", "clean", "render")
TEXT_INTERNAL_STAGES = ("translate", "ocr", "detect")
CLEAN_INTERNAL_STAGES = ("clean", "segment")

STAGE_TOOL_MAP = {
    "text": "box",
    "clean": "brush",
    "render": None,
}


class StageNavigationController:
    def __init__(self, main: ComicTranslate) -> None:
        self.main = main

    @staticmethod
    def _map_internal_to_ui_stage(stage: str) -> str:
        if stage == "render":
            return "render"
        if stage in {"segment", "clean"}:
            return "clean"
        return "text"

    @staticmethod
    def _set_ui_stage(state: dict, ui_stage: str) -> None:
        if ui_stage in UI_STAGE_ORDER:
            state["ui_stage"] = ui_stage

    def _clone_qt_data(self, value):
        if isinstance(value, QPainterPath):
            return QPainterPath(value)
        if isinstance(value, dict):
            return {key: self._clone_qt_data(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone_qt_data(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._clone_qt_data(item) for item in value)
        return value

    def _clone_brush_strokes(self, strokes: list[dict]) -> list[dict]:
        return [self._clone_qt_data(stroke) for stroke in strokes or []]

    def _current_file_path(self) -> str | None:
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            return self.main.image_files[self.main.curr_img_idx]
        return None

    def _current_target(self) -> str:
        return self.main.t_combo.currentText()

    def _target_for_state(self, state: dict | None = None) -> str:
        return resolve_target_lang(
            state,
            preferred_target=self._current_target(),
            pipeline_state=(state or {}).get("pipeline_state") if isinstance(state, dict) else None,
        )

    def get_ui_stage(self, file_path: str | None = None) -> str:
        file_path = file_path or self._current_file_path()
        if not file_path:
            return "text"
        state = self.main.image_states.get(file_path, {})
        target_lang = self._target_for_state(state)
        ui_stage = state.get("ui_stage")
        if ui_stage in {"text", "clean"}:
            return ui_stage
        if ui_stage == "render" and is_stage_available(
            state,
            "render",
            target_lang=target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        ):
            return ui_stage
        current_stage = get_current_stage(
            state,
            target_lang=target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        return self._map_internal_to_ui_stage(current_stage)

    def _get_state(self, file_path: str) -> dict:
        state = self.main.image_states.setdefault(file_path, {})
        ensure_pipeline_state(
            state,
            target_lang=self._target_for_state(state),
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        return state

    @staticmethod
    def _serialize_rectangles_from_blocks(blk_list) -> list[dict]:
        rectangles = []
        for blk in blk_list or []:
            if getattr(blk, "xyxy", None) is None or len(blk.xyxy) < 4:
                continue
            x1, y1, x2, y2 = blk.xyxy
            rectangles.append(
                {
                    "rect": (float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
                    "rotation": float(getattr(blk, "angle", 0) or 0),
                    "transform_origin": tuple(getattr(blk, "tr_origin_point", ()) or (0.0, 0.0)),
                    "block_uid": getattr(blk, "block_uid", ""),
                }
            )
        return rectangles

    def _extract_view_metadata(self, file_path: str) -> dict:
        state = self._get_state(file_path)
        current_file = self._current_file_path()
        if current_file == file_path and self.main.image_viewer.hasPhoto():
            current = self.main.image_viewer.save_state()
            return {
                "transform": current.get("transform"),
                "center": current.get("center"),
                "scene_rect": current.get("scene_rect"),
            }

        viewer_state = state.get("viewer_state") or {}
        if viewer_state:
            return {
                "transform": viewer_state.get("transform"),
                "center": viewer_state.get("center"),
                "scene_rect": viewer_state.get("scene_rect"),
            }

        identity = QTransform()
        return {
            "transform": (
                identity.m11(),
                identity.m12(),
                identity.m13(),
                identity.m21(),
                identity.m22(),
                identity.m23(),
                identity.m31(),
                identity.m32(),
                identity.m33(),
            ),
            "center": (0.0, 0.0),
            "scene_rect": (0.0, 0.0, 0.0, 0.0),
        }

    def _get_target_snapshot(self, state: dict, target_lang: str) -> dict:
        return get_target_snapshot(state, target_lang)

    def ensure_target_snapshot(self, file_path: str, target_lang: str, source_target: str | None = None) -> dict:
        state = self._get_state(file_path)
        return ensure_target_snapshot(
            state,
            target_lang,
            source_target=source_target or "",
            fallback_snapshot=state.get("viewer_state") or {},
        )

    def _get_segment_strokes(self, file_path: str, state: dict, *, seed_from_blocks: bool = True) -> list[dict]:
        saved_strokes = state.get("brush_strokes") or []
        if saved_strokes:
            return self._clone_brush_strokes(saved_strokes)
        if not seed_from_blocks:
            return []

        blk_list = state.get("blk_list") or []
        if not blk_list:
            return []

        image = self.main.image_ctrl.load_original_image(file_path)
        if image is None:
            return []

        try:
            strokes = self.main.pipeline.inpainting._make_segmentation_strokes_from_blocks(
                image,
                blk_list,
            )
        except Exception:
            strokes = []
        if strokes and not saved_strokes:
            state["brush_strokes"] = self._clone_brush_strokes(strokes)
        return self._clone_brush_strokes(strokes)

    def _preferred_internal_stage(
        self,
        state: dict,
        ui_stage: str,
        *,
        target_lang: str,
        has_runtime_patches: bool,
    ) -> str:
        if ui_stage == "text":
            ordered_stages = TEXT_INTERNAL_STAGES
        elif ui_stage == "clean":
            ordered_stages = CLEAN_INTERNAL_STAGES
        elif ui_stage == "render":
            ordered_stages = ("render",)
        else:
            ordered_stages = ()

        for stage in ordered_stages:
            if is_stage_available(
                state,
                stage,
                target_lang=target_lang,
                has_runtime_patches=has_runtime_patches,
            ):
                return stage
        return ""

    def _build_regular_view_state(self, file_path: str, ui_stage: str) -> tuple[dict, list[dict], bool]:
        state = self._get_state(file_path)
        target_lang = self._target_for_state(state)
        metadata = self._extract_view_metadata(file_path)
        view_state = {
            "transform": metadata.get("transform"),
            "center": metadata.get("center"),
            "scene_rect": metadata.get("scene_rect"),
            "rectangles": [],
            "text_items_state": [],
        }

        if ui_stage == "text":
            view_state["rectangles"] = self._serialize_rectangles_from_blocks(state.get("blk_list") or [])
        elif ui_stage == "render":
            snapshot = self._get_target_snapshot(state, target_lang)
            view_state["text_items_state"] = copy.deepcopy(snapshot.get("text_items_state", []) or [])

        has_existing_clean = bool(state.get("inpaint_cache") or self.main.image_patches.get(file_path))
        strokes = (
            self._get_segment_strokes(
                file_path,
                state,
                seed_from_blocks=not has_existing_clean,
            )
            if ui_stage == "clean"
            else []
        )
        load_patches = ui_stage in {"clean", "render"}
        return view_state, strokes, load_patches

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

        state = self._get_state(file_path)
        scene_mgr = manager.scene_item_manager
        self._clear_webtoon_page_items(page_idx)
        scene_mgr.text_block_manager.load_text_blocks(page_idx)

        temp_state = {
            "viewer_state": {
                "rectangles": [],
                "text_items_state": [],
            },
            "brush_strokes": [],
        }

        if ui_stage == "text":
            temp_state["viewer_state"]["rectangles"] = self._serialize_rectangles_from_blocks(state.get("blk_list") or [])
        elif ui_stage == "render":
            snapshot = self._get_target_snapshot(state, self._target_for_state(state))
            temp_state["viewer_state"]["text_items_state"] = copy.deepcopy(snapshot.get("text_items_state", []) or [])
        elif ui_stage == "clean":
            temp_state["brush_strokes"] = self._get_segment_strokes(
                file_path,
                state,
                seed_from_blocks=not bool(state.get("inpaint_cache") or self.main.image_patches.get(file_path)),
            )

        scene_mgr.rectangle_manager.load_rectangles(temp_state, page_idx)
        scene_mgr.text_item_manager.load_text_items(temp_state, page_idx)
        if ui_stage in {"clean", "render"}:
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
        state = self._get_state(file_path)
        target_lang = self._target_for_state(state)
        has_runtime_patches = bool(
            state.get("inpaint_cache") or self.main.image_patches.get(file_path)
        )
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

    def refresh_stage_buttons(self, file_path: str | None = None) -> None:
        current_file = self._current_file_path()
        if file_path and current_file and file_path != current_file:
            return
        file_path = current_file or file_path
        buttons = self.main.hbutton_group.get_button_group().buttons()
        if not file_path or file_path not in self.main.image_states:
            for button in buttons:
                button.setEnabled(False)
                if hasattr(button, "set_dayu_type"):
                    button.set_dayu_type(MPushButton.DefaultType)
            return

        state = self._get_state(file_path)
        target_lang = self._target_for_state(state)
        has_runtime_patches = bool(
            state.get("inpaint_cache") or self.main.image_patches.get(file_path)
        )
        current_ui_stage = self.get_ui_stage(file_path)

        for idx, button in enumerate(buttons):
            ui_stage = BUTTON_STAGE_MAP.get(idx, "")
            enabled = ui_stage in {"text", "clean"} or is_stage_available(
                state,
                "render",
                target_lang=target_lang,
                has_runtime_patches=has_runtime_patches,
            )
            button.setEnabled(enabled)
            if hasattr(button, "set_dayu_type"):
                button.set_dayu_type(
                    MPushButton.PrimaryType if ui_stage == current_ui_stage and enabled else MPushButton.DefaultType
                )

    def restore_current_page_view(self) -> None:
        file_path = self._current_file_path()
        if not file_path or file_path not in self.main.image_states:
            self.refresh_stage_buttons(file_path)
            return
        self.apply_stage_view(file_path, self.get_ui_stage(file_path))

    def navigate_to_stage(self, ui_stage: str) -> None:
        file_path = self._current_file_path()
        if not file_path:
            return
        self.main.image_ctrl.save_current_image_state()
        self.apply_stage_view(file_path, ui_stage)

    def _run_clean_for_current_view(self, file_path: str) -> None:
        if not self.main.image_viewer.hasPhoto() or not self.main.image_viewer.has_drawn_elements():
            return
        state = self._get_state(file_path)
        self._set_ui_stage(state, "clean")
        self.main.image_ctrl.save_current_image_state()
        self.main.text_ctrl.clear_text_edits()
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        self.main.undo_group.activeStack().beginMacro("clean")
        self.main.run_threaded(
            self.main.pipeline.inpaint,
            self.main.pipeline.inpaint_complete,
            self.main.default_error_handler,
            self.main.on_manual_finished,
        )

    def handle_stage_button(self, index: int) -> None:
        ui_stage = BUTTON_STAGE_MAP.get(index)
        if not ui_stage:
            return
        if ui_stage == "clean":
            file_path = self._current_file_path()
            if file_path and self.get_ui_stage(file_path) == "clean" and self.main.image_viewer.has_drawn_elements():
                self._run_clean_for_current_view(file_path)
                return
        self.navigate_to_stage(ui_stage)

    def invalidate_for_box_edit(self, file_path: str) -> None:
        state = self._get_state(file_path)
        invalidate_after_box_edit(
            state,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        self._set_ui_stage(state, "text")
        self.refresh_stage_buttons(file_path)

    def invalidate_for_source_text_edit(self, file_path: str) -> None:
        state = self._get_state(file_path)
        invalidate_after_source_text_edit(
            state,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        self._set_ui_stage(state, "text")
        self.refresh_stage_buttons(file_path)

    def invalidate_for_translated_text_edit(self, file_path: str, target_lang: str) -> None:
        state = self._get_state(file_path)
        invalidate_after_translated_text_edit(
            state,
            target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        self._set_ui_stage(state, "text")
        self.refresh_stage_buttons(file_path)

    def invalidate_for_format_edit(self, file_path: str, target_lang: str) -> None:
        state = self._get_state(file_path)
        invalidate_after_format_edit(
            state,
            target_lang,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        self._set_ui_stage(state, "text")
        self.refresh_stage_buttons(file_path)

    def invalidate_for_segmentation_edit(self, file_path: str) -> None:
        state = self._get_state(file_path)
        invalidate_after_segmentation_edit(
            state,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        self._set_ui_stage(state, "clean")
        self.refresh_stage_buttons(file_path)

    def mark_clean_ready(self, file_path: str) -> None:
        state = self._get_state(file_path)
        mark_clean_ready(
            state,
            has_runtime_patches=bool(
                state.get("inpaint_cache") or self.main.image_patches.get(file_path)
            ),
        )
        self.refresh_stage_buttons(file_path)
