from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QSizePolicy, QAbstractItemView
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QContextMenuEvent, QDropEvent
from .dayu_widgets.menu import MMenu
from .dayu_widgets.browser import MClickBrowserFilePushButton


class PageListView(QListWidget):

    del_img = Signal(list)
    toggle_skip_img = Signal(list, bool)  # list of images, bool for skip status (True=skip, False=unskip)
    translate_imgs = Signal(list)
    selection_changed = Signal(list)  # list of selected indices
    order_changed = Signal(list)  # reordered item identities (file paths when available)

    def __init__(self) -> None:
        super().__init__()
        self.setSpacing(5)
        self.setMinimumWidth(100)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) 
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        self.ui_elements()
        
        # Connect selection model changes to emit our custom signal
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def ui_elements(self):
        self.insert_browser = MClickBrowserFilePushButton(multiple=True)
        self.insert_browser.set_dayu_filters([".png", ".jpg", ".jpeg", ".webp", ".bmp",
                                            ".zip", ".cbz", ".cbr", ".cb7", ".cbt",
                                            ".pdf", ".epub"])

    def _on_selection_changed(self, selected, deselected):
        """Handle selection changes and emit signal with selected indices."""
        selected_indices = []
        for item in self.selectedItems():
            index = self.row(item)
            if index >= 0:
                selected_indices.append(index)
        self.selection_changed.emit(selected_indices)

    def _item_identity(self, item) -> str:
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, str) and data:
            return data
        return item.text()

    def _current_item_order(self) -> list[str]:
        order = []
        for idx in range(self.count()):
            item = self.item(idx)
            if item:
                order.append(self._item_identity(item))
        return order

    def dropEvent(self, event: QDropEvent):
        before_order = self._current_item_order()
        super().dropEvent(event)
        after_order = self._current_item_order()
        if after_order and after_order != before_order:
            self.order_changed.emit(after_order)
        self.viewport().update()

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
