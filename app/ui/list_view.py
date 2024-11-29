from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QSizePolicy, QAbstractItemView
from PySide6.QtCore import Qt, QSize

class PageListView(QListWidget):

    def __init__(self) -> None:
        super().__init__()
        self.setSpacing(5)
        self.setMinimumWidth(100)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) 
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
    
    def sizeHint(self) -> QSize:
        # Provide a reasonable default size
        return QSize(100, super().sizeHint().height())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.viewport().update() 

    def setCurrentItem(self, item):
        super().setCurrentItem(item)
        self.viewport().update()


