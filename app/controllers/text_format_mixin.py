from __future__ import annotations

from PySide6 import QtCore
from PySide6.QtGui import QColor

from app.ui.canvas.text_item import TextBlockItem


class TextFormatMixin:
    def _finalize_format_edit(self):
        current_file = self._current_file_path()
        if current_file:
            self._sync_current_render_snapshot(current_file)
            self.main.stage_nav_ctrl.invalidate_for_format_edit(
                current_file,
                self._current_target_lang(),
            )
        self.main.mark_project_dirty()

    def on_font_dropdown_change(self, font_family: str):
        if self.main.curr_tblock_item and font_family:
            font_size = int(self.main.font_size_dropdown.currentText())
            self.main.curr_tblock_item.set_font(font_family, font_size)
            if not self.main.curr_tblock_item.textCursor().hasSelection():
                self._reflow_current_text_item(max_font_size=font_size)
            self._finalize_format_edit()

    def on_font_size_change(self, font_size: str):
        if self.main.curr_tblock_item and font_size:
            font_size = float(font_size)
            self.main.curr_tblock_item.set_font_size(font_size)
            if not self.main.curr_tblock_item.textCursor().hasSelection():
                self._reflow_current_text_item(max_font_size=int(round(font_size)))
            self._finalize_format_edit()

    def on_line_spacing_change(self, line_spacing: str):
        if self.main.curr_tblock_item and line_spacing:
            spacing = float(line_spacing)
            self.main.curr_tblock_item.set_line_spacing(spacing)
            if not self.main.curr_tblock_item.textCursor().hasSelection():
                self._reflow_current_text_item(max_font_size=int(round(self.main.curr_tblock_item.font_size)))
            self._finalize_format_edit()

    def on_font_color_change(self):
        font_color = self.main.get_color()
        if font_color and font_color.isValid():
            self.main.block_font_color_button.setStyleSheet(
                f"background-color: {font_color.name()}; border: none; border-radius: 5px;"
            )
            self.main.block_font_color_button.setProperty("selected_color", font_color.name())
            if self.main.curr_tblock_item:
                self.main.curr_tblock_item.set_color(font_color)
                self._finalize_format_edit()

    def left_align(self):
        if self.main.curr_tblock_item:
            self.main.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            self._finalize_format_edit()

    def center_align(self):
        if self.main.curr_tblock_item:
            self.main.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._finalize_format_edit()

    def right_align(self):
        if self.main.curr_tblock_item:
            self.main.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self._finalize_format_edit()

    def bold(self):
        if self.main.curr_tblock_item:
            state = self.main.bold_button.isChecked()
            self.main.curr_tblock_item.set_bold(state)
            self._finalize_format_edit()

    def italic(self):
        if self.main.curr_tblock_item:
            state = self.main.italic_button.isChecked()
            self.main.curr_tblock_item.set_italic(state)
            self._finalize_format_edit()

    def underline(self):
        if self.main.curr_tblock_item:
            state = self.main.underline_button.isChecked()
            self.main.curr_tblock_item.set_underline(state)
            self._finalize_format_edit()

    def _refresh_current_text_controls(self):
        if not self.main.curr_tblock_item:
            return
        try:
            self.set_values_for_blk_item(self.main.curr_tblock_item)
        except Exception:
            pass
        try:
            self.main.t_text_edit.blockSignals(True)
            self.main.t_text_edit.setPlainText(self.main.curr_tblock_item.toPlainText())
        finally:
            self.main.t_text_edit.blockSignals(False)

    def on_outline_color_change(self):
        outline_color = self.main.get_color()
        if outline_color and outline_color.isValid():
            self.main.outline_font_color_button.setStyleSheet(
                f"background-color: {outline_color.name()}; border: none; border-radius: 5px;"
            )
            self.main.outline_font_color_button.setProperty("selected_color", outline_color.name())
            outline_width = float(self.main.outline_width_dropdown.currentText())

            if self.main.curr_tblock_item and self.main.outline_checkbox.isChecked():
                self.main.curr_tblock_item.set_outline(outline_color, outline_width)
                self._finalize_format_edit()

    def on_outline_width_change(self, outline_width):
        if self.main.curr_tblock_item and self.main.outline_checkbox.isChecked():
            outline_width = float(self.main.outline_width_dropdown.currentText())
            color_str = self.main.outline_font_color_button.property("selected_color")
            color = QColor(color_str)
            self.main.curr_tblock_item.set_outline(color, outline_width)
            self._finalize_format_edit()

    def toggle_outline_settings(self, state):
        enabled = state == 2
        if self.main.curr_tblock_item:
            if not enabled:
                self.main.curr_tblock_item.set_outline(None, None)
                self._finalize_format_edit()
            else:
                outline_width = float(self.main.outline_width_dropdown.currentText())
                color_str = self.main.outline_font_color_button.property("selected_color")
                color = QColor(color_str)
                self.main.curr_tblock_item.set_outline(color, outline_width)
                self._finalize_format_edit()

    def block_text_item_widgets(self, widgets):
        for widget in widgets:
            widget.blockSignals(True)

        self.main.bold_button.clicked.disconnect(self.bold)
        self.main.italic_button.clicked.disconnect(self.italic)
        self.main.underline_button.clicked.disconnect(self.underline)

        self.main.alignment_tool_group.get_button_group().buttons()[0].clicked.disconnect(self.left_align)
        self.main.alignment_tool_group.get_button_group().buttons()[1].clicked.disconnect(self.center_align)
        self.main.alignment_tool_group.get_button_group().buttons()[2].clicked.disconnect(self.right_align)

    def unblock_text_item_widgets(self, widgets):
        for widget in widgets:
            widget.blockSignals(False)

        self.main.bold_button.clicked.connect(self.bold)
        self.main.italic_button.clicked.connect(self.italic)
        self.main.underline_button.clicked.connect(self.underline)

        self.main.alignment_tool_group.get_button_group().buttons()[0].clicked.connect(self.left_align)
        self.main.alignment_tool_group.get_button_group().buttons()[1].clicked.connect(self.center_align)
        self.main.alignment_tool_group.get_button_group().buttons()[2].clicked.connect(self.right_align)

    def set_values_for_blk_item(self, text_item: TextBlockItem):
        self.block_text_item_widgets(self.widgets_to_block)

        try:
            self.main.font_dropdown.setCurrentText(text_item.font_family)
            self.main.font_size_dropdown.setCurrentText(str(int(text_item.font_size)))
            self.main.line_spacing_dropdown.setCurrentText(str(text_item.line_spacing))

            self.main.block_font_color_button.setStyleSheet(
                f"background-color: {text_item.text_color.name()}; border: none; border-radius: 5px;"
            )
            self.main.block_font_color_button.setProperty("selected_color", text_item.text_color.name())

            if text_item.outline_color is not None:
                self.main.outline_font_color_button.setStyleSheet(
                    f"background-color: {text_item.outline_color.name()}; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty("selected_color", text_item.outline_color.name())
            else:
                self.main.outline_font_color_button.setStyleSheet(
                    "background-color: white; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty("selected_color", "#ffffff")

            self.main.outline_width_dropdown.setCurrentText(str(text_item.outline_width))
            self.main.outline_checkbox.setChecked(text_item.outline)

            self.main.bold_button.setChecked(text_item.bold)
            self.main.italic_button.setChecked(text_item.italic)
            self.main.underline_button.setChecked(text_item.underline)

            alignment_to_button = {
                QtCore.Qt.AlignmentFlag.AlignLeft: 0,
                QtCore.Qt.AlignmentFlag.AlignCenter: 1,
                QtCore.Qt.AlignmentFlag.AlignRight: 2,
            }

            alignment = text_item.alignment
            button_group = self.main.alignment_tool_group.get_button_group()

            if alignment in alignment_to_button:
                button_index = alignment_to_button[alignment]
                button_group.buttons()[button_index].setChecked(True)

        finally:
            self.unblock_text_item_widgets(self.widgets_to_block)

    def set_values_from_highlight(self, item_highlighted=None):
        self.block_text_item_widgets(self.widgets_to_block)

        font_family = item_highlighted["font_family"]
        font_size = item_highlighted["font_size"]
        text_color = item_highlighted["text_color"]

        outline_color = item_highlighted["outline_color"]
        outline_width = item_highlighted["outline_width"]
        outline = item_highlighted["outline"]

        bold = item_highlighted["bold"]
        italic = item_highlighted["italic"]
        underline = item_highlighted["underline"]

        alignment = item_highlighted["alignment"]

        try:
            self.main.font_dropdown.setCurrentText(font_family) if font_family else None
            self.main.font_size_dropdown.setCurrentText(str(int(font_size))) if font_size else None

            if text_color is not None:
                self.main.block_font_color_button.setStyleSheet(
                    f"background-color: {text_color}; border: none; border-radius: 5px;"
                )
                self.main.block_font_color_button.setProperty("selected_color", text_color)

            if outline_color is not None:
                self.main.outline_font_color_button.setStyleSheet(
                    f"background-color: {outline_color}; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty("selected_color", outline_color)
            else:
                self.main.outline_font_color_button.setStyleSheet(
                    "background-color: white; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty("selected_color", "#ffffff")

            self.main.outline_width_dropdown.setCurrentText(str(outline_width)) if outline_width else None
            self.main.outline_checkbox.setChecked(outline)

            self.main.bold_button.setChecked(bold)
            self.main.italic_button.setChecked(italic)
            self.main.underline_button.setChecked(underline)

            alignment_to_button = {
                QtCore.Qt.AlignmentFlag.AlignLeft: 0,
                QtCore.Qt.AlignmentFlag.AlignCenter: 1,
                QtCore.Qt.AlignmentFlag.AlignRight: 2,
            }

            button_group = self.main.alignment_tool_group.get_button_group()

            if alignment in alignment_to_button:
                button_index = alignment_to_button[alignment]
                button_group.buttons()[button_index].setChecked(True)

        finally:
            self.unblock_text_item_widgets(self.widgets_to_block)
