from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import QEvent, QLineF, Qt, QPointF
from PySide6.QtGui import QTransform, QEventPoint
from PySide6.QtWidgets import QGraphicsPixmapItem

from .text_item import TextBlockItem, TextBlockState
from .rectangle import MoveableRectItem


class EventHandler:
    """Handles all Qt events for the ImageViewer using composition."""
    
    def __init__(self, viewer):
        self.viewer = viewer
    
    # Main Event Handlers

    def handle_mouse_press(self, event: QtGui.QMouseEvent):
        scene_pos = self.viewer.mapToScene(event.position().toPoint())
        clicked_item = self.viewer.itemAt(event.pos())
        
        # Delegate page change detection to the appropriate manager
        if self.viewer.webtoon_mode:
            self.viewer.webtoon_manager.update_page_on_click(scene_pos)
        
        if event.button() == Qt.LeftButton:
            if self._press_handle_rotation(event, scene_pos): 
                return
            self._press_handle_deselection(clicked_item)

        if event.button() == Qt.MiddleButton:
            self._press_handle_pan(event)
            return

        if self.viewer.current_tool in ['brush', 'eraser'] and self.viewer.hasPhoto():
            if self._is_on_image(scene_pos):
                self.viewer.drawing_manager.start_stroke(scene_pos)

        if self.viewer.current_tool == 'box' and self.viewer.hasPhoto():
            if self._is_on_image(scene_pos):
                if isinstance(clicked_item, MoveableRectItem):
                    self.viewer.select_rectangle(clicked_item)
                    QtWidgets.QGraphicsView.mousePressEvent(self.viewer, event)
                else:
                    self._press_handle_new_box(scene_pos)

        scroll = self.viewer.dragMode() == QtWidgets.QGraphicsView.DragMode.ScrollHandDrag
        if self.viewer.current_tool == 'pan' or isinstance(clicked_item, (TextBlockItem, MoveableRectItem)) or scroll:
            QtWidgets.QGraphicsView.mousePressEvent(self.viewer, event)
    
    def handle_mouse_move(self, event: QtGui.QMouseEvent):
        QtWidgets.QGraphicsView.mouseMoveEvent(self.viewer, event)
        scene_pos = self.viewer.mapToScene(event.position().toPoint())

        if self._move_handle_item_interaction(scene_pos): 
            return
        if self.viewer.panning: 
            self._move_handle_pan(event)
            return
        
        if self.viewer.current_tool in ['brush', 'eraser'] and self.viewer.drawing_manager.current_path:
            if self._is_on_image(scene_pos):
                self.viewer.drawing_manager.continue_stroke(scene_pos)
        
        if self.viewer.current_tool == 'box':
            self._move_handle_box_resize(scene_pos)

    def handle_mouse_release(self, event: QtGui.QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._release_handle_item_interaction()

        item = self.viewer.itemAt(event.pos())
        scroll = self.viewer.dragMode() == QtWidgets.QGraphicsView.DragMode.ScrollHandDrag
        if isinstance(item, (MoveableRectItem, TextBlockItem)) or self.viewer.current_tool == 'pan' or scroll:
            QtWidgets.QGraphicsView.mouseReleaseEvent(self.viewer, event)

        if event.button() == Qt.MiddleButton:
            self._release_handle_pan()
            return
        
        if self.viewer.current_tool in ['brush', 'eraser']:
            self.viewer.drawing_manager.end_stroke()
            
        if self.viewer.current_tool == 'box':
            self._release_handle_box_creation()
            QtWidgets.QGraphicsView.mouseReleaseEvent(self.viewer, event)

    def handle_wheel(self, event: QtGui.QWheelEvent):
        if not self.viewer.hasPhoto(): 
            return
        
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
            self.viewer.scale(factor, factor)
            self.viewer.zoom += 1 if factor > 1 else -1
        else:
            # Call QGraphicsView's wheelEvent directly
            QtWidgets.QGraphicsView.wheelEvent(self.viewer, event)
            
            # Handle lazy webtoon manager scroll events
            if self.viewer.webtoon_mode:
                self.viewer.webtoon_manager.on_scroll()

    def handle_viewport_event(self, event: QtCore.QEvent):
        if event.type() in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            touch_points = event.points()
            if len(touch_points) == 2:
                touchPoint0, touchPoint1 = touch_points[0], touch_points[1]
                current_scale_factor = (
                    QLineF(touchPoint0.pos(), touchPoint1.pos()).length() /
                    QLineF(touchPoint0.startPos(), touchPoint1.startPos()).length()
                )
                if any(tp.state() == QEventPoint.State.Released for tp in touch_points):
                    self.viewer.total_scale_factor *= current_scale_factor
                    current_scale_factor = 1.0
                scale_factor = self.viewer.total_scale_factor * current_scale_factor
                self.viewer.setTransform(QTransform.fromScale(scale_factor, scale_factor))
                return True
        if event.type() == QEvent.Type.Gesture:
            return self._handle_gesture_event(event)
        return QtWidgets.QGraphicsView.viewportEvent(self.viewer, event)

    def _handle_gesture_event(self, event):
        if pan := event.gesture(Qt.GestureType.PanGesture): 
            return self._handle_pan_gesture(pan)
        if pinch := event.gesture(Qt.GestureType.PinchGesture): 
            return self._handle_pinch_gesture(pinch)
        return False

    # Event Handler Helpers 

    def _is_on_image(self, scene_pos: QPointF) -> bool:
        if self.viewer.webtoon_mode:
            return any(item.contains(item.mapFromScene(scene_pos)) for item in self.viewer.webtoon_manager.image_items.values())
        return self.viewer.photo.contains(scene_pos)

    def _press_handle_rotation(self, event, scene_pos) -> bool:
        blk_item, rect_item = self.viewer.sel_rot_item()
        sel_item = blk_item or rect_item
        if sel_item and self.viewer.interaction_manager._in_rotate_ring(sel_item, scene_pos):
            angle = sel_item.rotation()
            inner_rect = sel_item.boundingRect()
            outer_rect = inner_rect.adjusted(-self.viewer.interaction_manager.rotate_margin_max, 
                                           -self.viewer.interaction_manager.rotate_margin_max, 
                                           self.viewer.interaction_manager.rotate_margin_max, 
                                           self.viewer.interaction_manager.rotate_margin_max)
            sel_item.rot_handle = self.viewer.interaction_manager.get_rotate_handle(outer_rect, sel_item.mapFromScene(scene_pos), angle)
            if sel_item.rot_handle:
                sel_item.init_rotation(scene_pos)
                event.accept()
                return True
        return False

    def _press_handle_deselection(self, clicked_item):
        if clicked_item is None or isinstance(clicked_item, QGraphicsPixmapItem):
            self.viewer.clear_text_edits.emit()
            self.viewer.deselect_all()
        else:
            for item in self.viewer._scene.items():
                if isinstance(item, (TextBlockItem, MoveableRectItem)) and item != clicked_item:
                    if isinstance(item, TextBlockItem): 
                        item.handleDeselection()
                    else: 
                        self.viewer.deselect_rect(item)

    def _press_handle_pan(self, event):
        self.viewer.panning = True
        self.viewer.pan_start_pos = event.position()
        self.viewer.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def _press_handle_new_box(self, scene_pos):
        self.viewer.start_point = scene_pos
        self.viewer.current_rect = self.viewer.create_rect_item(QtCore.QRectF(0, 0, 0, 0))
        self.viewer.current_rect.setPos(scene_pos)

    def _move_handle_item_interaction(self, scene_pos) -> bool:
        blk_item, rect_item = self.viewer.sel_rot_item()
        sel_item = blk_item or rect_item
        if not sel_item: 
            return False

        local_pos = sel_item.mapFromScene(scene_pos)
        inner_rect = sel_item.boundingRect()
        
        if sel_item.get_handle_at_position(local_pos, inner_rect):
            cursor_shape = sel_item.get_cursor_for_position(local_pos)
            self.viewer.viewport().setCursor(QtGui.QCursor(cursor_shape))
            return True
        
        if sel_item.rotating and sel_item.center_scene_pos:
            sel_item.rotate_item(scene_pos)
            return True
        
        if self.viewer.interaction_manager._in_rotate_ring(sel_item, scene_pos):
            outer_rect = inner_rect.adjusted(-self.viewer.interaction_manager.rotate_margin_max, 
                                           -self.viewer.interaction_manager.rotate_margin_max, 
                                           self.viewer.interaction_manager.rotate_margin_max, 
                                           self.viewer.interaction_manager.rotate_margin_max)
            cursor = self.viewer.interaction_manager.get_rotation_cursor(outer_rect, local_pos, sel_item.rotation())
            self.viewer.viewport().setCursor(cursor)
            return True

        self.viewer.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        return False

    def _move_handle_pan(self, event):
        delta = event.position() - self.viewer.pan_start_pos
        self.viewer.horizontalScrollBar().setValue(self.viewer.horizontalScrollBar().value() - delta.x())
        self.viewer.verticalScrollBar().setValue(self.viewer.verticalScrollBar().value() - delta.y())
        self.viewer.pan_start_pos = event.position()
        event.accept()

    def _move_handle_box_resize(self, scene_pos):
        if not self.viewer.start_point or not self.viewer.current_rect:
            return
        end_point = self.viewer.constrain_point(scene_pos)
        width = end_point.x() - self.viewer.start_point.x()
        height = end_point.y() - self.viewer.start_point.y()
        pos_x, pos_y = self.viewer.start_point.x(), self.viewer.start_point.y()
        if width < 0:
            pos_x = end_point.x()
            width = abs(width)
        if height < 0:
            pos_y = end_point.y() 
            height = abs(height)
        
        self.viewer.current_rect.setPos(QPointF(pos_x, pos_y))
        self.viewer.current_rect.setRect(QtCore.QRectF(0, 0, width, height))
        
    def _release_handle_item_interaction(self):
        blk_item, rect_item = self.viewer.sel_rot_item()
        sel_item = blk_item or rect_item
        if sel_item:
            sel_item.rotating = False
            sel_item.center_scene_pos = None
            sel_item.rot_handle = None
            if isinstance(sel_item, TextBlockItem):
                new_state = TextBlockState.from_item(sel_item)
                sel_item.change_undo.emit(sel_item.old_state, new_state)
        self.viewer.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def _release_handle_pan(self):
        self.viewer.panning = False
        self.viewer.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def _release_handle_box_creation(self):
        if self.viewer.current_rect and self.viewer.current_rect.rect().width() > 0 and self.viewer.current_rect.rect().height() > 0:
            self.viewer.rectangles.append(self.viewer.current_rect)
            self.viewer.rectangle_created.emit(self.viewer.current_rect)
        elif self.viewer.current_rect:
            self.viewer._scene.removeItem(self.viewer.current_rect)
        self.viewer.current_rect = None

    def _handle_pan_gesture(self, gesture):
        delta = gesture.delta().toPoint()
        new_pos = self.viewer.last_pan_pos + delta
        self.viewer.horizontalScrollBar().setValue(self.viewer.horizontalScrollBar().value() - (new_pos.x() - self.viewer.last_pan_pos.x()))
        self.viewer.verticalScrollBar().setValue(self.viewer.verticalScrollBar().value() - (new_pos.y() - self.viewer.last_pan_pos.y()))
        self.viewer.last_pan_pos = new_pos
        return True

    def _handle_pinch_gesture(self, gesture):
        scale = gesture.scaleFactor()
        if gesture.state() == Qt.GestureState.GestureStarted:
            self.viewer._pinch_center = self.viewer.mapToScene(gesture.centerPoint().toPoint())
        if scale != 1.0:
            self.viewer.scale(scale, scale)
            self.viewer.zoom += (scale - 1)
        if gesture.state() == Qt.GestureState.GestureFinished:
            self.viewer._pinch_center = QPointF()
        return True
        
    def _enable_page_detection(self):
        self.viewer._programmatic_scroll = False

    def _enable_page_detection_after_delay(self):
        self.viewer._programmatic_scroll = True
        if not hasattr(self.viewer, '_programmatic_scroll_timer'):
            self.viewer._programmatic_scroll_timer = QtCore.QTimer()
            self.viewer._programmatic_scroll_timer.setSingleShot(True)
            self.viewer._programmatic_scroll_timer.timeout.connect(self._enable_page_detection)
        self.viewer._programmatic_scroll_timer.start(200)
