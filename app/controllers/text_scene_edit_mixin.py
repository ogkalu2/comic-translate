from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QTextCursor

from app.ui.canvas.text_item import TextBlockItem
from modules.utils.common_utils import is_close

if TYPE_CHECKING:
    from modules.utils.textblock import TextBlock


class TextSceneEditMixin:
    def update_text_block(self):
        if self.main.curr_tblock:
            current_file = self._current_file_path()
            old_text = self.main.curr_tblock.text
            new_source_text = self.main.s_text_edit.toPlainText()
            self.main.curr_tblock.text = new_source_text
            self.main.curr_tblock.translation = self.main.t_text_edit.toPlainText()
            if self.main.curr_tblock_item:
                self.main.curr_tblock_item.set_source_text(new_source_text)
            self._sync_block_caches(self.main.curr_tblock, sync_translation=False)
            if current_file and old_text != self.main.curr_tblock.text:
                self.main.stage_nav_ctrl.invalidate_for_source_text_edit(current_file)
                self.main.mark_project_dirty()

    def update_text_block_from_edit(self):
        self._is_updating_from_edit = True
        try:
            current_file = self._current_file_path()
            current_target = self._current_target_lang()
            new_text = self.main.t_text_edit.toPlainText()
            old_translation = None
            old_item_text = None
            if self.main.curr_tblock:
                old_translation = self.main.curr_tblock.translation
                self.main.curr_tblock.translation = new_text
            if self.main.curr_tblock_item:
                self.main.curr_tblock_item.set_source_text(new_text)

            if self.main.curr_tblock_item and self.main.curr_tblock_item in self.main.image_viewer._scene.items():
                old_item_text = self.main.curr_tblock_item.toPlainText()
                cursor_position = self.main.t_text_edit.textCursor().position()
                self._apply_text_item_text_delta(self.main.curr_tblock_item, new_text)

                cursor = self.main.t_text_edit.textCursor()
                cursor.setPosition(cursor_position)
                self.main.t_text_edit.setTextCursor(cursor)
            if (old_translation is None or old_translation == new_text) and (old_item_text is None or old_item_text == new_text):
                return
            self._sync_block_caches(self.main.curr_tblock)
            if current_file:
                self._sync_current_render_snapshot(current_file)
                self.main.stage_nav_ctrl.invalidate_for_translated_text_edit(current_file, current_target)
            self.main.mark_project_dirty()
        finally:
            self._is_updating_from_edit = False

    def update_text_block_from_item(self, text_item: TextBlockItem, new_text: str):
        if self._suspend_text_command:
            return
        blk = self._find_text_block_for_item(text_item)
        if blk:
            blk.translation = new_text
            self._sync_block_caches(blk)

        if self.main.curr_tblock_item == text_item and not self._is_updating_from_edit:
            self.main.curr_tblock = blk
            self.main.t_text_edit.blockSignals(True)
            self.main.t_text_edit.setPlainText(new_text)
            self.main.t_text_edit.blockSignals(False)

        if text_item:
            text_item.set_source_text(new_text)
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

    def _find_text_block_for_item(self, text_item: TextBlockItem) -> "TextBlock" | None:
        if not self._is_live_text_item(text_item):
            return None

        x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
        rotation = text_item.rotation()

        return next(
            (
                blk for blk in self.main.blk_list
                if is_close(blk.xyxy[0], x1, 5) and is_close(blk.xyxy[1], y1, 5) and is_close(blk.angle, rotation, 1)
            ),
            None,
        )

    def _schedule_text_change_command(self, text_item: TextBlockItem, new_text: str, blk: "TextBlock" | None):
        if self._suspend_text_command:
            return
        if not self._is_live_text_item(text_item):
            self._forget_text_item(text_item)
            return

        pending = self._pending_text_command
        if pending and pending["item"] is not text_item:
            self._commit_pending_text_command()
            pending = None

        try:
            new_html = text_item.document().toHtml()
        except RuntimeError:
            self._forget_text_item(text_item)
            return
        if pending is None:
            old_text = self._last_item_text.get(text_item, new_text)
            old_html = self._last_item_html.get(text_item, new_html)
            if old_text == new_text:
                self._last_item_text[text_item] = new_text
                self._last_item_html[text_item] = new_html
                return
            pending = {
                "item": text_item,
                "old_text": old_text,
                "new_text": new_text,
                "old_html": old_html,
                "new_html": new_html,
                "blk": blk,
                "file_path": self._current_file_path(),
                "target_lang": self._current_target_lang(),
            }
            self._pending_text_command = pending
        else:
            pending["new_text"] = new_text
            pending["new_html"] = new_html
            pending["blk"] = blk
            pending["file_path"] = pending.get("file_path") or self._current_file_path()
            pending["target_lang"] = pending.get("target_lang") or self._current_target_lang()

        self._last_item_text[text_item] = new_text
        self._last_item_html[text_item] = new_html
        self._text_change_timer.start()

    def _commit_pending_text_command(self):
        if not self._pending_text_command:
            return
        self._text_change_timer.stop()
        pending = self._pending_text_command
        self._pending_text_command = None

        if pending["old_text"] == pending["new_text"]:
            return

        pending_file = pending.get("file_path") or self._current_file_path()
        pending_target = pending.get("target_lang") or self._current_target_lang()
        pending_item = pending.get("item")
        pending_blk = pending.get("blk")
        if not self._is_live_text_item(pending_item):
            self._forget_text_item(pending_item)
            if pending_file and pending_file in self.main.image_states:
                self.main.stage_nav_ctrl.invalidate_for_translated_text_edit(pending_file, pending_target)
            self.main.mark_project_dirty()
            return

        self.apply_text_from_command(
            pending_item,
            pending["new_text"],
            html=pending.get("new_html"),
            blk=pending_blk,
            file_path=pending_file,
        )
        if pending_file and pending_file in self.main.image_states:
            self.main.stage_nav_ctrl.invalidate_for_translated_text_edit(pending_file, pending_target)
        self.main.mark_project_dirty()

    def apply_text_from_command(
        self,
        text_item: TextBlockItem,
        text: str,
        html: str | None = None,
        blk: "TextBlock" | None = None,
        file_path: str | None = None,
    ):
        self._suspend_text_command = True
        try:
            item_is_live = self._is_live_text_item(text_item)
            if item_is_live and text_item in self.main.image_viewer._scene.items():
                if html is not None:
                    if text_item.document().toHtml() != html:
                        text_item.document().setHtml(html)
                elif text_item.toPlainText() != text:
                    text_item.set_plain_text(text)
            if blk is None and item_is_live:
                blk = self._find_text_block_for_item(text_item)
            if blk:
                blk.translation = text
                self._sync_block_caches(blk)
            if item_is_live and self.main.curr_tblock_item == text_item:
                self.main.curr_tblock = blk
                if self.main.t_text_edit.toPlainText() != text:
                    self.main.t_text_edit.blockSignals(True)
                    self.main.t_text_edit.setPlainText(text)
                    self.main.t_text_edit.blockSignals(False)
        finally:
            self._suspend_text_command = False
        if self._is_live_text_item(text_item):
            text_item.set_source_text(text)
