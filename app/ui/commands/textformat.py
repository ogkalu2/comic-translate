from PySide6.QtGui import QUndoCommand
from .base import RectCommandBase

class TextFormatCommand(QUndoCommand, RectCommandBase):
    def __init__(self, viewer, old_item, new_item):
        super().__init__()
        self.scene = viewer._scene
        self.old_dict = old_item.__dict__.copy()
        self.new_dict = new_item.__dict__.copy()
        self.new_item_prp = self.save_txt_item_properties(new_item)
        self.old_item_prp = self.save_txt_item_properties(old_item)
        self.old_html = old_item.toHtml()
        self.new_html = new_item.toHtml()

    def redo(self):
        matching_item = self.find_matching_txt_item(self.scene, self.old_item_prp)
        if matching_item:
            matching_item.set_text(self.new_html, self.new_item_prp['width'])
            matching_item.__dict__.update(self.new_dict)
            matching_item.update()

    def undo(self):
        matching_item = self.find_matching_txt_item(self.scene, self.new_item_prp)
        if matching_item:
            matching_item.set_text(self.old_html, self.old_item_prp['width'])
            matching_item.__dict__.update(self.old_dict)
            matching_item.update()