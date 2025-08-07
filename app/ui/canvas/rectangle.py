import math
from PySide6.QtWidgets import QGraphicsRectItem
from PySide6.QtCore import Signal, QObject, QRectF, Qt, QPointF
from PySide6.QtGui import QColor, QBrush, QCursor
from PySide6 import QtCore
from PySide6.QtGui import QTransform, QPolygonF
from dataclasses import dataclass
from ..dayu_widgets.menu import MMenu

@dataclass
class RectState:
    rect: tuple  # (x1, y1, x2, y2)
    rotation: float
    transform_origin: QPointF

    @classmethod
    def from_item(cls, item: QGraphicsRectItem):
        """Create RectState from a MoveableRectItem"""
        rect = QRectF(item.pos(), item.boundingRect().size()).getCoords()
        return cls(
            rect=rect,
            rotation=item.rotation(),
            transform_origin=item.transformOriginPoint()
        )

class RectSignals(QObject):
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
        self.setZValue(1)
        
        self.resize_handle = None
        self.resize_start = None
        self.selected = False
        self.resizing = False

        # Rotation properties
        self.rot_handle = None
        self.rotating = False
        self.last_rotation_angle = 0
        self.rotation_smoothing = 1.0 # rotation sensitivity
        self.center_scene_pos = None

        self.old_state = None

    def focusOutEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.selected = False
        self.update()
        super().focusOutEvent(event)

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
    
    def move_item(self, local_pos: QtCore.QPointF, last_local_pos: QtCore.QPointF):
        delta = self.mapToParent(local_pos) - self.mapToParent(last_local_pos)
        new_pos = self.pos() + delta
        
        # Calculate the bounding rect of the rotated rectangle in scene coordinates
        scene_rect = self.mapToScene(self.boundingRect())
        bounding_rect = scene_rect.boundingRect()
        
        # Get constraint bounds - use parent if available, otherwise use scene rect
        if self.parentItem():
            parent_rect = self.parentItem().boundingRect()
        else:
            # In webtoon mode or when no parent, use scene bounds
            scene_rect = self.scene().sceneRect()
            parent_rect = scene_rect
        
        # Constrain the movement
        if bounding_rect.left() + delta.x() < parent_rect.left():
            new_pos.setX(self.pos().x() - (bounding_rect.left() - parent_rect.left()))
        elif bounding_rect.right() + delta.x() > parent_rect.right():
            new_pos.setX(self.pos().x() + parent_rect.right() - bounding_rect.right())
        
        if bounding_rect.top() + delta.y() < parent_rect.top():
            new_pos.setY(self.pos().y() - (bounding_rect.top() - parent_rect.top()))
        elif bounding_rect.bottom() + delta.y() > parent_rect.bottom():
            new_pos.setY(self.pos().y() + parent_rect.bottom() - bounding_rect.bottom())
        
        self.setPos(new_pos)

    def init_resize(self, scene_pos: QPointF):
        self.resizing = True
        self.resize_start = scene_pos

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

    def resize_item(self, scene_pos: QPointF):
        if not self.resize_start or not self.resize_handle:
            return

        # Calculate delta in scene coordinates
        scene_delta = scene_pos - self.resize_start

        # Counter-rotate the delta to align with the item's unrotated coordinate system
        angle_rad = math.radians(-self.rotation())
        rotated_delta_x = scene_delta.x() * math.cos(angle_rad) - scene_delta.y() * math.sin(angle_rad)
        rotated_delta_y = scene_delta.x() * math.sin(angle_rad) + scene_delta.y() * math.cos(angle_rad)
        rotated_delta = QPointF(rotated_delta_x, rotated_delta_y)

        # Get the current rect and create a new one to modify
        rect = self.rect()
        new_rect = QRectF(rect)

        # Apply the delta based on which handle is being dragged
        if self.resize_handle in ['left', 'top_left', 'bottom_left']:
            new_rect.setLeft(rect.left() + rotated_delta.x())
        if self.resize_handle in ['right', 'top_right', 'bottom_right']:
            new_rect.setRight(rect.right() + rotated_delta.x())
        if self.resize_handle in ['top', 'top_left', 'top_right']:
            new_rect.setTop(rect.top() + rotated_delta.y())
        if self.resize_handle in ['bottom', 'bottom_left', 'bottom_right']:
            new_rect.setBottom(rect.bottom() + rotated_delta.y())

        # Ensure minimum size
        min_size = 20
        if new_rect.width() < min_size:
            if 'left' in self.resize_handle: new_rect.setLeft(new_rect.right() - min_size)
            else: new_rect.setRight(new_rect.left() + min_size)
        if new_rect.height() < min_size:
            if 'top' in self.resize_handle: new_rect.setTop(new_rect.bottom() - min_size)
            else: new_rect.setBottom(new_rect.top() + min_size)

        # Convert the new rectangle to scene coordinates to check bounds
        prospective_scene_rect = self.mapRectToScene(new_rect)
        
        # Get constraint bounds - use parent if available, otherwise use scene bounds
        constraint_rect = None
        if self.parentItem():
            constraint_rect = self.parentItem().sceneBoundingRect()
        elif self.scene():
            constraint_rect = self.scene().sceneRect()
        
        if constraint_rect:
            if (prospective_scene_rect.left() < constraint_rect.left() or
                prospective_scene_rect.right() > constraint_rect.right() or
                prospective_scene_rect.top() < constraint_rect.top() or
                prospective_scene_rect.bottom() > constraint_rect.bottom()):
                return  # Abort the resize operation

        # Calculate the required shift in the parent's coordinate system.
        pos_delta = self.mapToParent(new_rect.topLeft()) - self.mapToParent(rect.topLeft())
        new_pos = self.pos() + pos_delta

        self.setPos(new_pos)
        self.setRect(0, 0, new_rect.width(), new_rect.height())
        self.resize_start = scene_pos