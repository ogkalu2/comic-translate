import numpy as np
from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QRectF, QPointF

from modules.detection.utils.general import get_inpaint_bboxes
from .base import RectCommandBase
from ..canvas.rectangle import MoveableRectItem
from ..canvas.text_item import TextBlockItem


class AddRectangleCommand(QUndoCommand, RectCommandBase):
    def __init__(self, main_page, rect_item, blk, blk_list):
        super().__init__()
        self.viewer = main_page.image_viewer
        self.scene = self.viewer._scene
        self.photo = self.viewer.photo
        self.blk_list = blk_list
        self.rect_properties = self.save_rect_properties(rect_item)
        self.blk_properties = self.save_blk_properties(blk)

    def redo(self):
        if not self.find_matching_rect(self.scene, self.rect_properties):
            rect_item = self.create_rect_item(self.rect_properties, self.photo)
            self.viewer.connect_rect_item.emit(rect_item)
            self.viewer.rectangles.append(rect_item)

        if not self.find_matching_blk(self.blk_list, self.blk_properties):
            blk = self.create_new_blk(self.blk_properties)
            self.blk_list.append(blk)

    def undo(self):
        matching_item = self.find_matching_rect(self.scene, self.rect_properties)
        matching_blk = self.find_matching_blk(self.blk_list, self.blk_properties)

        if matching_item:
            self.scene.removeItem(matching_item)
            self.viewer.rectangles.remove(matching_item)

        if matching_blk:
            self.blk_list.remove(matching_blk)

class BoxesChangeCommand(QUndoCommand, RectCommandBase):
    def __init__(self, viewer, old_state, new_state, blk_list):
        super().__init__()
        self.viewer = viewer
        self.scene = self.viewer._scene
        self.blk_list = blk_list
        
        self.old_xyxy = [int(c) for c in old_state.rect]
        self.old_angle = old_state.rotation
        self.old_tr_origin = (old_state.transform_origin.x(), old_state.transform_origin.y())

        self.new_xyxy = [int(c) for c in new_state.rect]
        self.new_angle = new_state.rotation
        self.new_tr_origin = (new_state.transform_origin.x(), new_state.transform_origin.y())

    def redo(self):
        for blk in self.blk_list:
            if (np.array_equal(blk.xyxy, self.old_xyxy) and
                blk.angle == self.old_angle):
            
                blk.xyxy[:] = self.new_xyxy
                blk.angle = self.new_angle
                blk.tr_origin_point = self.new_tr_origin
                image = self.viewer.get_cv2_image()
                inpaint_bboxes = get_inpaint_bboxes(blk.xyxy, image)
                blk.inpaint_bboxes = inpaint_bboxes

                self.find_and_update_item(self.scene, self.old_xyxy, self.old_angle, 
                                                self.new_xyxy, self.new_angle, self.new_tr_origin)
                self.scene.update()

    def undo(self):
        for blk in self.blk_list:
            if (np.array_equal(blk.xyxy, self.new_xyxy) and
                blk.angle == self.new_angle ):
                
                blk.xyxy[:] = self.old_xyxy
                blk.angle = self.old_angle
                blk.tr_origin_point = self.old_tr_origin
                image = self.viewer.get_cv2_image()
                inpaint_bboxes = get_inpaint_bboxes(blk.xyxy, image)
                blk.inpaint_bboxes = inpaint_bboxes

                self.find_and_update_item(self.scene, self.new_xyxy, self.new_angle, 
                                        self.old_xyxy, self.old_angle, self.old_tr_origin)
                self.scene.update()

    @staticmethod
    def find_and_update_item(scene, old_xyxy, old_angle, new_xyxy, new_angle, new_tr_origin):
        for item in scene.items():
            # Check if item position and properties match
            if (isinstance(item, (MoveableRectItem, TextBlockItem)) and
                int(item.pos().x()) == int(old_xyxy[0]) and 
                int(item.pos().y()) == int(old_xyxy[1]) and
                int(item.rotation()) == int(old_angle)):

                new_width = new_xyxy[2] - new_xyxy[0]
                new_height = new_xyxy[3] - new_xyxy[1]

                if isinstance(item, MoveableRectItem):
                    rect = QRectF(0, 0, new_width, new_height)
                    item.setRect(rect)

                item.setTransformOriginPoint(QPointF(*new_tr_origin))
                item.setPos(new_xyxy[0], new_xyxy[1])
                item.setRotation(new_angle)
            
class ClearRectsCommand(QUndoCommand, RectCommandBase):
    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.photo = viewer.photo
        self.properties_list = []
        
    def undo(self):
        for properties in self.properties_list:
            rect_item = self.create_rect_item(properties, self.photo)
            self.viewer.connect_rect_item.emit(rect_item)
            self.viewer.rectangles.append(rect_item)
        self.scene.update()
        
    def redo(self):
        self.properties_list = []
        for item in self.scene.items():
            if isinstance(item, MoveableRectItem) and item != self.photo:
                self.properties_list.append(self.save_rect_properties(item))
                self.scene.removeItem(item)
                self.viewer.selected_rect = None
        self.scene.update()
    
class DeleteBoxesCommand(QUndoCommand, RectCommandBase):
    def __init__(self, main_page, rect_item, text_item, blk, blk_list):
        super().__init__()
        self.ct = main_page
        self.viewer = main_page.image_viewer
        self.photo = self.viewer.photo
        self.scene = self.viewer._scene
        self.rect_properties = self.save_rect_properties(rect_item) if rect_item else None
        self.txt_item_prp = self.save_txt_item_properties(text_item) if text_item else None
        self.blk_properties = self.save_blk_properties(blk)
        self.blk_list = blk_list

    def redo(self):
        matching_rect = self.find_matching_rect(self.scene, self.rect_properties) if self.rect_properties else None
        matching_txt_item = self.find_matching_txt_item(self.scene, self.txt_item_prp) if self.txt_item_prp else None
        matching_blk = self.find_matching_blk(self.blk_list, self.blk_properties)

        if matching_rect:
            self.scene.removeItem(matching_rect)
            self.viewer.rectangles.remove(matching_rect)
            self.viewer.selected_rect = None
            self.scene.update()

        if matching_blk:
            self.blk_list.remove(matching_blk)
            self.ct.curr_tblock = None

        if matching_txt_item:
            self.scene.removeItem(matching_txt_item)
            self.viewer.text_items.remove(matching_txt_item)
            self.ct.curr_tblock_item = None
            self.scene.update()

    def undo(self):
        if self.rect_properties and not self.find_matching_rect(self.scene, self.rect_properties):
            rect_item = self.create_rect_item(self.rect_properties, self.photo)
            self.viewer.connect_rect_item.emit(rect_item)
            self.viewer.rectangles.append(rect_item)
            self.scene.update()

        if not self.find_matching_blk(self.blk_list, self.blk_properties):
            blk = self.create_new_blk(self.blk_properties)
            self.blk_list.append(blk)

        if self.txt_item_prp and not self.find_matching_txt_item(self.scene, self.txt_item_prp):
            text_item = self.create_new_txt_item(self.txt_item_prp, self.photo)
            self.viewer.connect_text_item.emit(text_item)
            self.scene.addItem(text_item)
            self.viewer.text_items.append(text_item)

class AddTextItemCommand(QUndoCommand, RectCommandBase):
    def __init__(self, main_page, text_item):
        super().__init__()
        self.viewer = main_page.image_viewer
        self.photo = self.viewer.photo
        self.scene = self.viewer._scene
        self.txt_item_prp = self.save_txt_item_properties(text_item)

    def redo(self):
        if not self.find_matching_txt_item(self.scene, self.txt_item_prp):
            text_item = self.create_new_txt_item(self.txt_item_prp, self.photo)
            self.viewer.connect_text_item.emit(text_item)
            self.scene.addItem(text_item)
            self.viewer.text_items.append(text_item)

    def undo(self):
        matching_txt_item = self.find_matching_txt_item(self.scene, self.txt_item_prp)
        if matching_txt_item:
            self.scene.removeItem(matching_txt_item)
            self.viewer.text_items.remove(matching_txt_item)
            self.scene.update()

 

