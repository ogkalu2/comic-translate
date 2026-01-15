from PySide6.QtGui import QUndoCommand


class TextEditCommand(QUndoCommand):
    def __init__(self, main, text_item, old_text: str, new_text: str,
                 old_html: str | None = None, new_html: str | None = None, blk=None):
        super().__init__()
        self.main = main
        self.text_item = text_item
        self.old_text = old_text
        self.new_text = new_text
        self.old_html = old_html
        self.new_html = new_html
        self.blk = blk

    def _apply(self, text: str, html: str | None):
        self.main.text_ctrl.apply_text_from_command(self.text_item, text, html=html, blk=self.blk)

    def redo(self):
        self._apply(self.new_text, self.new_html)

    def undo(self):
        self._apply(self.old_text, self.old_html)
