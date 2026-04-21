from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING
from PySide6.QtCore import QRectF, QPointF

from app.ui.canvas.rectangle import MoveableRectItem
from app.ui.canvas.text_item import TextBlockState
from modules.detection.utils.geometry import do_rectangles_overlap
from modules.utils.textblock import TextBlock

if TYPE_CHECKING:
    from controller import ComicTranslate


class RectItemController:
    def __init__(self, main: ComicTranslate):
        self.main = main

    def _current_file_path(self) -> str | None:
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            return self.main.image_files[self.main.curr_img_idx]
        return None

    def _invalidate_current_page_pipeline(self) -> None:
        file_path = self._current_file_path()
        if file_path:
            self.main.stage_nav_ctrl.invalidate_for_box_edit(file_path)

    def connect_rect_item_signals(self, rect_item: MoveableRectItem, force_reconnect: bool = False):
        if getattr(rect_item, "_ct_signals_connected", False) and not force_reconnect:
            return

        if force_reconnect:
            try:
                rect_item.signals.change_undo.disconnect(self.rect_change_undo)
            except (TypeError, RuntimeError):
                pass

        rect_item.signals.change_undo.connect(self.rect_change_undo)
        rect_item._ct_signals_connected = True

    def handle_rectangle_selection(self, rect: QRectF):
        rect = rect.getCoords()
        self.main.curr_tblock = self.find_corresponding_text_block(rect, 0.5)
        if self.main.curr_tblock:
            self.main.s_text_edit.blockSignals(True)
            self.main.t_text_edit.blockSignals(True)
            self.main.s_text_edit.setPlainText(self.main.curr_tblock.text)
            self.main.t_text_edit.setPlainText(self.main.curr_tblock.translation)
            self.main.s_text_edit.blockSignals(False)
            self.main.t_text_edit.blockSignals(False)
        else:
            self.main.s_text_edit.clear()
            self.main.t_text_edit.clear()
            self.main.curr_tblock = None

    def handle_rectangle_creation(self, rect_item: MoveableRectItem):
        self.connect_rect_item_signals(rect_item)
        new_rect = rect_item.mapRectToScene(rect_item.rect())
        x1, y1, w, h = new_rect.getRect()
        x1, y1, w, h = int(x1), int(y1), int(w), int(h)
        new_rect_coords = (x1, y1, x1 + w, y1 + h)

        new_blk = TextBlock(text_bbox=np.array(new_rect_coords))
        rect_item.block_uid = new_blk.block_uid
        if new_blk not in self.main.blk_list:
            self.main.blk_list.append(new_blk)
        self._invalidate_current_page_pipeline()
        self.main.mark_project_dirty()

    def handle_rectangle_deletion(self, rect: QRectF):
        rect_coords = rect.getCoords()
        current_text_block = self.find_corresponding_text_block(rect_coords, 0.5)
        if current_text_block in self.main.blk_list:
            self.main.blk_list.remove(current_text_block)
        self._invalidate_current_page_pipeline()
        self.main.mark_project_dirty()

    def handle_rectangle_change(
            self, 
            old_rect_coords: tuple, 
            new_rect_coords: tuple, 
            new_angle: float, 
            new_tr_origin: QPointF,
            block_uid: str = "",
        ):
        target_blk = None
        if block_uid:
            for blk in self.main.blk_list:
                if getattr(blk, "block_uid", "") == block_uid:
                    target_blk = blk
                    break

        # Fallback to geometry matching if the block UID is not available.
        if target_blk is None:
            for blk in self.main.blk_list:
                if do_rectangles_overlap(blk.xyxy, old_rect_coords, 0.2):
                    target_blk = blk
                    break

        if target_blk is None:
            return

        for blk in self.main.blk_list:
            if blk is target_blk:
                blk.xyxy[:] = [
                    int(new_rect_coords[0]),
                    int(new_rect_coords[1]),
                    int(new_rect_coords[2]),
                    int(new_rect_coords[3]),
                ]
                blk.angle = new_angle if new_angle else 0
                blk.tr_origin_point = (new_tr_origin.x(), new_tr_origin.y()) if new_tr_origin else ()
                break
        self._invalidate_current_page_pipeline()
        self.main.mark_project_dirty()

    def rect_change_undo(self, old_state, new_state):
        if isinstance(old_state, TextBlockState) or isinstance(new_state, TextBlockState):
            handler = getattr(getattr(self.main, "text_ctrl", None), "on_text_item_geometry_changed", None)
            if callable(handler):
                handler(old_state, new_state)
            else:
                self.main.mark_project_dirty()
            return

        self.handle_rectangle_change(
            old_state.rect, 
            new_state.rect,
            new_state.rotation,
            new_state.transform_origin,
            getattr(new_state, "block_uid", "") or getattr(old_state, "block_uid", ""),
        )
        try:
            if getattr(self.main, "curr_tblock_item", None) is not None:
                current_file = self.main.text_ctrl._current_file_path()
                if current_file:
                    self.main.text_ctrl._sync_current_render_snapshot(
                        current_file,
                        update_style_overrides=True,
                    )
        except Exception:
            pass
        self.main.mark_project_dirty()


    def find_corresponding_text_block(self, rect: tuple[float], iou_threshold: int = 0.5):
        for blk in self.main.blk_list:
            if do_rectangles_overlap(rect, blk.xyxy, iou_threshold):
                return blk
        return None

    def find_corresponding_rect(self, tblock: TextBlock, iou_threshold: int):
        for rect in self.main.image_viewer.rectangles:
            if getattr(rect, "block_uid", "") and getattr(tblock, "block_uid", ""):
                if getattr(rect, "block_uid", "") == getattr(tblock, "block_uid", ""):
                    return rect
            mp_rect = rect.mapRectToScene(rect.rect())
            x1, y1, w, h = mp_rect.getRect()
            rect_coord = (x1, y1, x1 + w, y1 + h)
            if do_rectangles_overlap(rect_coord, tblock.xyxy, iou_threshold):
                return rect
        return None
