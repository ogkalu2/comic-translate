from __future__ import annotations

import os
import copy
import numpy as np
from typing import TYPE_CHECKING

from PySide6 import QtCore
from PySide6.QtGui import QColor, QTextCursor

from app.ui.commands.textformat import TextFormatCommand
from app.ui.commands.box import AddTextItemCommand, ResizeBlocksCommand
from app.ui.commands.text_edit import TextEditCommand
from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.text.text_item_properties import TextItemProperties

from modules.utils.textblock import TextBlock
from modules.rendering.render import TextRenderingSettings, manual_wrap, is_vertical_block, pyside_word_wrap
from modules.utils.pipeline_config import font_selected
from modules.utils.language_utils import get_language_code, get_layout_direction, is_no_space_lang
from modules.utils.image_utils import get_smart_text_color
from modules.utils.common_utils import is_close
from modules.utils.translator_utils import format_translations

if TYPE_CHECKING:
    from controller import ComicTranslate

class TextController:
    def __init__(self, main: ComicTranslate):
        self.main = main

        # List of widgets to block signals for during manual rendering
        self.widgets_to_block = [
            self.main.font_dropdown,
            self.main.font_size_dropdown,
            self.main.line_spacing_dropdown,
            self.main.block_font_color_button,
            self.main.outline_font_color_button,
            self.main.outline_width_dropdown,
            self.main.outline_checkbox
        ]
        self._text_change_timer = QtCore.QTimer(self.main)
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(400)
        self._text_change_timer.timeout.connect(self._commit_pending_text_command)
        self._pending_text_command = None
        self._last_item_text = {}
        self._last_item_html = {}
        self._suspend_text_command = False
        self._is_updating_from_edit = False

    def connect_text_item_signals(self, text_item: TextBlockItem, force_reconnect: bool = False):
        if getattr(text_item, "_ct_signals_connected", False) and not force_reconnect:
            return

        if force_reconnect:
            try:
                text_item.item_selected.disconnect(self.on_text_item_selected)
            except (TypeError, RuntimeError):
                pass
            try:
                text_item.item_deselected.disconnect(self.on_text_item_deselected)
            except (TypeError, RuntimeError):
                pass
            if hasattr(text_item, "_ct_text_changed_slot"):
                try:
                    text_item.text_changed.disconnect(text_item._ct_text_changed_slot)
                except (TypeError, RuntimeError):
                    pass
            try:
                text_item.text_highlighted.disconnect(self.set_values_from_highlight)
            except (TypeError, RuntimeError):
                pass
            try:
                text_item.change_undo.disconnect(self.main.rect_item_ctrl.rect_change_undo)
            except (TypeError, RuntimeError):
                pass

        if not hasattr(text_item, "_ct_text_changed_slot"):
            text_item._ct_text_changed_slot = (
                lambda text, ti=text_item: self.update_text_block_from_item(ti, text)
            )

        text_item.item_selected.connect(self.on_text_item_selected)
        text_item.item_deselected.connect(self.on_text_item_deselected)
        text_item.text_changed.connect(text_item._ct_text_changed_slot)
        text_item.text_highlighted.connect(self.set_values_from_highlight)
        text_item.change_undo.connect(self.main.rect_item_ctrl.rect_change_undo)
        self._last_item_text[text_item] = text_item.toPlainText()
        self._last_item_html[text_item] = text_item.document().toHtml()
        text_item._ct_signals_connected = True

    def clear_text_edits(self):
        self.main.curr_tblock = None
        self.main.curr_tblock_item = None
        self.main.s_text_edit.clear()
        self.main.t_text_edit.clear()

    def on_blk_rendered(self, text: str, font_size: int, blk: TextBlock, image_path: str):
        if not self.main.webtoon_mode:
            if self.main.curr_img_idx < 0 or self.main.curr_img_idx >= len(self.main.image_files):
                return
            current_file = self.main.image_files[self.main.curr_img_idx]
            if os.path.normcase(current_file) != os.path.normcase(image_path):
                return

        if not self.main.image_viewer.hasPhoto():
            print("No main image to add to.")
            return

        target_lang = self.main.lang_mapping.get(self.main.t_combo.currentText(), None)
        trg_lng_cd = get_language_code(target_lang)
        if is_no_space_lang(trg_lng_cd):
            text = text.replace(' ', '')

        render_settings = self.render_settings()
        font_family = render_settings.font_family
        text_color_str = render_settings.color
        text_color = QColor(text_color_str)

        # Smart Color Override
        text_color = get_smart_text_color(blk.font_color, text_color)

        id = render_settings.alignment_id
        alignment = self.main.button_to_alignment[id]
        line_spacing = float(render_settings.line_spacing)
        outline_color_str = render_settings.outline_color
        outline_color = QColor(outline_color_str) if self.main.outline_checkbox.isChecked() else None
        outline_width = float(render_settings.outline_width)
        bold = render_settings.bold
        italic = render_settings.italic
        underline = render_settings.underline
        direction = render_settings.direction
        vertical = is_vertical_block(blk, trg_lng_cd)

        properties = TextItemProperties(
            text=text,
            font_family=font_family,
            font_size=font_size,
            text_color=text_color,
            alignment=alignment,
            line_spacing=line_spacing,
            outline_color=outline_color,
            outline_width=outline_width,
            bold=bold,
            italic=italic,
            underline=underline,
            direction=direction,
            position=(blk.xyxy[0], blk.xyxy[1]),
            rotation=blk.angle,
            vertical=vertical,
        )
        
        text_item = self.main.image_viewer.add_text_item(properties)
        text_item.set_plain_text(text)

        command = AddTextItemCommand(self.main, text_item)
        self.main.push_command(command)

    def on_text_item_selected(self, text_item: TextBlockItem):
        self._commit_pending_text_command()
        self.main.curr_tblock_item = text_item
        self._last_item_text[text_item] = text_item.toPlainText()
        self._last_item_html[text_item] = text_item.document().toHtml()

        x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
        rotation = text_item.rotation()

        self.main.curr_tblock = next(
            (
            blk for blk in self.main.blk_list
            if is_close(blk.xyxy[0], x1, 5) and is_close(blk.xyxy[1], y1, 5)
            and is_close(blk.angle, rotation, 1)
            ),
            None
        )

        # Update both s_text_edit and t_text_edit
        if self.main.curr_tblock:
            self.main.s_text_edit.blockSignals(True)
            self.main.s_text_edit.setPlainText(self.main.curr_tblock.text)
            self.main.s_text_edit.blockSignals(False)

        self.main.t_text_edit.blockSignals(True)
        self.main.t_text_edit.setPlainText(text_item.toPlainText())
        self.main.t_text_edit.blockSignals(False)

        self.set_values_for_blk_item(text_item)

    def on_text_item_deselected(self):
        self._commit_pending_text_command()
        self.clear_text_edits()

    def update_text_block(self):
        if self.main.curr_tblock:
            self.main.curr_tblock.text = self.main.s_text_edit.toPlainText()
            self.main.curr_tblock.translation = self.main.t_text_edit.toPlainText()
            self.main.mark_project_dirty()

    def update_text_block_from_edit(self):
        self._is_updating_from_edit = True
        try:
            new_text = self.main.t_text_edit.toPlainText()
            old_translation = None
            old_item_text = None
            if self.main.curr_tblock:
                old_translation = self.main.curr_tblock.translation
                self.main.curr_tblock.translation = new_text

            if self.main.curr_tblock_item and self.main.curr_tblock_item in self.main.image_viewer._scene.items():
                old_item_text = self.main.curr_tblock_item.toPlainText()
                cursor_position = self.main.t_text_edit.textCursor().position()
                self._apply_text_item_text_delta(self.main.curr_tblock_item, new_text)

                # Restore cursor position
                cursor = self.main.t_text_edit.textCursor()
                cursor.setPosition(cursor_position)
                self.main.t_text_edit.setTextCursor(cursor)
            if (old_translation is None or old_translation == new_text) and (
                old_item_text is None or old_item_text == new_text
            ):
                return
        finally:
            self._is_updating_from_edit = False

    def update_text_block_from_item(self, text_item: TextBlockItem, new_text: str):
        if self._suspend_text_command:
            return
        blk = self._find_text_block_for_item(text_item)
        if blk:
            blk.translation = new_text

        if self.main.curr_tblock_item == text_item and not self._is_updating_from_edit:
            self.main.curr_tblock = blk
            self.main.t_text_edit.blockSignals(True)
            self.main.t_text_edit.setPlainText(new_text)
            self.main.t_text_edit.blockSignals(False)

        self._schedule_text_change_command(text_item, new_text, blk)

    def _apply_text_item_text_delta(self, text_item: TextBlockItem, new_text: str):
        old_text = text_item.toPlainText()
        if old_text == new_text:
            return

        prefix = 0
        max_prefix = min(len(old_text), len(new_text))
        while prefix < max_prefix and old_text[prefix] == new_text[prefix]:
            prefix += 1

        suffix = 0
        max_suffix = min(len(old_text) - prefix, len(new_text) - prefix)
        while suffix < max_suffix and old_text[-(suffix + 1)] == new_text[-(suffix + 1)]:
            suffix += 1

        old_mid_end = len(old_text) - suffix
        new_mid_end = len(new_text) - suffix
        old_mid = old_text[prefix:old_mid_end]
        new_mid = new_text[prefix:new_mid_end]

        doc = text_item.document()
        cursor = QTextCursor(doc)
        insert_format = None

        if old_text:
            if prefix < len(old_text):
                cursor.setPosition(prefix)
                insert_format = cursor.charFormat()
            elif prefix > 0:
                cursor.setPosition(prefix - 1)
                insert_format = cursor.charFormat()

        cursor.beginEditBlock()
        if old_mid:
            cursor.setPosition(prefix)
            cursor.setPosition(prefix + len(old_mid), QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        if new_mid:
            cursor.setPosition(prefix)
            if insert_format is not None:
                cursor.setCharFormat(insert_format)
            cursor.insertText(new_mid)
        cursor.endEditBlock()

    def save_src_trg(self):
        source_lang = self.main.s_combo.currentText()
        target_lang = self.main.t_combo.currentText()
        
        if self.main.curr_img_idx >= 0:
            current_file = self.main.image_files[self.main.curr_img_idx]
            self.main.image_states[current_file]['source_lang'] = source_lang
            self.main.image_states[current_file]['target_lang'] = target_lang

        target_en = self.main.lang_mapping.get(target_lang, None)
        t_direction = get_layout_direction(target_en)
        t_text_option = self.main.t_text_edit.document().defaultTextOption()
        t_text_option.setTextDirection(t_direction)
        self.main.t_text_edit.document().setDefaultTextOption(t_text_option)

        if self.main.curr_img_idx >= 0:
            self.main.mark_project_dirty()

    def set_src_trg_all(self):
        source_lang = self.main.s_combo.currentText()
        target_lang = self.main.t_combo.currentText()
        for image_path in self.main.image_files:
            self.main.image_states[image_path]['source_lang'] = source_lang
            self.main.image_states[image_path]['target_lang'] = target_lang
        if self.main.image_files:
            self.main.mark_project_dirty()

    def change_all_blocks_size(self, diff: int):
        if len(self.main.blk_list) == 0:
            return
        command = ResizeBlocksCommand(self.main, self.main.blk_list, diff)
        stack = self.main.undo_group.activeStack()
        if stack:
            stack.push(command)
        else:
            command.redo()
            self.main.mark_project_dirty()

    def _find_text_block_for_item(self, text_item: TextBlockItem) -> TextBlock | None:
        if not text_item:
            return None

        x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
        rotation = text_item.rotation()

        return next(
            (
                blk for blk in self.main.blk_list
                if is_close(blk.xyxy[0], x1, 5)
                and is_close(blk.xyxy[1], y1, 5)
                and is_close(blk.angle, rotation, 1)
            ),
            None
        )

    def _schedule_text_change_command(self, text_item: TextBlockItem, new_text: str, blk: TextBlock | None):
        if self._suspend_text_command:
            return

        pending = self._pending_text_command
        if pending and pending['item'] is not text_item:
            self._commit_pending_text_command()
            pending = None

        new_html = text_item.document().toHtml()
        if pending is None:
            old_text = self._last_item_text.get(text_item, new_text)
            old_html = self._last_item_html.get(text_item, new_html)
            if old_text == new_text:
                self._last_item_text[text_item] = new_text
                self._last_item_html[text_item] = new_html
                return
            pending = {
                'item': text_item,
                'old_text': old_text,
                'new_text': new_text,
                'old_html': old_html,
                'new_html': new_html,
                'blk': blk,
            }
            self._pending_text_command = pending
        else:
            pending['new_text'] = new_text
            pending['new_html'] = new_html
            pending['blk'] = blk

        self._last_item_text[text_item] = new_text
        self._last_item_html[text_item] = new_html
        self._text_change_timer.start()

    def _commit_pending_text_command(self):
        if not self._pending_text_command:
            return
        self._text_change_timer.stop()
        pending = self._pending_text_command
        self._pending_text_command = None

        if pending['old_text'] == pending['new_text']:
            return

        command = TextEditCommand(
            self.main,
            pending['item'],
            pending['old_text'],
            pending['new_text'],
            old_html=pending.get('old_html'),
            new_html=pending.get('new_html'),
            blk=pending['blk']
        )
        stack = self.main.undo_group.activeStack()
        if stack:
            stack.push(command)
        else:
            command.redo()
            self.main.mark_project_dirty()

    def apply_text_from_command(self, text_item: TextBlockItem, text: str,
                                html: str | None = None, blk: TextBlock | None = None):
        self._suspend_text_command = True
        try:
            if text_item and text_item in self.main.image_viewer._scene.items():
                if html is not None:
                    if text_item.document().toHtml() != html:
                        text_item.document().setHtml(html)
                elif text_item.toPlainText() != text:
                    text_item.set_plain_text(text)
            if blk is None:
                blk = self._find_text_block_for_item(text_item)
            if blk:
                blk.translation = text
            if self.main.curr_tblock_item == text_item:
                self.main.curr_tblock = blk
                # Only update if the text is actually different to avoid cursor reset
                if self.main.t_text_edit.toPlainText() != text:
                    self.main.t_text_edit.blockSignals(True)
                    self.main.t_text_edit.setPlainText(text)
                    self.main.t_text_edit.blockSignals(False)
        finally:
            self._suspend_text_command = False
        if text_item:
            self._last_item_text[text_item] = text
            self._last_item_html[text_item] = text_item.document().toHtml()

    # Formatting actions
    def on_font_dropdown_change(self, font_family: str):
        if self.main.curr_tblock_item and font_family:
            old_item = copy.copy(self.main.curr_tblock_item)
            font_size = int(self.main.font_size_dropdown.currentText())
            self.main.curr_tblock_item.set_font(font_family, font_size)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def on_font_size_change(self, font_size: str):
        if self.main.curr_tblock_item and font_size:
            old_item = copy.copy(self.main.curr_tblock_item)
            font_size = float(font_size)
            self.main.curr_tblock_item.set_font_size(font_size)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def on_line_spacing_change(self, line_spacing: str):
        if self.main.curr_tblock_item and line_spacing:
            old_item = copy.copy(self.main.curr_tblock_item)
            spacing = float(line_spacing)
            self.main.curr_tblock_item.set_line_spacing(spacing)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def on_font_color_change(self):
        font_color = self.main.get_color()
        if font_color and font_color.isValid():
            self.main.block_font_color_button.setStyleSheet(
                f"background-color: {font_color.name()}; border: none; border-radius: 5px;"
            )
            self.main.block_font_color_button.setProperty('selected_color', font_color.name())
            if self.main.curr_tblock_item:
                old_item = copy.copy(self.main.curr_tblock_item)
                self.main.curr_tblock_item.set_color(font_color)

                command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
                self.main.push_command(command)

    def left_align(self):
        if self.main.curr_tblock_item:
            old_item = copy.copy(self.main.curr_tblock_item)
            self.main.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignLeft)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def center_align(self):
        if self.main.curr_tblock_item:
            old_item = copy.copy(self.main.curr_tblock_item)
            self.main.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def right_align(self):
        if self.main.curr_tblock_item:
            old_item = copy.copy(self.main.curr_tblock_item)
            self.main.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignRight)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def bold(self):
        if self.main.curr_tblock_item:
            old_item = copy.copy(self.main.curr_tblock_item)
            state = self.main.bold_button.isChecked()
            self.main.curr_tblock_item.set_bold(state)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def italic(self):
        if self.main.curr_tblock_item:
            old_item = copy.copy(self.main.curr_tblock_item)
            state = self.main.italic_button.isChecked()
            self.main.curr_tblock_item.set_italic(state)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def underline(self):
        if self.main.curr_tblock_item:
            old_item = copy.copy(self.main.curr_tblock_item)
            state = self.main.underline_button.isChecked()
            self.main.curr_tblock_item.set_underline(state)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def on_outline_color_change(self):
        outline_color = self.main.get_color()
        if outline_color and outline_color.isValid():
            self.main.outline_font_color_button.setStyleSheet(
                f"background-color: {outline_color.name()}; border: none; border-radius: 5px;"
            )
            self.main.outline_font_color_button.setProperty('selected_color', outline_color.name())
            outline_width = float(self.main.outline_width_dropdown.currentText())

            if self.main.curr_tblock_item and self.main.outline_checkbox.isChecked():
                old_item = copy.copy(self.main.curr_tblock_item)
                self.main.curr_tblock_item.set_outline(outline_color, outline_width)

                command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
                self.main.push_command(command)

    def on_outline_width_change(self, outline_width):
        if self.main.curr_tblock_item and self.main.outline_checkbox.isChecked():
            old_item = copy.copy(self.main.curr_tblock_item)
            outline_width = float(self.main.outline_width_dropdown.currentText())
            color_str = self.main.outline_font_color_button.property('selected_color')
            color = QColor(color_str)
            self.main.curr_tblock_item.set_outline(color, outline_width)

            command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
            self.main.push_command(command)

    def toggle_outline_settings(self, state):
        enabled = True if state == 2 else False
        if self.main.curr_tblock_item:
            if not enabled:
                self.main.curr_tblock_item.set_outline(None, None)
            else:
                old_item = copy.copy(self.main.curr_tblock_item)
                outline_width = float(self.main.outline_width_dropdown.currentText())
                color_str = self.main.outline_font_color_button.property('selected_color')
                color = QColor(color_str)
                self.main.curr_tblock_item.set_outline(color, outline_width)

                command = TextFormatCommand(self.main.image_viewer, old_item, self.main.curr_tblock_item)
                self.main.push_command(command)

    # Widget helpers
    def block_text_item_widgets(self, widgets):
        # Block signals
        for widget in widgets:
            widget.blockSignals(True)

        # Block Signals is buggy for these, so use disconnect/connect
        self.main.bold_button.clicked.disconnect(self.bold)
        self.main.italic_button.clicked.disconnect(self.italic)
        self.main.underline_button.clicked.disconnect(self.underline)

        self.main.alignment_tool_group.get_button_group().buttons()[0].clicked.disconnect(self.left_align)
        self.main.alignment_tool_group.get_button_group().buttons()[1].clicked.disconnect(self.center_align)
        self.main.alignment_tool_group.get_button_group().buttons()[2].clicked.disconnect(self.right_align)

    def unblock_text_item_widgets(self, widgets):
        # Unblock signals
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
            # Set values
            self.main.font_dropdown.setCurrentText(text_item.font_family)
            self.main.font_size_dropdown.setCurrentText(str(int(text_item.font_size)))

            self.main.line_spacing_dropdown.setCurrentText(str(text_item.line_spacing))

            self.main.block_font_color_button.setStyleSheet(
                f"background-color: {text_item.text_color.name()}; border: none; border-radius: 5px;"
            )
            self.main.block_font_color_button.setProperty('selected_color', text_item.text_color.name())

            if text_item.outline_color is not None:
                self.main.outline_font_color_button.setStyleSheet(
                    f"background-color: {text_item.outline_color.name()}; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty('selected_color', text_item.outline_color.name())
            else:
                self.main.outline_font_color_button.setStyleSheet(
                    "background-color: white; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty('selected_color', '#ffffff')

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

    def set_values_from_highlight(self, item_highlighted = None):

        self.block_text_item_widgets(self.widgets_to_block)

        # Attributes
        font_family = item_highlighted['font_family']
        font_size = item_highlighted['font_size']
        text_color =  item_highlighted['text_color']

        outline_color = item_highlighted['outline_color']
        outline_width =  item_highlighted['outline_width']
        outline = item_highlighted['outline']

        bold = item_highlighted['bold']
        italic =  item_highlighted['italic']
        underline = item_highlighted['underline']

        alignment = item_highlighted['alignment']

        try:
            # Set values
            self.main.font_dropdown.setCurrentText(font_family) if font_family else None
            self.main.font_size_dropdown.setCurrentText(str(int(font_size))) if font_size else None

            if text_color is not None:
                self.main.block_font_color_button.setStyleSheet(
                    f"background-color: {text_color}; border: none; border-radius: 5px;"
                )
                self.main.block_font_color_button.setProperty('selected_color', text_color)

            if outline_color is not None:
                self.main.outline_font_color_button.setStyleSheet(
                    f"background-color: {outline_color}; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty('selected_color', outline_color)
            else:
                self.main.outline_font_color_button.setStyleSheet(
                    "background-color: white; border: none; border-radius: 5px;"
                )
                self.main.outline_font_color_button.setProperty('selected_color', '#ffffff')

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

    # Rendering
    def render_text(self):
        selected_paths = self.main.get_selected_page_paths()
        if self.main.image_viewer.hasPhoto() and len(selected_paths) > 1:
            self.main.set_tool(None)
            if not font_selected(self.main):
                return
            self.clear_text_edits()
            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()

            context = self.main.manual_workflow_ctrl._prepare_multi_page_context(selected_paths)
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
            outline_color = (
                QColor(render_settings.outline_color)
                if render_settings.outline
                else None
            )

            def render_selected_pages() -> set[str]:
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
                    existing_keys = {
                        (
                            int(item.get("position", (0, 0))[0]),
                            int(item.get("position", (0, 0))[1]),
                            float(item.get("rotation", 0)),
                        )
                        for item in existing_text_items
                    }

                    new_text_items_state = []
                    for blk in blk_list:
                        blk_key = (int(blk.xyxy[0]), int(blk.xyxy[1]), float(blk.angle))
                        if blk_key in existing_keys:
                            continue

                        x1, y1, width, height = blk.xywh
                        translation = blk.translation
                        if not translation or len(translation) == 1:
                            continue

                        vertical = is_vertical_block(blk, trg_lng_cd)
                        wrapped, font_size = pyside_word_wrap(
                            translation,
                            font_family,
                            width,
                            height,
                            line_spacing,
                            outline_width,
                            bold,
                            italic,
                            underline,
                            alignment,
                            direction,
                            max_font_size,
                            min_font_size,
                            vertical,
                        )
                        if is_no_space_lang(trg_lng_cd):
                            wrapped = wrapped.replace(" ", "")

                        font_color = get_smart_text_color(blk.font_color, setting_font_color)
                        text_props = TextItemProperties(
                            text=wrapped,
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
                            width=width,
                            vertical=vertical,
                        )
                        new_text_items_state.append(text_props.to_dict())

                    if new_text_items_state:
                        viewer_state["text_items_state"] = existing_text_items + new_text_items_state
                        viewer_state["push_to_stack"] = True
                        state["blk_list"] = blk_list
                        updated_paths.add(file_path)

                return updated_paths

            def on_selected_render_ready(updated_paths: set[str]) -> None:
                if not updated_paths:
                    return

                current_file = context["current_file"]
                if current_file in updated_paths:
                    self.main.blk_list = self.main.image_states.get(current_file, {}).get("blk_list", []).copy()
                    if self.main.webtoon_mode:
                        if context["current_page_unloaded"]:
                            self.main.manual_workflow_ctrl._reload_current_webtoon_page()
                    else:
                        self.main.image_ctrl.on_render_state_ready(current_file)

                self.main.mark_project_dirty()

            self.main.run_threaded(
                render_selected_pages,
                on_selected_render_ready,
                self.main.default_error_handler,
                self.main.on_manual_finished,
            )
            return

        if self.main.image_viewer.hasPhoto() and self.main.blk_list:
            self.main.set_tool(None)
            if not font_selected(self.main):
                return
            self.clear_text_edits()
            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()

            # Add items to the scene if they're not already present
            for item in self.main.image_viewer.text_items:
                if item not in self.main.image_viewer._scene.items():
                    self.main.image_viewer._scene.addItem(item)

            # Create a dictionary to map text items to their positions and rotations
            existing_text_items = {item: (int(item.pos().x()), int(item.pos().y()), item.rotation()) for item in self.main.image_viewer.text_items}

            # Identify new blocks based on position and rotation
            new_blocks = [
                blk for blk in self.main.blk_list
                if (int(blk.xyxy[0]), int(blk.xyxy[1]), blk.angle) not in existing_text_items.values()
            ]

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

            self.main.run_threaded(
            lambda: format_translations(self.main.blk_list, trg_lng_cd, upper_case=upper)
            )

            min_font_size = self.main.settings_page.get_min_font_size()
            max_font_size = self.main.settings_page.get_max_font_size()

            align_id = self.main.alignment_tool_group.get_dayu_checked()
            alignment = self.main.button_to_alignment[align_id]
            direction = render_settings.direction

            # Retrieve current image path to fix blk_rendered error
            image_path = ""
            if 0 <= self.main.curr_img_idx < len(self.main.image_files):
                image_path = self.main.image_files[self.main.curr_img_idx]

            self.main.run_threaded(
                manual_wrap, 
                self.on_render_complete, 
                self.main.default_error_handler,
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
                min_font_size
            )

    def on_render_complete(self, rendered_image: np.ndarray):
        # self.main.set_image(rendered_image) 
        self.main.loading.setVisible(False)
        self.main.enable_hbutton_group()
        self.main.undo_group.activeStack().endMacro()

    def render_settings(self) -> TextRenderingSettings:
        target_lang = self.main.lang_mapping.get(self.main.t_combo.currentText(), None)
        direction = get_layout_direction(target_lang)

        return TextRenderingSettings(
            alignment_id = self.main.alignment_tool_group.get_dayu_checked(),
            font_family = self.main.font_dropdown.currentText(),
            min_font_size = int(self.main.settings_page.ui.min_font_spinbox.value()),
            max_font_size = int(self.main.settings_page.ui.max_font_spinbox.value()),
            color = self.main.block_font_color_button.property('selected_color'),
            upper_case = self.main.settings_page.ui.uppercase_checkbox.isChecked(),
            outline = self.main.outline_checkbox.isChecked(),
            outline_color = self.main.outline_font_color_button.property('selected_color'),
            outline_width = self.main.outline_width_dropdown.currentText(),
            bold = self.main.bold_button.isChecked(),
            italic = self.main.italic_button.isChecked(),
            underline = self.main.underline_button.isChecked(),
            line_spacing = self.main.line_spacing_dropdown.currentText(),
            direction = direction
        )
