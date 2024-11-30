from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QSizePolicy, QAbstractItemView
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QContextMenuEvent
from .dayu_widgets.menu import MMenu


class PageListView(QListWidget):

    del_img = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setSpacing(5)
        self.setMinimumWidth(100)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) 
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

    def contextMenuEvent(self, event: QContextMenuEvent):
        # Create the context menu
        menu = MMenu(parent=self)
        delete_act = menu.addAction(self.tr('Delete'))
        result = menu.exec_(event.globalPos())

        # Handle the delete action
        if result == delete_act:
            self.delete_selected_items()

        super().contextMenuEvent(event)

    def delete_selected_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return

        # Collect the file names of selected items
        selected_file_names = [item.text() for item in selected_items]

        # Emit the signal with file names of deleted images
        self.del_img.emit(selected_file_names)
    
    def sizeHint(self) -> QSize:
        # Provide a reasonable default size
        return QSize(100, super().sizeHint().height())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.viewport().update() 

    def setCurrentItem(self, item):
        super().setCurrentItem(item)
        self.viewport().update()


