from __future__ import annotations

from PySide6.QtGui import QColor

from app.controllers.workflow_support import prepare_multi_page_context, reload_current_webtoon_page
from app.ui.canvas.text.text_item_properties import TextItemProperties
from modules.rendering.font_sizing import resolve_init_font_size
from modules.rendering.policy import is_vertical_block
from modules.rendering.render import pyside_word_wrap
from modules.utils.image_utils import get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.pipeline_config import font_selected
from modules.utils.translator_utils import format_translations
from pipeline.page_state import has_runtime_patches as page_has_runtime_patches
from pipeline.render_state import (
    build_render_template_map,
    get_render_template_for_block,
    set_target_snapshot,
    update_render_style_overrides,
)
from pipeline.stage_state import finalize_render_stage


class TextRenderBatchMixin:
    def render_all_pages(self) -> None:
        self._render_selected_pages(list(self.main.image_files))

    def _render_selected_pages(self, selected_paths: list[str]) -> None:
        if not selected_paths:
            return
        self.main.set_tool(None)
        if not font_selected(self.main):
            return
        self.clear_text_edits()
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()

        context = prepare_multi_page_context(self.main, selected_paths)

        self.main.run_threaded(
            lambda: self._render_selected_pages_worker(selected_paths),
            lambda updated_paths: self._on_selected_render_ready(updated_paths, context),
            self.main.default_error_handler,
            self.main.on_manual_finished,
        )

    def _render_selected_pages_worker(self, selected_paths: list[str]) -> set[str]:
        render_settings = self.render_settings()
        upper = render_settings.upper_case
        line_spacing = float(self.main.line_spacing_dropdown.currentText())
        font_family = self.main.font_dropdown.currentText()
        outline_width = float(self.main.outline_width_dropdown.currentText())
        bold = self.main.bold_button.isChecked()
        italic = self.main.italic_button.isChecked()
        underline = self.main.underline_button.isChecked()
        align_id = self.main.alignment_tool_group.get_dayu_checked()
        alignment = self.main.button_to_alignment[align_id]
        direction = render_settings.direction
        max_font_size = self.main.settings_page.get_max_font_size()
        min_font_size = self.main.settings_page.get_min_font_size()
        setting_font_color = QColor(render_settings.color)
        outline_color = QColor(render_settings.outline_color) if render_settings.outline else None
        second_outline_color = QColor(render_settings.second_outline_color) if render_settings.second_outline else None
        gradient_start_color = QColor(render_settings.text_gradient_start_color) if render_settings.text_gradient else None
        gradient_end_color = QColor(render_settings.text_gradient_end_color) if render_settings.text_gradient else None

        updated_paths: set[str] = set()
        target_lang_fallback = self.main.t_combo.currentText()
        for file_path in selected_paths:
            state = self.main.image_states.get(file_path, {})
            blk_list = state.get("blk_list", [])
            if not blk_list:
                continue

            target_lang = state.get("target_lang", target_lang_fallback)
            target_lang_en = self.main.lang_mapping.get(target_lang, None)
            trg_lng_cd = get_language_code(target_lang_en)
            format_translations(blk_list, trg_lng_cd, upper_case=upper)

            viewer_state = state.setdefault("viewer_state", {})
            existing_text_items = list(viewer_state.get("text_items_state", []))
            block_uids = {
                str(getattr(blk, "block_uid", "") or "")
                for blk in blk_list
                if getattr(blk, "block_uid", "")
            }
            block_legacy_keys = {
                (
                    int(getattr(blk, "xyxy", [0, 0, 0, 0])[0]),
                    int(getattr(blk, "xyxy", [0, 0, 0, 0])[1]),
                    float(getattr(blk, "angle", 0.0) or 0.0),
                )
                for blk in blk_list
                if not getattr(blk, "block_uid", "")
            }
            preserved_text_items = []
            for item in existing_text_items:
                if not isinstance(item, dict):
                    continue
                item_uid = str(item.get("block_uid", "") or "")
                if item_uid and item_uid in block_uids:
                    continue
                if not item_uid:
                    position = item.get("position", (0, 0))
                    legacy_key = (
                        int(position[0]),
                        int(position[1]),
                        float(item.get("rotation", 0.0) or 0.0),
                    )
                    if legacy_key in block_legacy_keys:
                        continue
                preserved_text_items.append(item)

            template_map = build_render_template_map(state, target_lang)
            new_text_items_state = []
            for blk in blk_list:
                x1, y1, block_width, block_height = blk.xywh
                translation = blk.translation or blk.text
                if not translation or len(translation) == 1:
                    continue

                template = get_render_template_for_block(template_map, blk)
                position = template.get("position") or (x1, y1)
                block_width = float(template.get("width", block_width) or block_width)
                block_height = float(template.get("height", block_height) or block_height)
                rotation = template.get("rotation", blk.angle)
                scale = template.get("scale", 1.0)
                transform_origin = template.get("transform_origin", blk.tr_origin_point if blk.tr_origin_point else (0, 0))
                font_family_for_block = template.get("font_family", font_family)
                line_spacing_for_block = float(template.get("line_spacing", line_spacing))
                outline_width_for_block = float(template.get("outline_width", outline_width))
                outline_enabled = bool(template.get("outline", render_settings.outline))
                template_outline_color = template.get("outline_color", outline_color)
                if template_outline_color is not None and not isinstance(template_outline_color, QColor):
                    template_outline_color = QColor(template_outline_color)
                outline_color_for_block = template_outline_color if outline_enabled else None
                second_outline_for_block = bool(template.get("second_outline", render_settings.second_outline))
                second_outline_width_for_block = float(template.get("second_outline_width", render_settings.second_outline_width))
                template_second_outline_color = template.get("second_outline_color", second_outline_color)
                if template_second_outline_color is not None and not isinstance(template_second_outline_color, QColor):
                    template_second_outline_color = QColor(template_second_outline_color)
                second_outline_color_for_block = template_second_outline_color if second_outline_for_block else None
                text_gradient_for_block = bool(template.get("text_gradient", render_settings.text_gradient))
                template_gradient_start = template.get("text_gradient_start_color", gradient_start_color)
                template_gradient_end = template.get("text_gradient_end_color", gradient_end_color)
                if template_gradient_start is not None and not isinstance(template_gradient_start, QColor):
                    template_gradient_start = QColor(template_gradient_start)
                if template_gradient_end is not None and not isinstance(template_gradient_end, QColor):
                    template_gradient_end = QColor(template_gradient_end)
                bold_for_block = bool(template.get("bold", bold))
                italic_for_block = bool(template.get("italic", italic))
                underline_for_block = bool(template.get("underline", underline))
                alignment_for_block = template.get("alignment", alignment)
                direction_for_block = template.get("direction", direction)
                template_font_color = template.get("text_color")
                if template_font_color is not None and not isinstance(template_font_color, QColor):
                    template_font_color = QColor(template_font_color)

                vertical = is_vertical_block(blk, trg_lng_cd)
                block_init_font_size = int(
                    round(template.get("font_size", resolve_init_font_size(blk, max_font_size, min_font_size)))
                )
                wrapped, font_size = pyside_word_wrap(
                    translation,
                    font_family_for_block,
                    block_width,
                    block_height,
                    line_spacing_for_block,
                    outline_width_for_block,
                    bold_for_block,
                    italic_for_block,
                    underline_for_block,
                    alignment_for_block,
                    direction_for_block,
                    block_init_font_size,
                    min_font_size,
                    vertical,
                )
                if is_no_space_lang(trg_lng_cd):
                    wrapped = wrapped.replace(" ", "")

                font_color = get_smart_text_color(blk.font_color, template_font_color or setting_font_color)
                text_props = TextItemProperties(
                    text=wrapped,
                    source_text=translation,
                    font_family=font_family_for_block,
                    font_size=font_size,
                    text_color=font_color,
                    alignment=alignment_for_block,
                    line_spacing=line_spacing_for_block,
                    outline_color=outline_color_for_block,
                    outline_width=outline_width_for_block,
                    outline=outline_enabled,
                    second_outline=second_outline_for_block,
                    second_outline_color=second_outline_color_for_block,
                    second_outline_width=second_outline_width_for_block,
                    text_gradient=text_gradient_for_block,
                    text_gradient_start_color=template_gradient_start if text_gradient_for_block else None,
                    text_gradient_end_color=template_gradient_end if text_gradient_for_block else None,
                    bold=bold_for_block,
                    italic=italic_for_block,
                    underline=underline_for_block,
                    direction=direction_for_block,
                    position=position,
                    rotation=rotation,
                    scale=scale,
                    transform_origin=transform_origin,
                    width=block_width,
                    height=block_height,
                    vertical=vertical,
                    block_uid=getattr(blk, "block_uid", ""),
                )
                new_text_items_state.append(text_props.to_dict())

            if new_text_items_state:
                viewer_state["text_items_state"] = preserved_text_items + new_text_items_state
                viewer_state["push_to_stack"] = True
                state["blk_list"] = blk_list
                state["target_lang"] = target_lang
                set_target_snapshot(state, target_lang, viewer_state)
                update_render_style_overrides(state, viewer_state, overwrite=False)
                finalize_render_stage(
                    state,
                    target_lang,
                    has_runtime_patches=page_has_runtime_patches(
                        state,
                        self.main.image_patches,
                        file_path,
                    ),
                    ui_stage="render",
                )
                pipeline_state = state.setdefault("pipeline_state", {})
                completed_stages = set(pipeline_state.get("completed_stages", []) or [])
                completed_stages.add("render")
                pipeline_state["completed_stages"] = list(completed_stages)
                pipeline_state["target_lang"] = target_lang
                updated_paths.add(file_path)

        return updated_paths

    def _on_selected_render_ready(self, updated_paths: set[str], context: dict) -> None:
        if not updated_paths:
            return

        current_file = context["current_file"]
        batch_report_ctrl = getattr(self.main, "batch_report_ctrl", None)
        if batch_report_ctrl is not None:
            for file_path in updated_paths:
                batch_report_ctrl.register_batch_success(file_path)

        if current_file in updated_paths:
            self.main.blk_list = self.main.image_states.get(current_file, {}).get("blk_list", []).copy()
            if self.main.webtoon_mode:
                if context["current_page_unloaded"]:
                    reload_current_webtoon_page(self.main)
            else:
                self.main.image_ctrl.on_render_state_ready(current_file)
                self.main.image_ctrl.save_current_image_state()

        self.main.mark_project_dirty()
