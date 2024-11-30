from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QSizePolicy, QAbstractItemView
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QContextMenuEvent
from .dayu_widgets.menu import MMenu
from .dayu_widgets.browser import MClickBrowserFilePushButton


class PageListView(QListWidget):

    del_img = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setSpacing(5)
        self.setMinimumWidth(100)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) 
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        self.ui_elements()

    def ui_elements(self):
        self.insert_browser = MClickBrowserFilePushButton(multiple=True)
        self.insert_browser.set_dayu_filters([".png", ".jpg", ".jpeg", ".webp", ".bmp",
                                            ".zip", ".cbz", ".cbr", ".cb7", ".cbt",
                                            ".pdf", ".epub"])

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = MMenu(parent=self)
        insert = menu.addAction(self.tr('Insert'))
        delete_act = menu.addAction(self.tr('Delete'))

        insert.triggered.connect(self.insert_browser.clicked)
        delete_act.triggered.connect(self.delete_selected_items)

        menu.exec_(event.globalPos())

        super().contextMenuEvent(event)

    def delete_selected_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return

        selected_file_names = [item.text() for item in selected_items]
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


