from __future__ import annotations

from PySide6.QtGui import QColor

from app.controllers.workflow_support import prepare_multi_page_context, reload_current_webtoon_page
from app.ui.canvas.text.text_item_properties import TextItemProperties
from modules.rendering.render import is_vertical_block, pyside_word_wrap, resolve_init_font_size
from modules.utils.image_utils import get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.pipeline_config import font_selected
from modules.utils.translator_utils import format_translations


class TextRenderBatchMixin:
    def _render_selected_pages(self, selected_paths: list[str]) -> None:
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
            existing_uids = {
                str(item.get("block_uid", ""))
                for item in existing_text_items
                if isinstance(item, dict) and item.get("block_uid")
            }
            existing_legacy_keys = {
                (
                    int(item.get("position", (0, 0))[0]),
                    int(item.get("position", (0, 0))[1]),
                    float(item.get("rotation", 0)),
                )
                for item in existing_text_items
                if isinstance(item, dict) and not item.get("block_uid")
            }

            new_text_items_state = []
            for blk in blk_list:
                blk_uid = str(getattr(blk, "block_uid", "") or "")
                blk_key = (int(blk.xyxy[0]), int(blk.xyxy[1]), float(blk.angle))
                if blk_uid and blk_uid in existing_uids:
                    continue
                if not blk_uid and blk_key in existing_legacy_keys:
                    continue

                x1, y1, block_width, block_height = blk.xywh
                translation = blk.translation or blk.text
                if not translation or len(translation) == 1:
                    continue

                vertical = is_vertical_block(blk, trg_lng_cd)
                block_init_font_size = resolve_init_font_size(blk, max_font_size, min_font_size)
                wrapped, font_size = pyside_word_wrap(
                    translation,
                    font_family,
                    block_width,
                    block_height,
                    line_spacing,
                    outline_width,
                    bold,
                    italic,
                    underline,
                    alignment,
                    direction,
                    block_init_font_size,
                    min_font_size,
                    vertical,
                )
                if is_no_space_lang(trg_lng_cd):
                    wrapped = wrapped.replace(" ", "")

                font_color = get_smart_text_color(blk.font_color, setting_font_color)
                text_props = TextItemProperties(
                    text=wrapped,
                    source_text=translation,
                    font_family=font_family,
                    font_size=font_size,
                    text_color=font_color,
                    alignment=alignment,
                    line_spacing=line_spacing,
                    outline_color=outline_color,
                    outline_width=outline_width,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    direction=direction,
                    position=(x1, y1),
                    rotation=blk.angle,
                    scale=1.0,
                    transform_origin=blk.tr_origin_point if blk.tr_origin_point else (0, 0),
                    width=block_width,
                    height=block_height,
                    vertical=vertical,
                    block_uid=getattr(blk, "block_uid", ""),
                )
                new_text_items_state.append(text_props.to_dict())

            if new_text_items_state:
                viewer_state["text_items_state"] = existing_text_items + new_text_items_state
                viewer_state["push_to_stack"] = True
                state["blk_list"] = blk_list
                state["target_lang"] = target_lang
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
