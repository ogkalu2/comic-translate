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
        self.before_erase = before_erase or [] 
        self.after_erase = after_erase or []    
        self.first = True

    def redo(self):
        if self.first:
            self.first = False
            return
        self.restore_scene_state(self.after_erase)

    def undo(self):
        self.restore_scene_state(self.before_erase)

    def restore_scene_state(self, target_properties_list):
        """Restore the scene to match the target state by comparing with current state."""
        # Get current path items in the scene
        photo_item = getattr(self.viewer, 'photo', None)
        current_items = [
            item for item in self.scene.items() 
            if (isinstance(item, QGraphicsPathItem) and 
                item != photo_item and
                hasattr(item, 'path'))  # Ensure item has path method
        ]
        
        # Get current properties for comparison
        current_properties = []
        for item in current_items:
            try:
                props = self.save_path_properties(item)
                if props:
                    current_properties.append(props)
            except Exception as e:
                print(f"Warning: Failed to save properties for item: {e}")
                continue
        
        # Create sets for efficient comparison
        def props_to_key(props):
            """Convert properties to a comparable key."""
            try:
                # Convert path to a string representation for comparison
                path_str = ""
                if props.get('path'):
                    path = props['path']
                    for i in range(path.elementCount()):
                        element = path.elementAt(i)
                        path_str += f"{element.type},{element.x:.2f},{element.y:.2f};"
                
                return (
                    path_str,
                    props.get('pen', ''),
                    props.get('brush', ''),
                    props.get('width', 0),
                )
            except Exception:
                # Fallback for corrupted properties
                return str(id(props))
        
        current_keys = {props_to_key(props): (props, item) for props, item in zip(current_properties, current_items)}
        target_keys = {props_to_key(props): props for props in target_properties_list}
        
        # Find items to remove (in current but not in target)
        items_to_remove = []
        for key in current_keys:
            if key not in target_keys:
                _, item = current_keys[key]
                items_to_remove.append(item)
        
        # Remove items that shouldn't exist in target state
        for item in items_to_remove:
            try:
                self.scene.removeItem(item)
            except Exception as e:
                print(f"Warning: Failed to remove item: {e}")
        
        # Find properties to add (in target but not in current)
        props_to_add = []
        for key in target_keys:
            if key not in current_keys:
                props_to_add.append(target_keys[key])
        
        # Add items that should exist in target state
        for properties in props_to_add:
            try:
                path_item = self.create_path_item(properties)
                if path_item:  # Only add if creation was successful
                    self.scene.addItem(path_item)
            except Exception as e:
                print(f"Warning: Failed to create path item during undo/redo: {e}")
                continue

        self.scene.update()
