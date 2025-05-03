from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QSizePolicy, QAbstractItemView
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QContextMenuEvent
from .dayu_widgets.menu import MMenu
from .dayu_widgets.browser import MClickBrowserFilePushButton


class PageListView(QListWidget):

    del_img = Signal(list)
    toggle_skip_img = Signal(list, bool)  # list of images, bool for skip status (True=skip, False=unskip)
    translate_imgs = Signal(list)

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

        # decide whether to show "Skip" or "Unskip"
        selected = self.selectedItems()
        if selected and all(item.font().strikeOut() for item in selected):
            action = menu.addAction(self.tr('Unskip'))
            action.triggered.connect(self.toggle_skip_status)
        else:
            action = menu.addAction(self.tr('Skip'))
            action.triggered.connect(self.toggle_skip_status)

        insert.triggered.connect(self.insert_browser.clicked)
        delete_act.triggered.connect(self.delete_selected_items)

        translate_act = menu.addAction(self.tr('Translate'))
        translate_act.triggered.connect(self.translate_selected_items)

        menu.exec_(event.globalPos())
        super().contextMenuEvent(event)

    def sizeHint(self) -> QSize:
        # Provide a reasonable default size
        return QSize(100, super().sizeHint().height())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.viewport().update() 

    def setCurrentItem(self, item):
        super().setCurrentItem(item)
        self.viewport().update()

    def delete_selected_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return

        selected_file_names = [item.text() for item in selected_items]
        self.del_img.emit(selected_file_names)

    def toggle_skip_status(self):
        selected = self.selectedItems()
        if not selected:
            return
            
        names = [item.text() for item in selected]
        # If all selected items are striked out, we're unskipping (False)
        # Otherwise, we're skipping (True)
        skip_status = not all(item.font().strikeOut() for item in selected)
        self.toggle_skip_img.emit(names, skip_status)

    def translate_selected_items(self):
        selected = self.selectedItems()
        if not selected:
            return
        names = [item.text() for item in selected]
        self.translate_imgs.emit(names)


