from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING, Tuple
from PySide6.QtCore import QRectF

from app.ui.canvas.rectangle import MoveableRectItem
from app.ui.commands.box import AddRectangleCommand, BoxesChangeCommand

from modules.detection.utils.general import do_rectangles_overlap, get_inpaint_bboxes
from modules.utils.textblock import TextBlock

if TYPE_CHECKING:
    from controller import ComicTranslate


class RectItemController:
    def __init__(self, main: ComicTranslate):
        self.main = main

    def connect_rect_item_signals(self, rect_item: MoveableRectItem):
        rect_item.signals.rectangle_changed.connect(self.handle_rectangle_change)
        rect_item.signals.change_undo.connect(self.rect_change_undo)
        rect_item.signals.ocr_block.connect(lambda: self.main.ocr(True))
        rect_item.signals.translate_block.connect(lambda: self.main.translate_image(True))

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
        image = self.main.image_viewer.get_cv2_image()
        inpaint_boxes = get_inpaint_bboxes(new_rect_coords, image)

        new_blk = TextBlock(text_bbox=np.array(new_rect_coords), inpaint_bboxes=inpaint_boxes)
        self.main.blk_list.append(new_blk)

        command = AddRectangleCommand(self.main, rect_item, new_blk, self.main.blk_list)
        self.main.undo_group.activeStack().push(command)

    def handle_rectangle_deletion(self, rect: QRectF):
        rect_coords = rect.getCoords()
        current_text_block = self.find_corresponding_text_block(rect_coords, 0.5)
        self.main.blk_list.remove(current_text_block)

    def handle_rectangle_change(self, new_rect: QRectF, angle: float, tr_origin: Tuple):
        # Find the corresponding TextBlock in blk_list
        for blk in self.main.blk_list:
            if do_rectangles_overlap(blk.xyxy, (new_rect.left(), new_rect.top(), new_rect.right(), new_rect.bottom()), 0.2):
                # Update the TextBlock coordinates
                blk.xyxy[:] = [int(new_rect.left()), int(new_rect.top()), int(new_rect.right()), int(new_rect.bottom())]
                blk.angle = angle if angle else 0
                blk.tr_origin_point = (tr_origin.x(), tr_origin.y()) if tr_origin else ()
                image = self.main.image_viewer.get_cv2_image()
                inpaint_bboxes = get_inpaint_bboxes(blk.xyxy, image)
                blk.inpaint_bboxes = inpaint_bboxes
                break

    def rect_change_undo(self, old_state, new_state):
        command = BoxesChangeCommand(self.main.image_viewer, old_state,
                                         new_state, self.main.blk_list)
        self.main.undo_group.activeStack().push(command)

    def find_corresponding_text_block(self, rect: Tuple[float], iou_threshold: int = 0.5):
        for blk in self.main.blk_list:
            if do_rectangles_overlap(rect, blk.xyxy, iou_threshold):
                return blk
        return None

    def find_corresponding_rect(self, tblock: TextBlock, iou_threshold: int):
        for rect in self.main.image_viewer.rectangles:
            mp_rect = rect.mapRectToScene(rect.rect())
            x1, y1, w, h = mp_rect.getRect()
            rect_coord = (x1, y1, x1 + w, y1 + h)
            if do_rectangles_overlap(rect_coord, tblock.xyxy, iou_threshold):
                return rect
        return None
