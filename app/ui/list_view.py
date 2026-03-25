from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QSizePolicy, QAbstractItemView, QStyledItemDelegate, QStyle
from PySide6.QtCore import Signal, Qt, QSize, QRect
from PySide6.QtGui import QContextMenuEvent, QDropEvent, QPainter, QPixmap, QFont
from .dayu_widgets.menu import MMenu
from .dayu_widgets.browser import MClickBrowserFilePushButton


class PageListItemDelegate(QStyledItemDelegate):
    """Paint lightweight page rows without instantiating a widget per item."""

    THUMB_SIZE = QSize(35, 50)
    ROW_HEIGHT = 60
    MARGIN_X = 8
    GAP = 10

    def paint(self, painter: QPainter, option, index):
        painter.save()

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        background = option.palette.highlight().color() if selected else option.palette.base().color()
        painter.fillRect(option.rect, background)

        thumb_rect = self._thumbnail_rect(option.rect)
        thumb_data = index.data(Qt.ItemDataRole.DecorationRole)
        pixmap = thumb_data if isinstance(thumb_data, QPixmap) else None

        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            draw_x = thumb_rect.x() + (thumb_rect.width() - scaled.width()) // 2
            draw_y = thumb_rect.y() + (thumb_rect.height() - scaled.height()) // 2
            painter.drawPixmap(draw_x, draw_y, scaled)
        else:
            painter.fillRect(thumb_rect, option.palette.alternateBase())
            painter.setPen(option.palette.mid().color())
            painter.drawRect(thumb_rect.adjusted(0, 0, -1, -1))

        text_rect = option.rect.adjusted(
            self.MARGIN_X + self.THUMB_SIZE.width() + self.GAP,
            0,
            -self.MARGIN_X,
            0,
        )
        font = option.font
        font_data = index.data(Qt.ItemDataRole.FontRole)
        strike_out = isinstance(font_data, QFont) and font_data.strikeOut()
        font.setStrikeOut(False)
        painter.setFont(font)

        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        metrics = painter.fontMetrics()
        text = metrics.elidedText(str(text), Qt.TextElideMode.ElideMiddle, text_rect.width())

        pen_color = option.palette.highlightedText().color() if selected else option.palette.text().color()
        if strike_out and not selected:
            pen_color = option.palette.mid().color()
        painter.setPen(pen_color)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        if strike_out:
            line_y = text_rect.center().y()
            painter.drawLine(text_rect.left(), line_y, text_rect.left() + metrics.horizontalAdvance(text), line_y)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(self.THUMB_SIZE.width() + 120, self.ROW_HEIGHT)

    def _thumbnail_rect(self, rect):
        top = rect.y() + (rect.height() - self.THUMB_SIZE.height()) // 2
        return QRect(self.MARGIN_X + rect.x(), top, self.THUMB_SIZE.width(), self.THUMB_SIZE.height())


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
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) 
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        self.setIconSize(PageListItemDelegate.THUMB_SIZE)
        self.setItemDelegate(PageListItemDelegate(self))
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

        selected_paths = []
        for item in selected_items:
            data = item.data(Qt.ItemDataRole.UserRole)
            selected_paths.append(data if isinstance(data, str) and data else item.text())
        self.del_img.emit(selected_paths)

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
