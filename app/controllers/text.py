from __future__ import annotations

import os
import copy
import logging
import numpy as np
from typing import TYPE_CHECKING

from PySide6 import QtCore
from PySide6.QtGui import QColor, QTextCursor
from shiboken6 import isValid as shiboken_is_valid

from app.ui.commands.box import ResizeBlocksCommand
from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.messages import Messages
from pipeline.render_state import ensure_target_snapshot, get_target_render_states, set_target_snapshot

from modules.utils.textblock import TextBlock
from modules.rendering.render import (
    TextRenderingSettings,
    manual_wrap,
    is_vertical_block,
    pyside_word_wrap,
    resolve_init_font_size,
)
from modules.utils.pipeline_config import font_selected
from modules.utils.language_utils import get_language_code, get_layout_direction, is_no_space_lang
from modules.utils.device import resolve_device
from modules.utils.image_utils import get_smart_text_color
from modules.utils.common_utils import is_close
from modules.utils.translator_utils import (
    format_translations,
    transform_text_case_preserving_html,
)

if TYPE_CHECKING:
    from controller import ComicTranslate

logger = logging.getLogger(__name__)

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
        self._bulk_font_restore_snapshot = None
        self._manual_render_macro_open = False
        self._last_target_lang = ""

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
            text_item._ct_text_changed_slot = (
                lambda text, ti=text_item: self.update_text_block_from_item(ti, text)
            )

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

    def clear_text_edits(self):
        self.main.curr_tblock = None
        self.main.curr_tblock_item = None
        self.main.s_text_edit.clear()
        self.main.t_text_edit.clear()

    def _current_file_path(self) -> str:
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            return self.main.image_files[self.main.curr_img_idx]
        return ""

    def _current_target_lang(self) -> str:
        return self.main.t_combo.currentText()

    def _mirror_target_snapshot_to_viewer_state(self, state: dict, target_lang: str) -> dict:
        target_snapshot = get_target_render_states(state).get(target_lang)
        if not target_snapshot:
            target_snapshot = ensure_target_snapshot(
                state,
                target_lang,
                source_target=state.get("target_lang") or self._last_target_lang or "",
                fallback_snapshot=state.get("viewer_state") or {},
            )
        if target_snapshot:
            state["viewer_state"] = copy.deepcopy(target_snapshot)
        else:
            state.setdefault("viewer_state", {})
        return state["viewer_state"]

    def _sync_current_render_snapshot(self, file_path: str | None = None) -> None:
        file_path = file_path or self._current_file_path()
        if not file_path:
            return
        state = self.main.image_states.get(file_path)
        if state is None:
            return

        viewer_state = copy.deepcopy(state.get("viewer_state", {}) or {})
        if self.main.image_viewer.hasPhoto():
            current_scene_state = self.main.image_viewer.save_state()
            for key in ("transform", "center", "scene_rect"):
                if current_scene_state.get(key) is not None:
                    viewer_state[key] = current_scene_state.get(key)
            if self.main.image_viewer.text_items:
                viewer_state["text_items_state"] = copy.deepcopy(
                    current_scene_state.get("text_items_state", []) or []
                )

        state["viewer_state"] = viewer_state
        target_lang = state.get("target_lang") or self._current_target_lang()
        if target_lang and viewer_state.get("text_items_state") is not None:
            set_target_snapshot(state, target_lang, viewer_state)

    def _finalize_manual_render(self, current_file: str | None) -> None:
        batch_report_ctrl = getattr(self.main, "batch_report_ctrl", None)

        def _finish() -> None:
            try:
                if current_file is not None:
                    self.main.image_ctrl.save_image_state(current_file)
                if batch_report_ctrl is not None and current_file:
                    batch_report_ctrl.register_batch_success(current_file)
            finally:
                if self._manual_render_macro_open:
                    stack = self.main.undo_group.activeStack()
                    if stack is not None:
                        try:
                            stack.endMacro()
                        except Exception:
                            pass
                    self._manual_render_macro_open = False

        QtCore.QTimer.singleShot(0, _finish)

    def _sync_block_caches(self, blk: TextBlock | None) -> None:
        if blk is None or self.main.curr_img_idx < 0 or self.main.curr_img_idx >= len(self.main.image_files):
            return

        current_file = self.main.image_files[self.main.curr_img_idx]
        try:
            image = self.main.image_ctrl.load_original_image(current_file)
        except Exception:
            image = None
        if image is None:
            return

        cache_manager = getattr(getattr(self.main, "pipeline", None), "cache_manager", None)
        if cache_manager is None:
            return

        settings_page = self.main.settings_page
        try:
            ocr_model = settings_page.get_tool_selection("ocr")
            device = resolve_device(settings_page.is_gpu_enabled())
            ocr_key = cache_manager._get_ocr_cache_key(image, "", ocr_model, device)
            cache_manager.update_ocr_cache_for_block(ocr_key, blk)
        except Exception:
            pass

        try:
            translator_key = settings_page.get_tool_selection("translator")
            extra_context = settings_page.get_llm_settings().get("extra_context", "")
            target_lang = self.main.t_combo.currentText()
            translation_key = cache_manager._get_translation_cache_key(
                image,
                "",
                target_lang,
                translator_key,
                extra_context,
            )
            cache_manager.update_translation_cache_for_block(translation_key, blk)
        except Exception:
            pass

    def _find_scene_text_item_for_block(self, blk: TextBlock) -> TextBlockItem | None:
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
            if (
                is_close(item.pos().x(), blk_x1, 5)
                and is_close(item.pos().y(), blk_y1, 5)
                and is_close(item.rotation(), blk_rotation, 1)
            ):
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
            source_text=blk.translation or blk.text or text,
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
            current_file = self._current_file_path()
            old_text = self.main.curr_tblock.text
            self.main.curr_tblock.text = self.main.s_text_edit.toPlainText()
            self.main.curr_tblock.translation = self.main.t_text_edit.toPlainText()
            if self.main.curr_tblock_item:
                self.main.curr_tblock_item.set_source_text(self.main.t_text_edit.toPlainText())
            self._sync_block_caches(self.main.curr_tblock)
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

                # Restore cursor position
                cursor = self.main.t_text_edit.textCursor()
                cursor.setPosition(cursor_position)
                self.main.t_text_edit.setTextCursor(cursor)
            if (old_translation is None or old_translation == new_text) and (
                old_item_text is None or old_item_text == new_text
            ):
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

    def save_src_trg(self):
        target_lang = self.main.t_combo.currentText()
        previous_target = self._last_target_lang
        if not previous_target and self.main.curr_img_idx >= 0:
            current_file = self.main.image_files[self.main.curr_img_idx]
            previous_target = self.main.image_states.get(current_file, {}).get("target_lang", "")

        self.main.image_ctrl.save_current_image_state()

        target_en = self.main.lang_mapping.get(target_lang, None)
        t_direction = get_layout_direction(target_en)
        t_text_option = self.main.t_text_edit.document().defaultTextOption()
        t_text_option.setTextDirection(t_direction)
        self.main.t_text_edit.document().setDefaultTextOption(t_text_option)

        for image_path in self.main.image_files:
            state = self.main.image_states.get(image_path)
            if state is not None:
                old_target = state.get("target_lang") or previous_target
                viewer_state = copy.deepcopy(state.get("viewer_state", {}) or {})
                target_render_states = get_target_render_states(state)
                if old_target and viewer_state and old_target not in target_render_states:
                    set_target_snapshot(state, old_target, viewer_state)

                had_target_snapshot = target_lang in target_render_states
                if not had_target_snapshot:
                    ensure_target_snapshot(
                        state,
                        target_lang,
                        source_target=old_target or "",
                        fallback_snapshot=viewer_state,
                    )
                if target_lang in target_render_states:
                    state["viewer_state"] = copy.deepcopy(target_render_states[target_lang])
                else:
                    state["viewer_state"] = viewer_state
                state['target_lang'] = target_lang
                if not had_target_snapshot:
                    ps = state.setdefault("pipeline_state", {})
                    target_validity = ps.setdefault("target_validity", {})
                    target_validity[target_lang] = {"translate": False, "render": False}

        if self.main.curr_img_idx >= 0:
            self.main.stage_nav_ctrl.restore_current_page_view()
            self.main.mark_project_dirty()
        self._last_target_lang = target_lang

    def set_src_trg_all(self):
        target_lang = self.main.t_combo.currentText()
        for image_path in self.main.image_files:
            state = self.main.image_states[image_path]
            target_render_states = get_target_render_states(state)
            if target_lang not in target_render_states and state.get("viewer_state"):
                set_target_snapshot(state, target_lang, state["viewer_state"])
            state["target_lang"] = target_lang
            if target_lang in target_render_states:
                state["viewer_state"] = copy.deepcopy(target_render_states[target_lang])
        if self.main.image_files:
            self.main.mark_project_dirty()

    def change_all_blocks_size(self, diff: int):
        if len(self.main.blk_list) == 0:
            return
        command = ResizeBlocksCommand(self.main, self.main.blk_list, diff)
        command.redo()
        current_file = self._current_file_path()
        if current_file:
            self.main.stage_nav_ctrl.invalidate_for_box_edit(current_file)
        self.main.mark_project_dirty()

    def _find_text_block_for_item(self, text_item: TextBlockItem) -> TextBlock | None:
        if not self._is_live_text_item(text_item):
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
        if not self._is_live_text_item(text_item):
            self._forget_text_item(text_item)
            return

        pending = self._pending_text_command
        if pending and pending['item'] is not text_item:
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
                'item': text_item,
                'old_text': old_text,
                'new_text': new_text,
                'old_html': old_html,
                'new_html': new_html,
                'blk': blk,
                'file_path': self._current_file_path(),
                'target_lang': self._current_target_lang(),
            }
            self._pending_text_command = pending
        else:
            pending['new_text'] = new_text
            pending['new_html'] = new_html
            pending['blk'] = blk
            pending['file_path'] = pending.get('file_path') or self._current_file_path()
            pending['target_lang'] = pending.get('target_lang') or self._current_target_lang()

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

        pending_file = pending.get('file_path') or self._current_file_path()
        pending_target = pending.get('target_lang') or self._current_target_lang()
        pending_item = pending.get('item')
        pending_blk = pending.get('blk')
        if not self._is_live_text_item(pending_item):
            self._forget_text_item(pending_item)
            if pending_file and pending_file in self.main.image_states:
                self.main.stage_nav_ctrl.invalidate_for_translated_text_edit(
                    pending_file,
                    pending_target,
                )
            self.main.mark_project_dirty()
            return

        self.apply_text_from_command(
            pending_item,
            pending['new_text'],
            html=pending.get('new_html'),
            blk=pending_blk,
            file_path=pending_file,
        )
        if pending_file and pending_file in self.main.image_states:
            self.main.stage_nav_ctrl.invalidate_for_translated_text_edit(
                pending_file,
                pending_target,
            )
        self.main.mark_project_dirty()

    def apply_text_from_command(self, text_item: TextBlockItem, text: str,
                                html: str | None = None, blk: TextBlock | None = None,
                                file_path: str | None = None):
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
                # Only update if the text is actually different to avoid cursor reset
                if self.main.t_text_edit.toPlainText() != text:
                    self.main.t_text_edit.blockSignals(True)
                    self.main.t_text_edit.setPlainText(text)
                    self.main.t_text_edit.blockSignals(False)
        finally:
            self._suspend_text_command = False
        if self._is_live_text_item(text_item):
            text_item.set_source_text(text)
            self._last_item_text[text_item] = text
            self._last_item_html[text_item] = text_item.document().toHtml()
        else:
            self._forget_text_item(text_item)
        current_file = file_path or self._current_file_path()
        if current_file and blk in self.main.blk_list:
            self._sync_current_render_snapshot(current_file)

    def _finalize_format_edit(self):
        current_file = self._current_file_path()
        if current_file:
            self._sync_current_render_snapshot(current_file)
            self.main.stage_nav_ctrl.invalidate_for_format_edit(
                current_file,
                self._current_target_lang(),
            )
        self.main.mark_project_dirty()

    # Formatting actions
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
            self.main.block_font_color_button.setProperty('selected_color', font_color.name())
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

    def _get_image_state_for_path(self, file_path: str):
        state = self.main.image_states.get(file_path)
        if state is not None:
            return state
        target_norm = os.path.normcase(file_path)
        for key, value in self.main.image_states.items():
            if os.path.normcase(key) == target_norm:
                return value
        return None

    def _apply_bulk_text_update(self, per_page_fn=None, per_scene_fn=None, action_name: str = "bulk text update"):
        updated_any = False
        updated_pages = 0
        updated_files: list[str] = []
        for file_path in self.main.image_files:
            state = self._get_image_state_for_path(file_path)
            if state is None:
                continue
            if per_page_fn is not None:
                try:
                    if per_page_fn(file_path, state):
                        updated_any = True
                        updated_pages += 1
                        updated_files.append(file_path)
                except Exception:
                    continue

        if per_scene_fn is not None:
            try:
                if per_scene_fn():
                    updated_any = True
            except Exception:
                pass

        self._refresh_current_text_controls()

        if updated_any:
            current_target = self._current_target_lang()
            for file_path in updated_files:
                state = self.main.image_states.get(file_path)
                if state is not None and state.get("target_lang") == current_target:
                    set_target_snapshot(state, current_target, state.get("viewer_state", {}) or {})
                self.main.stage_nav_ctrl.invalidate_for_format_edit(file_path, current_target)
            current_file = self._current_file_path()
            if current_file:
                self._sync_current_render_snapshot(current_file)
            self.main.mark_project_dirty()
            logger.info("%s applied to %d page(s).", action_name, updated_pages)
            self._show_bulk_update_message(action_name, updated_pages)

    def _capture_bulk_font_snapshot(self):
        snapshot = {}
        for file_path in self.main.image_files:
            state = self._get_image_state_for_path(file_path)
            if not state:
                continue
            text_items_state = state.get("viewer_state", {}).get("text_items_state", [])
            snapshot[file_path] = [
                {
                    "font_family": item_state.get("font_family", ""),
                    "line_spacing": item_state.get("line_spacing", 0),
                }
                if isinstance(item_state, dict)
                else {"font_family": "", "line_spacing": 0}
                for item_state in text_items_state
            ]

        current_path = self._current_file_path()
        current_items = []
        if self.main.image_viewer and self.main.image_viewer.text_items:
            current_items = [
                {
                    "font_family": getattr(item, "font_family", ""),
                    "line_spacing": getattr(item, "line_spacing", 0),
                }
                for item in self.main.image_viewer.text_items
            ]
        if current_path:
            snapshot[current_path] = current_items
        self._bulk_font_restore_snapshot = snapshot

    def _get_bulk_font_snapshot(self):
        snapshot = self._bulk_font_restore_snapshot or {}
        if not snapshot:
            return {}
        return snapshot

    @staticmethod
    def _normalize_bulk_font_snapshot_entry(entry):
        if isinstance(entry, dict):
            return {
                "font_family": entry.get("font_family", ""),
                "line_spacing": entry.get("line_spacing", 0),
            }
        if isinstance(entry, str):
            return {"font_family": entry, "line_spacing": 0}
        return {"font_family": "", "line_spacing": 0}

    def _show_bulk_update_message(self, action_name: str, updated_pages: int):
        if updated_pages <= 0:
            return
        try:
            Messages.show_bulk_text_update(self.main, action_name, updated_pages)
        except Exception:
            pass

    def _make_temp_text_item(self, props: TextItemProperties, font_family: str) -> TextBlockItem:
        render_color = props.text_color
        if render_color is None:
            selected_color = self.main.block_font_color_button.property("selected_color")
            render_color = QColor(selected_color) if selected_color else QColor("#000000")

        temp_width = props.width if props.width is not None and props.width > 0 else 1000
        temp_item = TextBlockItem(
            text=props.text,
            font_family=props.font_family,
            font_size=props.font_size,
            render_color=render_color,
            alignment=props.alignment,
            line_spacing=props.line_spacing,
            outline_color=props.outline_color,
            outline_width=props.outline_width,
            bold=props.bold,
            italic=props.italic,
            underline=props.underline,
            direction=props.direction,
        )
        temp_item.set_text(props.text, temp_width)
        temp_item.set_font(font_family, props.font_size)
        source_text = props.source_text or temp_item.get_source_text()
        if source_text:
            temp_item.set_source_text(source_text)
            temp_height = props.height if props.height is not None and props.height > 0 else temp_item.get_text_box_size()[1]
            temp_item.reflow_from_source_text(
                temp_width,
                temp_height,
                max_font_size=int(round(props.font_size)) if props.font_size else None,
            )
        return temp_item

    def _reflow_current_text_item(self, max_font_size: int | None = None):
        text_item = self.main.curr_tblock_item
        if not text_item:
            return
        width, height = text_item.get_text_box_size()
        text_item.reflow_from_source_text(width, height, max_font_size=max_font_size)

    def _get_saved_item_source_text(self, item_state: dict) -> str:
        source_text = item_state.get("source_text", "")
        if source_text:
            return source_text

        try:
            props = TextItemProperties.from_dict(item_state)
            temp_item = self._make_temp_text_item(props, props.font_family)
            return temp_item.get_source_text()
        except Exception:
            return item_state.get("text", "")

    def _rebuild_saved_item_layout(self, item_state: dict) -> bool:
        try:
            props = TextItemProperties.from_dict(item_state)
            temp_item = self._make_temp_text_item(props, props.font_family)
            item_state["text"] = temp_item.toHtml()
            item_state["source_text"] = temp_item.get_source_text()
            item_state["font_family"] = temp_item.font_family
            width, height = temp_item.get_text_box_size()
            item_state["width"] = width
            item_state["height"] = height
            return True
        except Exception:
            return False

    def _transform_text_item_html(
        self,
        html: str,
        item_state: dict | None = None,
        font_family: str | None = None,
        transform_font_fn=None,
        transform_case_fn=None,
    ) -> str:
        if not html:
            return html

        if transform_case_fn is not None:
            return transform_case_fn(html)

        if item_state is None or transform_font_fn is None:
            return html

        try:
            props = TextItemProperties.from_dict(item_state)
            temp_item = self._make_temp_text_item(props, font_family or props.font_family)
            return temp_item.toHtml()
        except Exception:
            return html

    def _update_saved_text_items(
        self,
        state,
        transform_text_fn=None,
        transform_font_fn=None,
        transform_source_text_fn=None,
    ) -> bool:
        updated = False
        text_items_state = state.setdefault("viewer_state", {}).get("text_items_state", [])

        for item_state in text_items_state:
            if not isinstance(item_state, dict):
                continue

            old_html = item_state.get("text", "")
            old_font_family = item_state.get("font_family") if transform_font_fn is not None else None
            old_source_text = item_state.get("source_text", "") if transform_source_text_fn is not None else None
            if transform_font_fn is not None:
                transform_font_fn(item_state)

            if transform_source_text_fn is not None:
                source_text = self._get_saved_item_source_text(item_state)
                transformed_source_text = transform_source_text_fn(source_text)
                if transformed_source_text != source_text:
                    item_state["source_text"] = transformed_source_text
                    updated = True

            if transform_text_fn is not None and old_html:
                new_html = transform_text_fn(old_html, item_state)
                if new_html != old_html:
                    item_state["text"] = new_html
                    updated = True

            if transform_font_fn is not None and old_font_family != item_state.get("font_family"):
                updated = True

            if transform_source_text_fn is not None and old_source_text != item_state.get("source_text"):
                updated = True

            if (transform_font_fn is not None or transform_source_text_fn is not None) and self._rebuild_saved_item_layout(item_state):
                updated = True

        return updated

    def _update_current_scene_text_items(
        self,
        transform_text_fn=None,
        transform_font_fn=None,
        transform_source_text_fn=None,
    ) -> bool:
        if not (self.main.image_viewer and self.main.image_viewer.text_items):
            return False

        updated = False
        for item in self.main.image_viewer.text_items:
            try:
                source_changed = False
                style_before = (
                    getattr(item, "font_family", ""),
                    getattr(item, "font_size", 0),
                    getattr(item, "bold", False),
                    getattr(item, "italic", False),
                    getattr(item, "underline", False),
                    getattr(item, "line_spacing", 0),
                )
                if transform_text_fn is not None:
                    html = item.toHtml()
                    transformed_html = transform_text_fn(html, item)
                    if transformed_html != html:
                        width = item.textWidth()
                        if width is None or width <= 0:
                            width = item.document().size().width()
                        item.set_text(transformed_html, width)
                        updated = True
                if transform_source_text_fn is not None and hasattr(item, "get_source_text"):
                    source_text = item.get_source_text()
                    transformed_source_text = transform_source_text_fn(source_text)
                    if transformed_source_text != source_text:
                        item.set_source_text(transformed_source_text)
                        source_changed = True
                if transform_font_fn is not None:
                    transform_font_fn(item)
                style_after = (
                    getattr(item, "font_family", ""),
                    getattr(item, "font_size", 0),
                    getattr(item, "bold", False),
                    getattr(item, "italic", False),
                    getattr(item, "underline", False),
                    getattr(item, "line_spacing", 0),
                )
                style_changed = style_after != style_before
                if style_changed:
                    updated = True
                if (source_changed or style_changed) and hasattr(item, "reflow_from_source_text"):
                    width, height = item.get_text_box_size()
                    item.reflow_from_source_text(
                        width,
                        height,
                        max_font_size=int(round(getattr(item, "font_size", 1))),
                    )
                    updated = True
            except Exception:
                continue
        return updated

    def apply_font_to_all_pages(self):
        font_family = self.main.font_dropdown.currentText()
        if not font_family:
            return

        try:
            line_spacing = float(self.main.line_spacing_dropdown.currentText())
        except Exception:
            line_spacing = None

        self._capture_bulk_font_snapshot()

        def _set_item_font(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["font_family"] = font_family
                if line_spacing is not None:
                    item_or_state["line_spacing"] = line_spacing
            else:
                item_or_state.set_font(font_family, item_or_state.font_size)
                if line_spacing is not None:
                    item_or_state.set_line_spacing(line_spacing)

        def _transform_saved_html(old_html, item_state):
            return self._transform_text_item_html(
                old_html,
                item_state=item_state,
                font_family=font_family,
                transform_font_fn=_set_item_font,
            )

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_text_fn=_transform_saved_html,
                transform_font_fn=_set_item_font,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_font,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_apply_font_all_label(),
        )

    def restore_font_to_all_pages(self):
        snapshot = self._get_bulk_font_snapshot()
        if not snapshot:
            return

        def _update_page(file_path, state):
            page_snapshot = snapshot.get(file_path, [])
            if not page_snapshot:
                return False

            text_items_state = state.get("viewer_state", {}).get("text_items_state", [])
            updated = False
            for idx, item_state in enumerate(text_items_state):
                if not isinstance(item_state, dict):
                    continue
                prev_state = self._normalize_bulk_font_snapshot_entry(
                    page_snapshot[idx] if idx < len(page_snapshot) else {}
                )
                font_family = prev_state.get("font_family", "")
                line_spacing = prev_state.get("line_spacing", 0)
                if font_family and item_state.get("font_family") != font_family:
                    item_state["font_family"] = font_family
                    updated = True
                if item_state.get("line_spacing", 0) != line_spacing:
                    item_state["line_spacing"] = line_spacing
                    updated = True
                    self._rebuild_saved_item_layout(item_state)
            return updated

        def _update_scene():
            current_path = self._current_file_path()
            page_snapshot = snapshot.get(current_path, [])
            if not page_snapshot or not self.main.image_viewer.text_items:
                return False

            updated = False
            for idx, item in enumerate(self.main.image_viewer.text_items):
                prev_state = self._normalize_bulk_font_snapshot_entry(
                    page_snapshot[idx] if idx < len(page_snapshot) else {}
                )
                font_family = prev_state.get("font_family", "")
                line_spacing = prev_state.get("line_spacing", 0)
                if font_family and getattr(item, "font_family", "") != font_family:
                    item.set_font(font_family, item.font_size)
                    updated = True
                if line_spacing is not None and getattr(item, "line_spacing", 0) != line_spacing:
                    item.set_line_spacing(line_spacing)
                    updated = True
                if font_family or line_spacing is not None:
                    width, height = item.get_text_box_size()
                    item.reflow_from_source_text(
                        width,
                        height,
                        max_font_size=int(round(getattr(item, "font_size", 1))),
                    )
                    updated = True
            return updated

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_restore_font_all_label(),
        )

    def apply_italic_to_all_pages(self):
        def _set_item_italic(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["italic"] = True
            else:
                item_or_state.set_italic(True)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_italic,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_italic,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_italic_all_label(),
        )

    def apply_italic_off_to_all_pages(self):
        def _set_item_italic(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["italic"] = False
            else:
                item_or_state.set_italic(False)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_italic,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_italic,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_italic_off_all_label(),
        )

    def apply_bold_to_all_pages(self):
        def _set_item_bold(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["bold"] = True
            else:
                item_or_state.set_bold(True)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_bold,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_bold,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_bold_all_label(),
        )

    def apply_bold_off_to_all_pages(self):
        def _set_item_bold(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["bold"] = False
            else:
                item_or_state.set_bold(False)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_bold,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_bold,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_bold_off_all_label(),
        )

    def apply_underline_to_all_pages(self):
        def _set_item_underline(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["underline"] = True
            else:
                item_or_state.set_underline(True)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_underline,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_underline,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_underline_all_label(),
        )

    def apply_underline_off_to_all_pages(self):
        def _set_item_underline(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["underline"] = False
            else:
                item_or_state.set_underline(False)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_underline,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_underline,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_underline_off_all_label(),
        )

    def apply_text_case_to_all_pages(self, upper_case: bool):
        def _transform_case_text(text: str) -> str:
            return text.upper() if upper_case else text.lower()

        def _transform_case_html(text: str) -> str:
            return transform_text_case_preserving_html(text, upper_case=upper_case)

        def _transform_saved_html(old_html, _item_state):
            return self._transform_text_item_html(
                old_html,
                transform_case_fn=_transform_case_html,
            )

        action_name = (
            Messages.bulk_upper_all_label()
            if upper_case
            else Messages.bulk_lower_all_label()
        )

        def _update_page(_file_path, state):
            updated = False
            for blk in state.get("blk_list", []):
                translation = getattr(blk, "translation", "")
                if not translation:
                    continue
                transformed_translation = translation.upper() if upper_case else translation.lower()
                if transformed_translation != translation:
                    blk.translation = transformed_translation
                    updated = True

            if self._update_saved_text_items(
                state,
                transform_text_fn=_transform_saved_html,
                transform_source_text_fn=_transform_case_text,
            ):
                updated = True
            return updated

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_text_fn=_transform_saved_html,
                transform_source_text_fn=_transform_case_text,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=action_name,
        )

    def handle_bulk_text_action_change(self, index: int):
        dropdown = self.main.bulk_text_action_dropdown
        if not dropdown or index <= 0:
            return

        action = dropdown.itemData(index)
        try:
            if action == "apply_font_all":
                self.apply_font_to_all_pages()
            elif action == "restore_font_all":
                self.restore_font_to_all_pages()
            elif action == "upper_all":
                self.apply_text_case_to_all_pages(True)
            elif action == "lower_all":
                self.apply_text_case_to_all_pages(False)
            elif action == "bold_all":
                self.apply_bold_to_all_pages()
            elif action == "bold_off_all":
                self.apply_bold_off_to_all_pages()
            elif action == "italic_all":
                self.apply_italic_to_all_pages()
            elif action == "italic_off_all":
                self.apply_italic_off_to_all_pages()
            elif action == "underline_all":
                self.apply_underline_to_all_pages()
            elif action == "underline_off_all":
                self.apply_underline_off_to_all_pages()
        finally:
            dropdown.blockSignals(True)
            dropdown.setCurrentIndex(0)
            dropdown.blockSignals(False)

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
            self.main.outline_font_color_button.setProperty('selected_color', outline_color.name())
            outline_width = float(self.main.outline_width_dropdown.currentText())

            if self.main.curr_tblock_item and self.main.outline_checkbox.isChecked():
                self.main.curr_tblock_item.set_outline(outline_color, outline_width)
                self._finalize_format_edit()

    def on_outline_width_change(self, outline_width):
        if self.main.curr_tblock_item and self.main.outline_checkbox.isChecked():
            outline_width = float(self.main.outline_width_dropdown.currentText())
            color_str = self.main.outline_font_color_button.property('selected_color')
            color = QColor(color_str)
            self.main.curr_tblock_item.set_outline(color, outline_width)
            self._finalize_format_edit()

    def toggle_outline_settings(self, state):
        enabled = True if state == 2 else False
        if self.main.curr_tblock_item:
            if not enabled:
                self.main.curr_tblock_item.set_outline(None, None)
                self._finalize_format_edit()
            else:
                outline_width = float(self.main.outline_width_dropdown.currentText())
                color_str = self.main.outline_font_color_button.property('selected_color')
                color = QColor(color_str)
                self.main.curr_tblock_item.set_outline(color, outline_width)
                self._finalize_format_edit()

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

            def on_selected_render_ready(updated_paths: set[str]) -> None:
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
                            self.main.manual_workflow_ctrl._reload_current_webtoon_page()
                    else:
                        self.main.image_ctrl.on_render_state_ready(current_file)
                        self.main.image_ctrl.save_current_image_state()

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

            # Prefer stable block_uid matching; fall back to geometry for legacy items.
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

            # Retrieve current image path to fix blk_rendered error
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
                min_font_size
            )

    def on_render_complete(self, rendered_image: np.ndarray):
        # self.main.set_image(rendered_image) 
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
