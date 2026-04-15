from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore
from PySide6.QtGui import QTextCursor

from app.controllers.search_replace_core import _rect_area, find_block_by_key
from modules.utils.common_utils import is_close


class SearchReplaceSelectionMixin:
    def _set_current_row_for_file(self, file_path: str) -> bool:
        try:
            idx = self.main.image_files.index(file_path)
        except ValueError:
            return False
        if self.main.curr_img_idx == idx:
            return True
        self.main.page_list.setCurrentRow(idx)
        return True

    def _find_block_in_current_image(self, key) -> Optional[object]:
        if self.main.curr_img_idx < 0:
            return None
        current_file = self.main.image_files[self.main.curr_img_idx]
        if os.path.normcase(current_file) != os.path.normcase(key.file_path):
            return None

        def _key_xyxy_to_scene() -> tuple[float, float, float, float] | None:
            if not getattr(self.main, "webtoon_mode", False):
                return None
            viewer = getattr(self.main, "image_viewer", None)
            webtoon_manager = getattr(viewer, "webtoon_manager", None) if viewer is not None else None
            converter = getattr(webtoon_manager, "coordinate_converter", None) if webtoon_manager is not None else None
            if converter is None:
                return None
            try:
                page_idx = self.main.image_files.index(key.file_path)
            except ValueError:
                return None
            try:
                tl = QtCore.QPointF(float(key.xyxy[0]), float(key.xyxy[1]))
                br = QtCore.QPointF(float(key.xyxy[2]), float(key.xyxy[3]))
                stl = converter.page_local_to_scene_position(tl, page_idx)
                sbr = converter.page_local_to_scene_position(br, page_idx)
                return (float(stl.x()), float(stl.y()), float(sbr.x()), float(sbr.y()))
            except Exception:
                return None

        scene_xyxy = _key_xyxy_to_scene()
        for blk in self.main.blk_list or []:
            angle = float(getattr(blk, "angle", 0.0) or 0.0)
            try:
                bxyxy = (float(blk.xyxy[0]), float(blk.xyxy[1]), float(blk.xyxy[2]), float(blk.xyxy[3]))
            except Exception:
                continue

            if (
                (int(bxyxy[0]), int(bxyxy[1]), int(bxyxy[2]), int(bxyxy[3])) == key.xyxy
                and is_close(angle, key.angle, 0.5)
            ):
                return blk

            if scene_xyxy is not None and is_close(angle, key.angle, 0.5):
                if (
                    is_close(bxyxy[0], scene_xyxy[0], 5)
                    and is_close(bxyxy[1], scene_xyxy[1], 5)
                    and is_close(bxyxy[2], scene_xyxy[2], 5)
                    and is_close(bxyxy[3], scene_xyxy[3], 5)
                ):
                    return blk
        return None

    def _find_text_item_for_block(self, blk: object):
        if not getattr(self.main, "image_viewer", None):
            return None
        text_items = getattr(self.main.image_viewer, "text_items", None)
        if not text_items:
            return None
        try:
            x1, y1, x2, y2 = blk.xyxy
        except Exception:
            return None

        block_rect = QtCore.QRectF(float(x1), float(y1), float(x2 - x1), float(y2 - y1))
        block_area = _rect_area(block_rect)
        if block_area <= 0:
            return None

        best = None
        best_score = 0.0
        for item in text_items:
            try:
                item_rect = item.mapToScene(item.boundingRect()).boundingRect()
            except Exception:
                continue
            if not block_rect.intersects(item_rect):
                continue
            inter = block_rect.intersected(item_rect)
            inter_area = _rect_area(inter)
            if inter_area <= 0:
                continue
            score = inter_area / max(1e-6, min(block_area, _rect_area(item_rect)))
            if score > best_score:
                best_score = score
                best = item

        if best is not None and best_score >= 0.15:
            return best
        return None

    def _select_block(self, blk: object):
        try:
            text_item = self._find_text_item_for_block(blk)
            if text_item is not None:
                self.main.image_viewer.deselect_all()
                text_item.selected = True
                text_item.setSelected(True)
                try:
                    if not getattr(text_item, "editing_mode", False):
                        text_item.item_selected.emit(text_item)
                except Exception:
                    pass
                try:
                    self.main.image_viewer.centerOn(text_item)
                except Exception:
                    pass
                return
        except Exception:
            pass

        try:
            rect = self.main.rect_item_ctrl.find_corresponding_rect(blk, 0.2)
            if rect:
                self.main.image_viewer.select_rectangle(rect)
                return
        except Exception:
            pass

        try:
            self.main.curr_tblock = blk
            self.main.s_text_edit.blockSignals(True)
            self.main.t_text_edit.blockSignals(True)
            self.main.s_text_edit.setPlainText(getattr(blk, "text", "") or "")
            self.main.t_text_edit.setPlainText(getattr(blk, "translation", "") or "")
            self.main.s_text_edit.blockSignals(False)
            self.main.t_text_edit.blockSignals(False)
        except Exception:
            pass

    def _highlight_in_target_edit(self, start: int, end: int):
        try:
            edit = self.main.t_text_edit
            cursor = edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            edit.setTextCursor(cursor)
            edit.ensureCursorVisible()
        except Exception:
            pass

    def _highlight_in_source_edit(self, start: int, end: int):
        try:
            edit = self.main.s_text_edit
            cursor = edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            edit.setTextCursor(cursor)
            edit.ensureCursorVisible()
        except Exception:
            pass

    def _apply_match_selection(self, m, blk: object, focus: bool, preserve_focus_state=None):
        self._select_block(blk)
        if self._gather_options().in_target:
            self._highlight_in_target_edit(m.start, m.end)
            if focus:
                self.main.t_text_edit.setFocus()
        else:
            self._highlight_in_source_edit(m.start, m.end)
            if focus:
                self.main.s_text_edit.setFocus()
        if preserve_focus_state is not None and not focus:
            self._restore_focus_state(preserve_focus_state)

    def _apply_webtoon_fallback_selection(self, m, focus: bool, preserve_focus_state=None):
        state = self.main.image_states.get(m.key.file_path) or {}
        blk = find_block_by_key(state.get("blk_list") or [], m.key)
        if blk is None:
            return
        self._select_block(blk)
        if self._gather_options().in_target:
            self._highlight_in_target_edit(m.start, m.end)
            if focus:
                self.main.t_text_edit.setFocus()
        else:
            self._highlight_in_source_edit(m.start, m.end)
            if focus:
                self.main.s_text_edit.setFocus()
        if preserve_focus_state is not None and not focus:
            self._restore_focus_state(preserve_focus_state)
