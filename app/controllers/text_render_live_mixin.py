from __future__ import annotations

from modules.rendering.render import (
    TextRenderingSettings,
    manual_wrap,
)
from modules.utils.language_utils import get_language_code, get_layout_direction
from modules.utils.pipeline_config import font_selected
from modules.utils.translator_utils import format_translations
from pipeline.page_state import has_runtime_patches as page_has_runtime_patches
from pipeline.stage_state import finalize_render_stage


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

        render_blocks = list(self.main.blk_list)

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
            render_blocks,
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

    def on_render_complete(self, rendered_blocks: list):
        current_file = None
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            current_file = self.main.image_files[self.main.curr_img_idx]
            for text, font_size, blk, image_path in rendered_blocks or []:
                self.main.blk_rendered.emit(text, font_size, blk, image_path)

            state = self.main.image_states.get(current_file)
            if state is not None:
                finalize_render_stage(
                    state,
                    self.main.t_combo.currentText(),
                    has_runtime_patches=page_has_runtime_patches(
                        state,
                        self.main.image_patches,
                        current_file,
                    ),
                    ui_stage="render",
                )
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
            second_outline=self.main.second_outline_checkbox.isChecked(),
            second_outline_color=self.main.second_outline_color_button.property("selected_color"),
            second_outline_width=self.main.second_outline_width_dropdown.currentText(),
            text_gradient=self.main.text_gradient_checkbox.isChecked(),
            text_gradient_start_color=self.main.text_gradient_start_button.property("selected_color"),
            text_gradient_end_color=self.main.text_gradient_end_button.property("selected_color"),
        )
