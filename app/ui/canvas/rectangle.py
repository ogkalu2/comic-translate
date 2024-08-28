from PySide6.QtWidgets import QGraphicsRectItem
from PySide6.QtCore import Signal, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QCursor
from PySide6 import QtCore


class RectSignals(QObject):
    rectangle_changed = Signal(QRectF)

class MovableRectItem(QGraphicsRectItem):
    signals = RectSignals()

    def __init__(self, rect=None, parent=None):
        super().__init__(rect, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(QColor(255, 192, 203, 125)))  # Transparent pink
        self.handle_size = 20
        self._resize_handle = None
        self._resize_start = None
        self._dragging = False
        self._drag_start = None
        self._drag_offset = None
        self.selected = False

    def hoverMoveEvent(self, event):
        if self.selected:
            self.update_cursor(event.pos())
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def focusOutEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.selected = False
        self.update()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos().toPoint())
        local_pos = self.mapFromScene(scene_pos)
        self.selected = self.boundingRect().contains(local_pos)

        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.boundingRect()
            handle = self.get_handle_at_position(event.pos(), rect)
            if handle:
                self._resize_handle = handle
                self._resize_start = scene_pos
            else:
                self._dragging = True
                self._drag_start = scene_pos
                self._drag_offset = scene_pos - self.rect().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.parentItem().mapToScene(event.pos().toPoint())
        if self._resize_handle:
            self.resize_rectangle(event.pos())
        elif self._dragging:
            self.move_rectangle(scene_pos)
            #super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._drag_offset = None
        self._resize_handle = None
        self._resize_start = None
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().mouseReleaseEvent(event)

    def update_cursor(self, pos):
        cursor = self.get_cursor_for_position(pos)
        self.setCursor(QCursor(cursor))

    def get_cursor_for_position(self, pos):
        rect = self.boundingRect()
        handle = self.get_handle_at_position(pos, rect)
        
        cursors = {
            'top_left': Qt.CursorShape.SizeFDiagCursor,
            'top_right': Qt.CursorShape.SizeBDiagCursor,
            'bottom_left': Qt.CursorShape.SizeBDiagCursor,
            'bottom_right': Qt.CursorShape.SizeFDiagCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
        }
        
        if handle:
            return cursors.get(handle, Qt.CursorShape.ArrowCursor)
        elif rect.contains(pos):
            return Qt.CursorShape.SizeAllCursor
        else:
            return Qt.CursorShape.PointingHandCursor

    def get_handle_at_position(self, pos, rect):
        handle_size = self.handle_size
        rect_rect = rect.toRect()
        top_left = rect_rect.topLeft()
        bottom_right = rect_rect.bottomRight()

        handles = {
            'top_left': QRectF(top_left.x() - handle_size/2, top_left.y() - handle_size/2, handle_size, handle_size),
            'top_right': QRectF(bottom_right.x() - handle_size/2, top_left.y() - handle_size/2, handle_size, handle_size),
            'bottom_left': QRectF(top_left.x() - handle_size/2, bottom_right.y() - handle_size/2, handle_size, handle_size),
            'bottom_right': QRectF(bottom_right.x() - handle_size/2, bottom_right.y() - handle_size/2, handle_size, handle_size),
            'top': QRectF(top_left.x(), top_left.y() - handle_size/2, rect_rect.width(), handle_size),
            'bottom': QRectF(top_left.x(), bottom_right.y() - handle_size/2, rect_rect.width(), handle_size),
            'left': QRectF(top_left.x() - handle_size/2, top_left.y(), handle_size, rect_rect.height()),
            'right': QRectF(bottom_right.x() - handle_size/2, top_left.y(), handle_size, rect_rect.height()),
        }

        for handle, handle_rect in handles.items():
            if handle_rect.contains(pos):
                return handle

        return None
    
    def move_rectangle(self, scene_pos: QtCore.QPointF):
        new_pos = scene_pos
        new_top_left = new_pos - self._drag_offset
        new_rect = QRectF(new_top_left, self.rect().size())
        constrained_rect = self.constrain_rect(new_rect)
        self.setRect(constrained_rect)
        
        # Emit the rectangle_moved signal
        self.signals.rectangle_changed.emit(constrained_rect)

    def constrain_rect(self, rect: QRectF):
        photo_rect = self.parentItem().boundingRect()
        new_x = max(0, min(rect.x(), photo_rect.width() - rect.width()))
        new_y = max(0, min(rect.y(), photo_rect.height() - rect.height()))
        return QRectF(new_x, new_y, rect.width(), rect.height())
    
    def resize_rectangle(self, pos: QtCore.QPointF):
        if not self._resize_handle:
            return

        rect = self.rect()
        dx = pos.x() - self._resize_start.x()
        dy = pos.y() - self._resize_start.y()

        new_rect = QRectF(rect)

        if self._resize_handle in ['top_left', 'left', 'bottom_left']:
            new_rect.setLeft(rect.left() + dx)
        if self._resize_handle in ['top_left', 'top', 'top_right']:
            new_rect.setTop(rect.top() + dy)
        if self._resize_handle in ['top_right', 'right', 'bottom_right']:
            new_rect.setRight(rect.right() + dx)
        if self._resize_handle in ['bottom_left', 'bottom', 'bottom_right']:
            new_rect.setBottom(rect.bottom() + dy)

        # Ensure the rectangle doesn't flip inside out
        if new_rect.width() < 10:
            if 'left' in self._resize_handle:
                new_rect.setLeft(new_rect.right() - 10)
            else:
                new_rect.setRight(new_rect.left() + 10)
        if new_rect.height() < 10:
            if 'top' in self._resize_handle:
                new_rect.setTop(new_rect.bottom() - 10)
            else:
                new_rect.setBottom(new_rect.top() + 10)

        constrained_rect = self.constrain_rect(new_rect)
        self.setRect(constrained_rect)
        self._resize_start = pos

        # Emit the rectangle_resized signal
        self.signals.rectangle_changed.emit(constrained_rect)
