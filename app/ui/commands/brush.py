from typing import List
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QGraphicsPathItem
from .base import PathCommandBase, PathProperties

class BrushStrokeCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer, path_item: QGraphicsPathItem):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.properties = self.save_path_properties(path_item)


    def redo(self):
        if not self.find_matching_item(self.scene, self.properties):
            path_item = self.create_path_item(self.properties)
            self.scene.addItem(path_item)
            self.scene.update()

    def undo(self):
        matching_item = self.find_matching_item(self.scene, self.properties)
        if matching_item:
            self.scene.removeItem(matching_item)
            self.scene.update()

class SegmentBoxesCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer, path_items: List[QGraphicsPathItem]):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.properties_list = [self.save_path_properties(item) for item in path_items]

    def redo(self):
        for properties in self.properties_list:
            if not self.find_matching_item(self.scene, properties):
                path_item = self.create_path_item(properties)
                self.scene.addItem(path_item)
        self.scene.update()

    def undo(self):
        for properties in self.properties_list:
            item = self.find_matching_item(self.scene, properties)
            if item:
                self.scene.removeItem(item)
        self.scene.update()

class ClearBrushStrokesCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.properties_list = []

    def redo(self):
        self.properties_list = []
        for item in self.scene.items():
            if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo:
                self.properties_list.append(self.save_path_properties(item))
                self.scene.removeItem(item)
        self.scene.update()
        
    def undo(self):
        for properties in self.properties_list:
            path_item = self.create_path_item(properties)
            self.scene.addItem(path_item)
        self.scene.update()
        
class EraseUndoCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer, before_erase: PathProperties, after_erase: PathProperties):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.before_erase = before_erase
        self.after_erase = after_erase
        self.first = True

    def redo(self):
        if self.first:
            self.first = False
            return
        self.update_scene(self.after_erase)

    def undo(self):
        self.update_scene(self.before_erase)

    def update_scene(self, properties_list):
        items_to_remove = [
            item for item in self.scene.items() 
            if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo
        ]
        for item in items_to_remove:
            self.scene.removeItem(item)

        for properties in properties_list:
            path_item = self.create_path_item(properties)
            self.scene.addItem(path_item)

        self.scene.update()
