import math
from PySide6.QtWidgets import QGraphicsRectItem
from PySide6.QtCore import Signal, QObject, QRectF, Qt, QPointF
from PySide6.QtGui import QColor, QBrush, QCursor
from PySide6 import QtCore
from dataclasses import dataclass
from ..dayu_widgets.menu import MMenu

@dataclass
class RectState:
    rect: tuple  # (x1, y1, x2, y2)
    rotation: float
    transform_origin: QPointF

    @classmethod
    def from_item(cls, item):
        """Create TextBlockState from a TextBlockItem"""
        rect = QRectF(item.pos(), item.boundingRect().size()).getCoords()
        return cls(
            rect=rect,
            rotation=item.rotation(),
            transform_origin=item.transformOriginPoint()
        )

class RectSignals(QObject):
    rectangle_changed = Signal(QRectF, float, QPointF)
    change_undo = Signal(RectState, RectState)
    ocr_block = Signal()
    translate_block = Signal()

class MoveableRectItem(QGraphicsRectItem):
    signals = RectSignals()

    def __init__(self, rect=None, parent=None):
        super().__init__(rect, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(QColor(255, 192, 203, 125)))  # Transparent pink
        self.setTransformOriginPoint(self.boundingRect().center())
        self.handle_size = 20
        self.resize_handle = None
        self.resize_start = None
        self.dragging = False
        self.drag_start = None
        self.drag_offset = None
        self.selected = False

        # Rotation properties
        self.rot_handle = None
        self.rotating = True
        self.last_rotation_angle = 0
        self.rotation_smoothing = 1.0 # rotation sensitivity
        self.center_scene_pos = None

        self.old_state = None

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
        scene_pos = self.mapToScene(event.pos())
        local_pos = event.pos()
        self.selected = self.boundingRect().contains(local_pos)

        if event.button() == Qt.MouseButton.LeftButton:
            self.old_state = RectState.from_item(self)
            rect = self.boundingRect()
            handle = self.get_handle_at_position(local_pos, rect)
            if handle:
                self.resize_handle = handle
                self.resize_start = event.scenePos()
            else:
                self.dragging = True
                self.drag_start = scene_pos
                self.drag_offset = scene_pos - self.mapToScene(self.rect().topLeft())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_handle:
            self.resize_rectangle(event.pos())
        elif self.dragging:
            scene_pos = event.scenePos()
            local_pos = self.mapFromScene(scene_pos)
            local_last_scene = self.mapFromScene(event.lastScenePos())
            self.move_rectangle(local_pos, local_last_scene)

    def mouseReleaseEvent(self, event):
        if self.old_state:
            new_state = RectState.from_item(self)
            if self.old_state.rect != new_state.rect:
                self.signals.change_undo.emit(self.old_state, new_state)

        self.dragging = False
        self.drag_offset = None
        self.resize_handle = None
        self.resize_start = None
        self.rotating = False
        self.center_scene_pos = None
        self.update_cursor(event.pos())
        #self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        # Get the global position for the context menu
        scene_pos = event.scenePos()  # Position in the scene
        views = self.scene().views()  # Get all views associated with the scene

        if views:
            view = views[0]
            global_pos = view.mapToGlobal(view.mapFromScene(scene_pos))

            menu = MMenu(parent=view)
            ocr = menu.addAction(view.tr('OCR'))
            translate = menu.addAction(view.tr('Translate'))

            ocr.triggered.connect(self.signals.ocr_block.emit)
            translate.triggered.connect(self.signals.translate_block.emit)

            menu.exec_(global_pos)

            super().contextMenuEvent(event)

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
            cursor = cursors.get(handle, Qt.CursorShape.ArrowCursor)
            # Adjust cursor based on rotation
            rotation = self.rotation() % 360
            if 22.5 <= rotation < 67.5:
                cursor = self.rotate_cursor(cursor, 1)
            elif 67.5 <= rotation < 112.5:
                cursor = self.rotate_cursor(cursor, 2)
            elif 112.5 <= rotation < 157.5:
                cursor = self.rotate_cursor(cursor, 3)
            elif 157.5 <= rotation < 202.5:
                cursor = self.rotate_cursor(cursor, 4)
            elif 202.5 <= rotation < 247.5:
                cursor = self.rotate_cursor(cursor, 5)
            elif 247.5 <= rotation < 292.5:
                cursor = self.rotate_cursor(cursor, 6)
            elif 292.5 <= rotation < 337.5:
                cursor = self.rotate_cursor(cursor, 7)
            return cursor
        elif rect.contains(pos):
            return Qt.CursorShape.SizeAllCursor
        else:
            return Qt.CursorShape.PointingHandCursor
            
    def rotate_cursor(self, cursor, steps):
        cursor_map = {
            Qt.SizeVerCursor: [Qt.SizeVerCursor, Qt.SizeBDiagCursor, Qt.SizeHorCursor, Qt.SizeFDiagCursor] * 2,
            Qt.SizeHorCursor: [Qt.SizeHorCursor, Qt.SizeFDiagCursor, Qt.SizeVerCursor, Qt.SizeBDiagCursor] * 2,
            Qt.SizeFDiagCursor: [Qt.SizeFDiagCursor, Qt.SizeVerCursor, Qt.SizeBDiagCursor, Qt.SizeHorCursor] * 2,
            Qt.SizeBDiagCursor: [Qt.SizeBDiagCursor, Qt.SizeHorCursor, Qt.SizeFDiagCursor, Qt.SizeVerCursor] * 2
        }
        return cursor_map.get(cursor, [cursor] * 8)[steps]

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
    
    def move_rectangle(self, local_pos: QtCore.QPointF, last_scene_pos: QtCore.QPointF):
        delta = self.mapToParent(local_pos) - self.mapToParent(last_scene_pos)
        new_pos = self.pos() + delta
        
        # Calculate the bounding rect of the rotated rectangle in scene coordinates
        scene_rect = self.mapToScene(self.boundingRect())
        bounding_rect = scene_rect.boundingRect()
        
        parent_rect = self.parentItem().boundingRect()
        
        # Constrain the movement
        if bounding_rect.left() + delta.x() < 0:
            new_pos.setX(self.pos().x() - bounding_rect.left())
        elif bounding_rect.right() + delta.x() > parent_rect.width():
            new_pos.setX(self.pos().x() + parent_rect.width() - bounding_rect.right())
        
        if bounding_rect.top() + delta.y() < 0:
            new_pos.setY(self.pos().y() - bounding_rect.top())
        elif bounding_rect.bottom() + delta.y() > parent_rect.height():
            new_pos.setY(self.pos().y() + parent_rect.height() - bounding_rect.bottom())
        
        self.setPos(new_pos)
        
        # Update Textblock
        new_rect = QRectF(new_pos, self.boundingRect().size())
        self.signals.rectangle_changed.emit(new_rect, self.rotation(),
                                             self.transformOriginPoint())

    def init_rotation(self, scene_pos):
        self.rotating = True
        center = self.boundingRect().center()
        self.center_scene_pos = self.mapToScene(center)
        self.last_rotation_angle = math.degrees(math.atan2(
            scene_pos.y() - self.center_scene_pos.y(),
            scene_pos.x() - self.center_scene_pos.x()
        ))

    def rotate_item(self, scene_pos):
        self.setTransformOriginPoint(self.boundingRect().center())
        current_angle = math.degrees(math.atan2(
            scene_pos.y() - self.center_scene_pos.y(),
            scene_pos.x() - self.center_scene_pos.x()
        ))
        
        angle_diff = current_angle - self.last_rotation_angle
        
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360
        
        smoothed_angle = angle_diff / self.rotation_smoothing
        
        new_rotation = self.rotation() + smoothed_angle
        self.setRotation(new_rotation)
        self.last_rotation_angle = current_angle

        # Emit signal for rectangle change
        rect = QRectF(self.pos(), self.boundingRect().size())
        self.signals.rectangle_changed.emit(rect, self.rotation(), 
                                            self.transformOriginPoint())

    def resize_rectangle(self, pos: QtCore.QPointF):
        if not self.resize_start:
            return
            
        # Convert positions to scene coordinates
        scene_pos = self.mapToScene(pos)

        # Get the current rectangle in local coordinates
        current_rect = self.rect()
        new_rect = QRectF(current_rect)

        # Rect Calcs
        # Map scene position back to item coordinates, taking rotation into account
        local_pos = self.mapFromScene(scene_pos)
        
        # Handle different resize handles
        if self.resize_handle == 'top_left':
            new_rect.setTopLeft(local_pos)
        elif self.resize_handle == 'top_right':
            new_rect.setTopRight(local_pos)
        elif self.resize_handle == 'bottom_left':
            new_rect.setBottomLeft(local_pos)
        elif self.resize_handle == 'bottom_right':
            new_rect.setBottomRight(local_pos)
        elif self.resize_handle == 'top':
            new_rect.setTop(local_pos.y())
        elif self.resize_handle == 'bottom':
            new_rect.setBottom(local_pos.y())
        elif self.resize_handle == 'left':
            new_rect.setLeft(local_pos.x())
        elif self.resize_handle == 'right':
            new_rect.setRight(local_pos.x())

        # Ensure minimum size
        min_size = 20
        if new_rect.width() < min_size:
            if 'right' in self.resize_handle:
                new_rect.setRight(new_rect.left() + min_size)
            else:
                new_rect.setLeft(new_rect.right() - min_size)
        
        if new_rect.height() < min_size:
            if 'bottom' in self.resize_handle:
                new_rect.setBottom(new_rect.top() + min_size)
            else:
                new_rect.setTop(new_rect.bottom() - min_size)

        # Calculate the change in position in scene coordinates
        old_pos = self.mapToScene(current_rect.topLeft())
        new_pos = self.mapToScene(new_rect.topLeft())
        pos_delta = new_pos - old_pos
        act_pos = self.pos() + pos_delta
        
        # Convert the new rectangle to scene coordinates to check bounds
        scene_rect = self.mapRectToScene(new_rect)
        parent_rect = self.parentItem().boundingRect()
        
        # Ensure the rectangle stays within parent bounds
        if (scene_rect.left() >= 0 and 
            scene_rect.right() <= parent_rect.right() and
            scene_rect.top() >= 0 and 
            scene_rect.bottom() <= parent_rect.bottom()):
            
            # Update the rectangle
            self.setPos(act_pos)
            self.setRect(0, 0, new_rect.width(), new_rect.height())

            # Emit signal for rectangle change
            rect = QRectF(act_pos, self.boundingRect().size())
            self.signals.rectangle_changed.emit(rect, self.rotation(),
                                                 self.transformOriginPoint())
        