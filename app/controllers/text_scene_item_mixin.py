from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6 import QtCore
from PySide6.QtGui import QColor
from shiboken6 import isValid as shiboken_is_valid

from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import TextBlockItem
from modules.rendering.render import is_vertical_block
from modules.utils.common_utils import is_close
from modules.utils.image_utils import get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang

if TYPE_CHECKING:
    from modules.utils.textblock import TextBlock


class TextSceneItemMixin:
    @staticmethod
    def _is_live_text_item(text_item: TextBlockItem | None) -> bool:
        if text_item is None:
            return False
        try:
            return bool(shiboken_is_valid(text_item))
        except Exception:
            return False

    def _forget_text_item(self, text_item: TextBlockItem | None) -> None:
        if text_item is None:
            return
        pending = self._pending_text_command
        if pending and pending.get("item") is text_item:
            self._pending_text_command = None
            self._text_change_timer.stop()
        self._last_item_text.pop(text_item, None)
        self._last_item_html.pop(text_item, None)
        if self.main.curr_tblock_item is text_item:
            self.main.curr_tblock_item = None

    def connect_text_item_signals(self, text_item: TextBlockItem, force_reconnect: bool = False):
        if not self._is_live_text_item(text_item):
            return
        if getattr(text_item, "_ct_signals_connected", False) and not force_reconnect:
            return
        is_bulk_restore = bool(getattr(self.main.image_viewer, "_bulk_text_restore", False))

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
            text_item._ct_text_changed_slot = lambda text, ti=text_item: self.update_text_block_from_item(ti, text)

        text_item.item_selected.connect(self.on_text_item_selected)
        text_item.item_deselected.connect(self.on_text_item_deselected)
        text_item.text_changed.connect(text_item._ct_text_changed_slot)
        text_item.text_highlighted.connect(self.set_values_from_highlight)
        text_item.change_undo.connect(self.main.rect_item_ctrl.rect_change_undo)
        if not hasattr(text_item, "_ct_destroyed_slot"):
            text_item._ct_destroyed_slot = lambda *_args, ti=text_item: self._forget_text_item(ti)
        try:
            text_item.destroyed.connect(text_item._ct_destroyed_slot)
        except (AttributeError, TypeError, RuntimeError):
            pass
        self._last_item_text[text_item] = text_item.toPlainText()
        if not is_bulk_restore:
            self._last_item_html[text_item] = text_item.document().toHtml()
        text_item._ct_signals_connected = True

    def _find_scene_text_item_for_block(self, blk: "TextBlock") -> TextBlockItem | None:
        if blk is None or not getattr(self.main, "image_viewer", None):
            return None

        block_uid = str(getattr(blk, "block_uid", "") or "")
        if block_uid:
            for item in self.main.image_viewer.text_items:
                if not self._is_live_text_item(item):
                    continue
                if str(getattr(item, "block_uid", "") or "") == block_uid:
                    return item

        blk_x1 = int(getattr(blk, "xyxy", [0, 0, 0, 0])[0])
        blk_y1 = int(getattr(blk, "xyxy", [0, 0, 0, 0])[1])
        blk_rotation = float(getattr(blk, "angle", 0.0) or 0.0)
        for item in self.main.image_viewer.text_items:
            if not self._is_live_text_item(item):
                continue
            if is_close(item.pos().x(), blk_x1, 5) and is_close(item.pos().y(), blk_y1, 5) and is_close(item.rotation(), blk_rotation, 1):
                return item
        return None

    def _remove_scene_text_item(self, text_item: TextBlockItem | None) -> None:
        if not self._is_live_text_item(text_item):
            self._forget_text_item(text_item)
            return
        scene = text_item.scene()
        if scene is not None:
            try:
                scene.removeItem(text_item)
            except RuntimeError:
                pass
        if text_item in self.main.image_viewer.text_items:
            self.main.image_viewer.text_items.remove(text_item)
        self._forget_text_item(text_item)

    def on_blk_rendered(self, text: str, font_size: int, blk: "TextBlock", image_path: str):
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
            text = text.replace(" ", "")

        render_settings = self.render_settings()
        text_color = get_smart_text_color(blk.font_color, QColor(render_settings.color))
        alignment = self.main.button_to_alignment[render_settings.alignment_id]
        outline_color = QColor(render_settings.outline_color) if self.main.outline_checkbox.isChecked() else None
        vertical = is_vertical_block(blk, trg_lng_cd)

        properties = TextItemProperties(
            text=text,
            source_text=blk.translation or blk.text or text,
            font_family=render_settings.font_family,
            font_size=font_size,
            text_color=text_color,
            alignment=alignment,
            line_spacing=float(render_settings.line_spacing),
            outline_color=outline_color,
            outline_width=float(render_settings.outline_width),
            bold=render_settings.bold,
            italic=render_settings.italic,
            underline=render_settings.underline,
            direction=render_settings.direction,
            position=(blk.xyxy[0], blk.xyxy[1]),
            rotation=blk.angle,
            vertical=vertical,
            width=blk.xywh[2],
            height=blk.xywh[3],
            block_uid=getattr(blk, "block_uid", ""),
        )

        existing_item = self._find_scene_text_item_for_block(blk)
        if existing_item is not None:
            self._remove_scene_text_item(existing_item)

        text_item = self.main.image_viewer.add_text_item(properties)
        text_item.set_plain_text(text, preserve_source_text=True, update_width=False)
        current_file = self._current_file_path()
        if current_file and image_path and os.path.normcase(current_file) == os.path.normcase(image_path):
            self._sync_current_render_snapshot(current_file)

    def on_text_item_selected(self, text_item: TextBlockItem):
        if not self._is_live_text_item(text_item):
            self._forget_text_item(text_item)
            return
        self._commit_pending_text_command()
        self.main.curr_tblock_item = text_item
        self._last_item_text[text_item] = text_item.toPlainText()
        self._last_item_html[text_item] = text_item.document().toHtml()

        x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
        rotation = text_item.rotation()

        self.main.curr_tblock = next(
            (
                blk for blk in self.main.blk_list
                if is_close(blk.xyxy[0], x1, 5) and is_close(blk.xyxy[1], y1, 5) and is_close(blk.angle, rotation, 1)
            ),
            None,
        )

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
