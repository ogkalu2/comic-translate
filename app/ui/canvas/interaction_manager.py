import math
from typing import Optional

from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, QRectF, Qt

from .text_item import TextBlockItem
from .rectangle import MoveableRectItem
from ..commands.box import ClearRectsCommand


class InteractionManager:
    """Manages interactions with scene items like selection, rotation, and resizing using composition."""

    def __init__(self, viewer):
        self.viewer = viewer
        # Rotation margins
        self.rotate_margin_min = 20
        self.rotate_margin_max = 50
        # Resize margins
        self.resize_margin_min = 0
        self.resize_margin_max = 20

    def set_rotate_ring(self, inner: int, outer: int):
        if inner < 0 or outer <= inner:
            raise ValueError("outer must be > inner ≥ 0")
        self.rotate_margin_min = inner
        self.rotate_margin_max = outer

    def set_resize_ring(self, inner: int, outer: int):
        if inner < 0 or outer <= inner:
            raise ValueError("outer must be > inner ≥ 0")
        self.resize_margin_min = inner
        self.resize_margin_max = outer
    
    def sel_rot_item(self):
        blk_item = next(
            (item for item in self.viewer._scene.items() if (
                isinstance(item, TextBlockItem) and item.selected)
            ), None )

        rect_item = next(
            (item for item in self.viewer._scene.items() if (
                isinstance(item, MoveableRectItem) and item.selected)
            ),  None )
        return blk_item, rect_item

    def _in_rotate_ring(self, item: Optional[MoveableRectItem|TextBlockItem], scene_pos) -> bool:
        """Checks if a scene position is within the item's rotation ring."""
        if not item: return False
        local = item.mapFromScene(scene_pos)
        r = item.boundingRect()
        dx = max(r.left() - local.x(), 0, local.x() - r.right())
        dy = max(r.top() - local.y(), 0, local.y() - r.bottom())
        dist = math.hypot(dx, dy)
        return self.rotate_margin_min < dist < self.rotate_margin_max

    def _in_resize_area(self, item: Optional[MoveableRectItem|TextBlockItem], scene_pos) -> bool:
        """Checks if a scene position is within the item's resize area."""
        if not item: return False
        local = item.mapFromScene(scene_pos)
        r = item.boundingRect()
        dx = max(r.left() - local.x(), 0, local.x() - r.right())
        dy = max(r.top() - local.y(), 0, local.y() - r.bottom())
        dist = math.hypot(dx, dy)
        return self.resize_margin_min < dist < self.resize_margin_max

    # --- START: NEW METHOD FROM YOUR CODE ---
    def rotate_cursor(self, cursor, steps):
        cursor_map = {
            Qt.SizeVerCursor: [Qt.SizeVerCursor, Qt.SizeBDiagCursor, Qt.SizeHorCursor, Qt.SizeFDiagCursor] * 2,
            Qt.SizeHorCursor: [Qt.SizeHorCursor, Qt.SizeFDiagCursor, Qt.SizeVerCursor, Qt.SizeBDiagCursor] * 2,
            Qt.SizeFDiagCursor: [Qt.SizeFDiagCursor, Qt.SizeVerCursor, Qt.SizeBDiagCursor, Qt.SizeHorCursor] * 2,
            Qt.SizeBDiagCursor: [Qt.SizeBDiagCursor, Qt.SizeHorCursor, Qt.SizeFDiagCursor, Qt.SizeVerCursor] * 2
        }
        return cursor_map.get(cursor, [cursor] * 8)[steps]
    # --- END: NEW METHOD FROM YOUR CODE ---

    # --- START: REPLACED get_resize_cursor WITH YOUR get_cursor_for_position LOGIC ---
    def get_resize_cursor(self, item: MoveableRectItem | TextBlockItem, pos: QPointF) -> QtGui.QCursor:
        """Gets the appropriate resize cursor for a given position."""
        rect = item.boundingRect()
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
            rotation = item.rotation() % 360
            steps = 0
            if 22.5 <= rotation < 67.5:
                steps = 1
            elif 67.5 <= rotation < 112.5:
                steps = 2
            elif 112.5 <= rotation < 157.5:
                steps = 3
            elif 157.5 <= rotation < 202.5:
                steps = 4
            elif 202.5 <= rotation < 247.5:
                steps = 5
            elif 247.5 <= rotation < 292.5:
                steps = 6
            elif 292.5 <= rotation < 337.5:
                steps = 7
            
            rotated_shape = self.rotate_cursor(cursor, steps)
            return QtGui.QCursor(rotated_shape)
        
        return QtGui.QCursor(QtCore.Qt.ArrowCursor)
    # --- END: REPLACED get_resize_cursor ---

    # --- START: REPLACED get_resize_handle WITH YOUR get_handle_at_position LOGIC ---
    def get_resize_handle(self, item: MoveableRectItem | TextBlockItem, pos: QPointF) -> str | None:
        """Determines which resize handle is at a position (pos is in item's local coordinates)."""
        return self.get_handle_at_position(pos, item.boundingRect())

    def get_handle_at_position(self, pos, rect):
        handle_size = self.resize_margin_max # Use manager's property
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

        # Check corners first, as they overlap with sides
        corner_handles = ['top_left', 'top_right', 'bottom_left', 'bottom_right']
        for handle in corner_handles:
            if handles[handle].contains(pos):
                return handle
        
        side_handles = ['top', 'bottom', 'left', 'right']
        for handle in side_handles:
             if handles[handle].contains(pos):
                return handle

        return None
    # --- END: REPLACED get_resize_handle ---

    def get_rotation_cursor(self, outer_rect, pos, angle):
        """Gets the appropriate rotation cursor for a given position."""
        inner_rect = outer_rect.adjusted(self.rotate_margin_max, self.rotate_margin_max,
                                         -self.rotate_margin_max, -self.rotate_margin_max)
        handle = self._resolve_rotate_handle(inner_rect, outer_rect, pos, angle)
        return self.viewer.rotate_cursors.get_cursor(handle) if handle else QtGui.QCursor(QtCore.Qt.ArrowCursor)

    def get_rotate_handle(self, outer_rect, pos, angle):
        """Determines which rotation handle (e.g., 'top_left') is at a position."""
        inner_rect = outer_rect.adjusted(self.rotate_margin_max, self.rotate_margin_max,
                                         -self.rotate_margin_max, -self.rotate_margin_max)
        return self._resolve_rotate_handle(inner_rect, outer_rect, pos, angle)

    def _resolve_rotate_handle(self, inner: QRectF, outer: QRectF, pos: QPointF, angle: float) -> str | None:
        if not outer.contains(pos) or inner.contains(pos):
            return None
        
        centre = inner.center()
        rot = QtGui.QTransform().translate(centre.x(), centre.y()).rotate(-angle).translate(-centre.x(), -centre.y())
        p = rot.map(pos)

        if p.y() < inner.top():
            return 'top_left' if p.x() < inner.left() else 'top_right' if p.x() > inner.right() else 'top'
        elif p.y() > inner.bottom():
            return 'bottom_left' if p.x() < inner.left() else 'bottom_right' if p.x() > inner.right() else 'bottom'
        else:
            return 'left' if p.x() < inner.left() else 'right'

    def select_rectangle(self, rect: MoveableRectItem):
        self.deselect_all()
        if rect:
            rect.selected = True
            rect.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 100)))
            self.viewer.selected_rect = rect
            self.viewer.rectangle_selected.emit(rect.mapRectToScene(rect.rect()))

    def deselect_rect(self, rect: MoveableRectItem):
        rect.setBrush(QtGui.QBrush(QtGui.QColor(255, 192, 203, 125)))
        rect.selected = False

    def deselect_all(self):
        for rect in self.viewer.rectangles:
            self.deselect_rect(rect)
        for txt_item in self.viewer.text_items:
            txt_item.handleDeselection()
        self.viewer.selected_rect = None
        self.viewer.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        
    def clear_rectangles(self, page_switch=False):
        if page_switch:
            for rect in self.viewer.rectangles:
                self.viewer._scene.removeItem(rect)
            self.viewer.rectangles.clear()
            self.viewer.selected_rect = None
        else:
            command = ClearRectsCommand(self.viewer)
            self.viewer.command_emitted.emit(command)
                
    def clear_text_items(self, delete=True):
        # Clear from scene
        for item in self.viewer.text_items:
            self.viewer._scene.removeItem(item)
        if delete:
            self.viewer.text_items.clear()
            
    def clear_rectangles_in_visible_area(self):
        """Clear rectangles that are within the currently visible viewport area."""
        if not self.viewer.webtoon_mode:
            # Not in lazy webtoon mode, fall back to regular clear
            self.clear_rectangles()
            return
            
        # Get the visible area mappings to determine Y bounds
        _, page_mappings = self.viewer.webtoon_manager.get_visible_area_image()
        if not page_mappings:
            return
            
        # Calculate the scene Y range of the visible area
        visible_y_min = min(mapping['scene_y_start'] for mapping in page_mappings)
        visible_y_max = max(mapping['scene_y_end'] for mapping in page_mappings)
        
        # Find rectangles that overlap with the visible area
        to_remove = []
        for rect in self.viewer.rectangles:
            rect_y = rect.pos().y()
            rect_h = rect.rect().height()
            rect_bottom_y = rect_y + rect_h
            
            # Check if rectangle overlaps with visible area
            if not (rect_bottom_y <= visible_y_min or rect_y >= visible_y_max):
                to_remove.append(rect)
        
        # Remove the overlapping rectangles
        for rect in to_remove:
            self.viewer._scene.removeItem(rect)
            self.viewer.rectangles.remove(rect)
            if self.viewer.selected_rect == rect:
                self.viewer.selected_rect = None
