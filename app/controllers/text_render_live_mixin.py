from __future__ import annotations

import numpy as np

from modules.rendering.render import (
    TextRenderingSettings,
    manual_wrap,
)
from modules.utils.language_utils import get_language_code, get_layout_direction
from modules.utils.pipeline_config import font_selected
from modules.utils.translator_utils import format_translations


class TextRenderLiveMixin:
    def _render_current_page(self) -> None:
        self.main.set_tool(None)
        if not font_selected(self.main):
            return
        self.clear_text_edits()
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()

        for item in self.main.image_viewer.text_items:
            if item not in self.main.image_viewer._scene.items():
                self.main.image_viewer._scene.addItem(item)

        existing_text_item_uids = {
            str(getattr(item, "block_uid", "") or "")
            for item in self.main.image_viewer.text_items
            if getattr(item, "block_uid", "")
        }
        existing_text_item_keys = {
            (int(item.pos().x()), int(item.pos().y()), float(item.rotation()))
            for item in self.main.image_viewer.text_items
            if not getattr(item, "block_uid", "")
        }

        new_blocks = []
        for blk in self.main.blk_list:
            blk_uid = str(getattr(blk, "block_uid", "") or "")
            blk_key = (int(blk.xyxy[0]), int(blk.xyxy[1]), float(blk.angle))
            if blk_uid and blk_uid in existing_text_item_uids:
                continue
            if not blk_uid and blk_key in existing_text_item_keys:
                continue
            new_blocks.append(blk)

        self.main.image_viewer.clear_rectangles()
        self.main.curr_tblock = None
        self.main.curr_tblock_item = None

        render_settings = self.render_settings()
        upper = render_settings.upper_case

        line_spacing = float(self.main.line_spacing_dropdown.currentText())
        font_family = self.main.font_dropdown.currentText()
        outline_width = float(self.main.outline_width_dropdown.currentText())

        bold = self.main.bold_button.isChecked()
        italic = self.main.italic_button.isChecked()
        underline = self.main.underline_button.isChecked()

        target_lang = self.main.t_combo.currentText()
        target_lang_en = self.main.lang_mapping.get(target_lang, None)
        trg_lng_cd = get_language_code(target_lang_en)

        if self._manual_render_macro_open:
            try:
                stack = self.main.undo_group.activeStack()
                if stack is not None:
                    stack.endMacro()
            except Exception:
                pass
            self._manual_render_macro_open = False

        stack = self.main.undo_group.activeStack()
        if stack is not None:
            stack.beginMacro("text_items_rendered")
            self._manual_render_macro_open = True

        self.main.run_threaded(
            lambda: format_translations(self.main.blk_list, trg_lng_cd, upper_case=upper)
        )

        min_font_size = self.main.settings_page.get_min_font_size()
        max_font_size = self.main.settings_page.get_max_font_size()

        align_id = self.main.alignment_tool_group.get_dayu_checked()
        alignment = self.main.button_to_alignment[align_id]
        direction = render_settings.direction

        image_path = ""
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            image_path = self.main.image_files[self.main.curr_img_idx]

        def on_manual_render_error(error_tuple: tuple) -> None:
            if self._manual_render_macro_open:
                stack = self.main.undo_group.activeStack()
                if stack is not None:
                    try:
                        stack.endMacro()
                    except Exception:
                        pass
                self._manual_render_macro_open = False
            self.main.default_error_handler(error_tuple)

        self.main.run_threaded(
            manual_wrap,
            self.on_render_complete,
            on_manual_render_error,
            None,
            self.main,
            new_blocks,
            image_path,
            font_family,
            line_spacing,
            outline_width,
            bold,
            italic,
            underline,
            alignment,
            direction,
            max_font_size,
            min_font_size,
        )

    def on_render_complete(self, rendered_image: np.ndarray):
        current_file = None
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            current_file = self.main.image_files[self.main.curr_img_idx]
            state = self.main.image_states.get(current_file)
            if state is not None:
                state["target_lang"] = self.main.t_combo.currentText()
                pipeline_state = state.setdefault("pipeline_state", {})
                completed_stages = set(pipeline_state.get("completed_stages", []) or [])
                completed_stages.add("render")
                pipeline_state["completed_stages"] = list(completed_stages)
                pipeline_state["target_lang"] = self.main.t_combo.currentText()
        self._finalize_manual_render(current_file)

    def render_settings(self) -> TextRenderingSettings:
        target_lang = self.main.lang_mapping.get(self.main.t_combo.currentText(), None)
        direction = get_layout_direction(target_lang)

        return TextRenderingSettings(
            alignment_id=self.main.alignment_tool_group.get_dayu_checked(),
            font_family=self.main.font_dropdown.currentText(),
            min_font_size=int(self.main.settings_page.ui.min_font_spinbox.value()),
            max_font_size=int(self.main.settings_page.ui.max_font_spinbox.value()),
            color=self.main.block_font_color_button.property("selected_color"),
            upper_case=self.main.settings_page.ui.uppercase_checkbox.isChecked(),
            outline=self.main.outline_checkbox.isChecked(),
            outline_color=self.main.outline_font_color_button.property("selected_color"),
            outline_width=self.main.outline_width_dropdown.currentText(),
            bold=self.main.bold_button.isChecked(),
            italic=self.main.italic_button.isChecked(),
            underline=self.main.underline_button.isChecked(),
            line_spacing=self.main.line_spacing_dropdown.currentText(),
            direction=direction,
        )
