from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QGraphicsPathItem
from .base import PathCommandBase

class BrushStrokeCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer, path_item):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.properties = self.save_path_properties(path_item)

    def undo(self):
        matching_item = self.find_matching_item(self.scene, self.properties)
        if matching_item:
            self.scene.removeItem(matching_item)
            self.scene.update()

    def redo(self):
        if not self.find_matching_item(self.scene, self.properties):
            path_item = self.create_path_item(self.properties)
            self.scene.addItem(path_item)
            self.scene.update()

class SegmentBoxesCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer, path_items):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.properties_list = [self.save_path_properties(item) for item in path_items]

    def undo(self):
        for properties in self.properties_list:
            item = self.find_matching_item(self.scene, properties)
            if item:
                self.scene.removeItem(item)
        self.scene.update()

    def redo(self):
        for properties in self.properties_list:
            if not self.find_matching_item(self.scene, properties):
                path_item = self.create_path_item(properties)
                self.scene.addItem(path_item)
        self.scene.update()

class ClearBrushStrokesCommand(QUndoCommand, PathCommandBase):
    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self.scene = viewer._scene
        self.properties_list = []
        
    def undo(self):
        for properties in self.properties_list:
            path_item = self.create_path_item(properties)
            self.scene.addItem(path_item)
        self.scene.update()
        
    def redo(self):
        self.properties_list = []
        for item in self.scene.items():
            if isinstance(item, QGraphicsPathItem) and item != self.viewer._photo:
                self.properties_list.append(self.save_path_properties(item))
                self.scene.removeItem(item)
        self.scene.update()