from __future__ import annotations

from PySide6.QtGui import QPainterPath, QTransform

from app.controllers.stage_view_model import build_stage_view_model
from pipeline.page_state import build_page_state_context, get_active_viewer_state, resolve_page_target_lang
from pipeline.render_state import ensure_target_snapshot
from pipeline.stage_state import get_current_stage, is_stage_available


UI_STAGE_ORDER = ("text", "clean", "render")
TEXT_INTERNAL_STAGES = ("translate", "ocr", "detect")
CLEAN_INTERNAL_STAGES = ("clean", "segment")

STAGE_TOOL_MAP = {
    "text": "box",
    "clean": "brush",
    "render": None,
}


class StageViewStateMixin:
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
        return resolve_page_target_lang(
            state,
            preferred_target=self._current_target(),
            pipeline_state=(state or {}).get("pipeline_state") if isinstance(state, dict) else None,
        )

    def _get_page_context(self, file_path: str):
        return build_page_state_context(
            self.main.image_states,
            self.main.image_patches,
            file_path,
            preferred_target=self._current_target(),
            ensure_state=True,
        )

    def get_ui_stage(self, file_path: str | None = None) -> str:
        file_path = file_path or self._current_file_path()
        if not file_path:
            return "text"
        page_ctx = self._get_page_context(file_path)
        state = page_ctx.state
        target_lang = page_ctx.target_lang
        ui_stage = state.get("ui_stage")
        if ui_stage in {"text", "clean"}:
            return ui_stage
        if ui_stage == "render" and is_stage_available(
            state,
            "render",
            target_lang=target_lang,
            has_runtime_patches=page_ctx.has_runtime_patches,
        ):
            return ui_stage
        current_stage = get_current_stage(
            state,
            target_lang=target_lang,
            has_runtime_patches=page_ctx.has_runtime_patches,
        )
        return self._map_internal_to_ui_stage(current_stage)

    def _get_state(self, file_path: str) -> dict:
        return self._get_page_context(file_path).state

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

        viewer_state = get_active_viewer_state(
            state,
            preferred_target=self._current_target(),
            fallback_to_viewer_state=True,
        )
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
        return get_active_viewer_state(
            state,
            target_lang=target_lang,
            fallback_to_viewer_state=True,
        )

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
        page_ctx = self._get_page_context(file_path)
        state = page_ctx.state
        target_lang = page_ctx.target_lang
        metadata = self._extract_view_metadata(file_path)
        rectangles = []
        text_items_state = []

        if ui_stage == "text":
            rectangles = self._serialize_rectangles_from_blocks(state.get("blk_list") or [])
        elif ui_stage == "render":
            snapshot = self._get_target_snapshot(state, target_lang)
            text_items_state = snapshot.get("text_items_state", []) or []

        has_existing_clean = page_ctx.has_runtime_patches
        strokes = (
            self._get_segment_strokes(
                file_path,
                state,
                seed_from_blocks=not has_existing_clean,
            )
            if ui_stage == "clean"
            else []
        )
        view_model = build_stage_view_model(
            ui_stage,
            rectangles=rectangles,
            text_items_state=text_items_state,
            brush_strokes=strokes,
            metadata=metadata,
        )
        return view_model.viewer_state, view_model.brush_strokes, view_model.load_patches
