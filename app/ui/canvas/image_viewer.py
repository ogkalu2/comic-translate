# Import third-party modules
from PySide6 import QtWidgets
from PySide6 import QtCore, QtGui

from PySide6.QtGui import QFont, QFontDatabase

from .text_item import TextBlockItem
from .rectangle import MovableRectItem

import cv2, os
import numpy as np
import math
from typing import List, Dict

class ImageViewer(QtWidgets.QGraphicsView):
    rectangle_created = QtCore.Signal(QtCore.QRectF)
    rectangle_selected = QtCore.Signal(QtCore.QRectF)
    rectangle_deleted = QtCore.Signal(QtCore.QRectF)

    def __init__(self, parent):
        super().__init__(parent)
        self._zoom = 0
        self._empty = True
        self._scene = QtWidgets.QGraphicsScene(self)
        self._photo = QtWidgets.QGraphicsPixmapItem()
        self._photo.setShapeMode(QtWidgets.QGraphicsPixmapItem.BoundingRectShape)
        self._scene.addItem(self._photo)
        self.setScene(self._scene)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.viewport().setAttribute(QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self._current_tool = None
        self._box_mode = False
        self._start_point = None
        self._current_rect = None
        self._rectangles = []
        self._text_items = []
        self._selected_rect = None
        self._panning = False
        self._pan_start_pos = None

        self._brush_color = QtGui.QColor(255, 0, 0, 100)
        self._brush_size = 25
        self._drawing_path = None
        self._drawing_items = []
        self._undo_brush_stack = []
        self._redo_brush_stack = []
        self._eraser_size = 25

        self._brush_cursor = self.create_inpaint_cursor('brush', self._brush_size)
        self._eraser_cursor = self.create_inpaint_cursor('eraser', self._eraser_size)

        self._current_path = None
        self._current_path_item = None

        # Initialize last pan position
        self._last_pan_pos = QtCore.QPoint()

    def hasPhoto(self):
        return not self._empty


    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.Gesture:
            return self.gestureEvent(event)
        return super().viewportEvent(event)

    def gestureEvent(self, event):
        pan = event.gesture(QtCore.Qt.GestureType.PanGesture)
        pinch = event.gesture(QtCore.Qt.GestureType.PinchGesture)
        
        if pan:
            return self.handlePanGesture(pan)
        elif pinch:
            return self.handlePinchGesture(pinch)
        
        return False

    def handlePanGesture(self, gesture):
        delta = gesture.delta()
        # Supported signatures:
        # PySide6.QtCore.QPoint.__add__(PySide6.QtCore.QPoint)
        new_pos = self._last_pan_pos + delta.toPoint()
        
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - (new_pos.x() - self._last_pan_pos.x())
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - (new_pos.y() - self._last_pan_pos.y())
        )
        
        self._last_pan_pos = new_pos
        return True

    def handlePinchGesture(self, gesture):
        scale_factor = gesture.scaleFactor()
        center = gesture.centerPoint()
        
        if gesture.state() == QtCore.Qt.GestureState.GestureStarted:
            self._pinch_center = self.mapToScene(center.toPoint())
        
        if scale_factor != 1:
            self.scale(scale_factor, scale_factor)
            self._zoom += (scale_factor - 1)
        
        if gesture.state() == QtCore.Qt.GestureState.GestureFinished:
            self._pinch_center = QtCore.QPointF()
        
        return True

    def wheelEvent(self, event):
        if self.hasPhoto():
            if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
                # Zoom with Ctrl + Wheel
                factor = 1.25
                if event.angleDelta().y() > 0:
                    self.scale(factor, factor)
                    self._zoom += 1
                else:
                    self.scale(1 / factor, 1 / factor)
                    self._zoom -= 1
            else:
                # Scroll without Ctrl
                super().wheelEvent(event)

    def fitInView(self):
        rect = QtCore.QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if self.hasPhoto():
                unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
                self.centerOn(rect.center())

    def set_tool(self, tool: str):
        self._current_tool = tool
        
        if tool == 'pan':
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        elif tool in ['brush', 'eraser']:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            if tool == 'brush':
                self.setCursor(self._brush_cursor)
            else:
                self.setCursor(self._eraser_cursor)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

    def delete_selected_rectangle(self):
        if self._selected_rect:
            self.rectangle_deleted.emit(self._selected_rect.rect())
            self._scene.removeItem(self._selected_rect)
            self._rectangles.remove(self._selected_rect)
            self._selected_rect = None

    def mousePressEvent(self, event):

        clicked_item = self.itemAt(event.pos())

        for item in self._scene.items():
            if isinstance(item, TextBlockItem) and item != clicked_item:
                item.handleDeselection()

        if self._current_tool == 'pan' or isinstance(clicked_item, TextBlockItem):
            super().mousePressEvent(event)

        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self._pan_start_pos = event.position()
            self.viewport().setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        
        if self._current_tool in ['brush', 'eraser'] and self.hasPhoto():
            self._drawing_path = QtGui.QPainterPath()
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._photo.contains(scene_pos):
                self._drawing_path.moveTo(scene_pos)
                self._current_path = QtGui.QPainterPath()
                self._current_path.moveTo(scene_pos)
                self._current_path_item = self._scene.addPath(self._current_path, 
                                                              QtGui.QPen(self._brush_color, self._brush_size, 
                                                                         QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, 
                                                                         QtCore.Qt.RoundJoin))

        if self._current_tool == 'box' and self.hasPhoto():
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._photo.contains(scene_pos):
                item = self.itemAt(event.position().toPoint())
                if isinstance(item, MovableRectItem):
                    self.select_rectangle(item)
                    super().mousePressEvent(event)
                else:
                    self.deselect_all()
                    self._box_mode = True
                    self._start_point = scene_pos
                    self._current_rect = MovableRectItem(QtCore.QRectF(scene_pos, scene_pos), self._photo)
                    self._current_rect.setZValue(1)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        if self._panning:
            new_pos = event.position()
            delta = new_pos - self._pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start_pos = new_pos
            event.accept()
            return
        
        if self._current_tool in ['brush', 'eraser'] and self._current_path:
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._photo.contains(scene_pos):
                self._current_path.lineTo(scene_pos)
                if self._current_tool == 'brush':
                    self._current_path_item.setPath(self._current_path)
                elif self._current_tool == 'eraser':
                    self.erase_at(scene_pos)


        if self._current_tool == 'box':
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._box_mode:
                end_point = self.constrain_point(scene_pos)
                rect = QtCore.QRectF(self._start_point, end_point).normalized()
                self._current_rect.setRect(rect)

    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.pos())
        if self._current_tool == 'pan' or isinstance(item, TextBlockItem):
            super().mouseReleaseEvent(event)

        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._panning = False
            self.viewport().setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        
        if self._current_tool in ['brush', 'eraser']:
            if self._current_path_item:
                self._drawing_items.append(self._current_path_item)
            self._current_path = None
            self._current_path_item = None
            self._undo_brush_stack.append(self._drawing_items)
            self._drawing_items = []
            self._redo_brush_stack.clear()

        if self._current_tool == 'box':
            if self._box_mode:
                self._box_mode = False
                if self._current_rect and self._current_rect.rect().width() > 0 and self._current_rect.rect().height() > 0:
                    self._rectangles.append(self._current_rect)
                    self.rectangle_created.emit(self._current_rect.rect())
                else:
                    self._scene.removeItem(self._current_rect)
                self._current_rect = None
            super().mouseReleaseEvent(event)
            
    def erase_at(self, pos: QtCore.QPointF):
        erase_path = QtGui.QPainterPath()
        erase_path.addEllipse(pos, self._eraser_size, self._eraser_size)
        
        # Increase precision of eraser path
        precise_erase_path = QtGui.QPainterPath()
        for i in range(36):
            angle = i * 10 * 3.14159 / 180
            point = QtCore.QPointF(pos.x() + self._eraser_size * math.cos(angle),
                                pos.y() + self._eraser_size * math.sin(angle))
            if i == 0:
                precise_erase_path.moveTo(point)
            else:
                precise_erase_path.lineTo(point)
        precise_erase_path.closeSubpath()

        items = self._scene.items(erase_path)
        for item in items:
            if isinstance(item, QtWidgets.QGraphicsPathItem) and item != self._photo:
                path = item.path()
                intersected_path = path.intersected(precise_erase_path)
                if not intersected_path.isEmpty():
                    new_path = QtGui.QPainterPath(path)
                    new_path = new_path.subtracted(intersected_path)
                    item.setPath(new_path)
                    if new_path.isEmpty():
                        self._scene.removeItem(item)
                        if item in self._drawing_items:
                            self._drawing_items.remove(item)

    def save_brush_strokes(self):
        brush_strokes = []
        for item in self._scene.items():
            if isinstance(item, QtWidgets.QGraphicsPathItem):
                brush_strokes.append({
                    'path': item.path(),
                    'pen': item.pen().color().name(QtGui.QColor.HexArgb),  # Save with alpha
                    'brush': item.brush().color().name(QtGui.QColor.HexArgb),  # Save fill color
                    'width': item.pen().width()
                })
        return brush_strokes

    def load_brush_strokes(self, brush_strokes: List[Dict]):
        self.clear_brush_strokes()
        # Reverse the brush_strokes list
        reversed_brush_strokes = brush_strokes[::-1]
        for stroke in reversed_brush_strokes:
            pen = QtGui.QPen()
            pen.setColor(QtGui.QColor(stroke['pen']))
            pen.setWidth(stroke['width'])
            pen.setStyle(QtCore.Qt.SolidLine)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)

            brush = QtGui.QBrush(QtGui.QColor(stroke['brush']))
            brush_color = QtGui.QColor(stroke['brush'])
            if brush_color == "#80ff0000": # generated 
                path_item = self._scene.addPath(stroke['path'], pen, brush)
            else:
                path_item = self._scene.addPath(stroke['path'], pen)
            self._drawing_items.append(path_item)
            self._undo_brush_stack.append(self._drawing_items)
            self._drawing_items = []
            #self._redo_brush_stack.clear()

    def undo_brush_stroke(self):
        if self._undo_brush_stack:
            items = self._undo_brush_stack.pop()
            for item in items:
                self._scene.removeItem(item)
            self._redo_brush_stack.append(items)

    def redo_brush_stroke(self):
        if self._redo_brush_stack:
            items = self._redo_brush_stack.pop()
            for item in items:
                self._scene.addItem(item)
            self._undo_brush_stack.append(items)

    def clear_brush_strokes(self):
        items_to_remove = []
        for item in self._scene.items():
            if isinstance(item, QtWidgets.QGraphicsPathItem) and item != self._photo:
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self._scene.removeItem(item)
        
        self._drawing_items.clear()
        self._undo_brush_stack.clear()
        self._redo_brush_stack.clear()
        
        # Update the scene to reflect the changes
        self._scene.update()

    def constrain_point(self, point: QtCore.QPointF):
        return QtCore.QPointF(
            max(0, min(point.x(), self._photo.pixmap().width())),
            max(0, min(point.y(), self._photo.pixmap().height()))
        )

    def select_rectangle(self, rect: QtWidgets.QGraphicsRectItem):
        self.deselect_all()
        rect.selected = True
        rect.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 100)))  # Transparent red
        self._selected_rect = rect

        self.rectangle_selected.emit(rect.rect())

    def deselect_all(self):
        for rect in self._rectangles:
            rect.setBrush(QtGui.QBrush(QtGui.QColor(255, 192, 203, 125)))  # Transparent pink
            rect.selected = False
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._selected_rect = None

    def get_rectangle_properties(self):
        return [
            {
                'x': rect.rect().x(),
                'y': rect.rect().y(),
                'width': rect.rect().width(),
                'height': rect.rect().height(),
                'selected': rect == self._selected_rect
            }
            for rect in self._rectangles
        ]

    def get_rectangle_coordinates(self):
        return [
            (
                int(rect.rect().x()),
                int(rect.rect().y()),
                int(rect.rect().x() + rect.rect().width()),
                int(rect.rect().y() + rect.rect().height())
            )
            for rect in self._rectangles
        ]


    def get_cv2_image(self, paint_all=False):
        """Get the currently loaded image as a cv2 image, including text blocks and all scene items."""
        if self._photo.pixmap() is None:
            return None

        if paint_all:
            # Create a high-resolution QImage
            scale_factor = 2  # Increase this for higher resolution
            pixmap = self._photo.pixmap()
            original_size = pixmap.size()
            scaled_size = original_size * scale_factor
            
            qimage = QtGui.QImage(scaled_size, QtGui.QImage.Format_ARGB32)
            qimage.fill(QtCore.Qt.transparent)

            # Create a QPainter with antialiasing
            painter = QtGui.QPainter(qimage)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

            # Save the current view's transformation
            original_transform = self._scene.views()[0].transform()

            # Reset the transformation to identity (no zoom, no pan)
            self._scene.views()[0].resetTransform()

            # Set the sceneRect to cover the entire image
            self._scene.setSceneRect(0, 0, original_size.width(), original_size.height())

            # Render the scene
            self._scene.render(painter)
            painter.end()

            # Scale down the image to the original size
            qimage = qimage.scaled(original_size, 
                                QtCore.Qt.AspectRatioMode.KeepAspectRatio, 
                                QtCore.Qt.TransformationMode.SmoothTransformation)

            # Restore the original transformation
            self._scene.views()[0].setTransform(original_transform)
        else:
            qimage = self._photo.pixmap().toImage()

        # Convert QImage to cv2 image
        qimage = qimage.convertToFormat(QtGui.QImage.Format.Format_RGB888)
        width = qimage.width()
        height = qimage.height()
        bytes_per_line = qimage.bytesPerLine()

        byte_count = qimage.sizeInBytes()
        expected_size = height * bytes_per_line  # bytes per line can include padding

        if byte_count != expected_size:
            print(f"QImage sizeInBytes: {byte_count}, Expected size: {expected_size}")
            print(f"Image dimensions: ({width}, {height}), Format: {qimage.format()}")
            raise ValueError(f"Byte count mismatch: got {byte_count} but expected {expected_size}")

        ptr = qimage.bits()

        # Convert memoryview to a numpy array considering the complete data with padding
        arr = np.array(ptr).reshape((height, bytes_per_line))
        # Exclude the padding bytes, keeping only the relevant image data
        arr = arr[:, :width * 3]
        # Reshape to the correct dimensions without the padding bytes
        arr = arr.reshape((height, width, 3))

        return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    
    def display_cv2_image(self, cv2_img: np.ndarray):
        height, width, channel = cv2_img.shape
        bytes_per_line = 3 * width
        qimage = QtGui.QImage(cv2_img.data, width, height, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qimage)
        self.setPhoto(pixmap)

    def clear_scene(self):
        self._scene.clear()
        self._photo = QtWidgets.QGraphicsPixmapItem()
        self._photo.setShapeMode(QtWidgets.QGraphicsPixmapItem.BoundingRectShape)
        self._scene.addItem(self._photo)
        self._rectangles = []
        self._text_items = []
        self._selected_rect = None

    def clear_rectangles(self):
        for rect in self._rectangles:
            self._scene.removeItem(rect)
        self._rectangles.clear()
        self._selected_rect = None

    def clear_text_items(self, delete=True):
        for item in self._text_items:
            self._scene.removeItem(item)
        if delete:
            self._text_items.clear()

    def setPhoto(self, pixmap: QtGui.QPixmap =None):
        self.clear_scene()
        if pixmap and not pixmap.isNull():
            self._empty = False
            self._photo.setPixmap(pixmap)
            self.fitInView()
        else:
            self._empty = True
        self._zoom = 0

    def has_drawn_elements(self):
        for item in self._scene.items():
            if isinstance(item, QtWidgets.QGraphicsPathItem):
                if item != self._photo:
                    return True
        return False

    def generate_mask_from_strokes(self):
        if not self.hasPhoto():
            return None

        # Get the size of the image
        image_rect = self._photo.boundingRect()
        width = int(image_rect.width())
        height = int(image_rect.height())

        # Create two blank masks
        human_mask = np.zeros((height, width), dtype=np.uint8)
        generated_mask = np.zeros((height, width), dtype=np.uint8)

        # Create two QImages to draw paths separately
        human_qimage = QtGui.QImage(width, height, QtGui.QImage.Format_Grayscale8)
        generated_qimage = QtGui.QImage(width, height, QtGui.QImage.Format_Grayscale8)
        human_qimage.fill(QtGui.QColor(0, 0, 0))
        generated_qimage.fill(QtGui.QColor(0, 0, 0))

        # Create QPainters for both QImages
        human_painter = QtGui.QPainter(human_qimage)
        generated_painter = QtGui.QPainter(generated_qimage)
        
        hum_pen = QtGui.QPen(QtGui.QColor(255, 255, 255), self._brush_size)
        gen_pen = QtGui.QPen(QtGui.QColor(255, 255, 255), 2, QtCore.Qt.SolidLine)

        human_painter.setPen(hum_pen)
        generated_painter.setPen(gen_pen)
        
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        human_painter.setBrush(brush)
        generated_painter.setBrush(brush)

        # Iterate through all items in the scene
        for item in self._scene.items():
            if isinstance(item, QtWidgets.QGraphicsPathItem) and item != self._photo:
                brush_color = QtGui.QColor(item.brush().color().name(QtGui.QColor.HexArgb))
                if brush_color == "#80ff0000":  # generated stroke
                    generated_painter.drawPath(item.path())
                else:  # human-drawn stroke
                    human_painter.drawPath(item.path())

        # End painting
        human_painter.end()
        generated_painter.end()

        # Convert the QImages to numpy arrays, accounting for padding
        bytes_per_line = human_qimage.bytesPerLine()
        human_ptr = human_qimage.constBits()
        generated_ptr = generated_qimage.constBits()
        human_arr = np.array(human_ptr).reshape(height, bytes_per_line)
        generated_arr = np.array(generated_ptr).reshape(height, bytes_per_line)
        
        # Exclude the padding bytes, keeping only the relevant image data
        human_mask = human_arr[:, :width]
        generated_mask = generated_arr[:, :width]

        kernel = np.ones((5,5), np.uint8)
        human_mask = cv2.dilate(human_mask, kernel, iterations=2)
        generated_mask = cv2.dilate(generated_mask, kernel, iterations=3)

        # Combine the masks
        final_mask = cv2.bitwise_or(human_mask, generated_mask)

        return final_mask

    def get_mask_for_inpainting(self):
        # Generate the mask
        mask = self.generate_mask_from_strokes()

        if mask is None:
            return None

        # Get the current image
        cv2_image = self.get_cv2_image()

        if cv2_image is None:
            return None

        # Ensure the mask and image have the same dimensions
        mask = cv2.resize(mask, (cv2_image.shape[1], cv2_image.shape[0]))

        return mask

    def draw_segmentation_lines(self, bboxes, layers: int = 1, scale_factor: float = 1.0):
        if not self.hasPhoto():
            print("No photo loaded.")
            return

        if not bboxes:
            return

        # Calculate the centroid of all points
        all_points = np.array(bboxes).reshape(-1, 2)
        centroid = np.mean(all_points, axis=0)

        # Scale the line segments towards the centroid
        scaled_segments = []
        for x1, y1, x2, y2 in bboxes:
            scaled_p1 = (np.array([x1, y1]) - centroid) * scale_factor + centroid
            scaled_p2 = (np.array([x2, y2]) - centroid) * scale_factor + centroid
            scaled_segments.append((scaled_p1[0], scaled_p1[1], scaled_p2[0], scaled_p2[1]))

        # Create rectangles for each line segment
        fill_color = QtGui.QColor(255, 0, 0, 128)  # Semi-transparent red
        outline_color = QtGui.QColor(255, 0, 0)  # Solid red for the outline

        for _ in range(layers):
            for x1, y1, x2, y2 in scaled_segments:
                path = QtGui.QPainterPath()
                path.addRect(QtCore.QRectF(x1, y1, x2 - x1, y2 - y1))
                
                path_item = QtWidgets.QGraphicsPathItem(path)
                path_item.setPen(QtGui.QPen(outline_color, 2, QtCore.Qt.SolidLine))
                path_item.setBrush(QtGui.QBrush(fill_color))
                self._scene.addItem(path_item)
                self._drawing_items.append(path_item)  # Add to drawing items for saving

        # Ensure the rectangles are visible
        self._scene.update()

    def load_state(self, state: Dict):
        self.setTransform(QtGui.QTransform(*state['transform']))
        self.centerOn(QtCore.QPointF(*state['center']))
        self.setSceneRect(QtCore.QRectF(*state['scene_rect']))
        
        for rect_data in state['rectangles']:
            rect_item = MovableRectItem(QtCore.QRectF(*rect_data), self._photo)
            self._rectangles.append(rect_item)
        
        # Recreate text block items
        for text_block in state.get('text_items_state', []):
            text_item = TextBlockItem(
                text=text_block['text'],
                parent_item= self._photo,
                font_family=text_block['font_family'],
                font_size=text_block['font_size'],
                render_color=text_block['text_color'],
                alignment=text_block['alignment'],
                line_spacing=text_block['line_spacing'],
                outline_color=text_block['outline_color'],
                outline_width=text_block['outline_width'],
                bold=text_block['bold'],
                italic=text_block['italic'],
                underline=text_block['underline'],
                text_block=text_block['block']
            )
            text_item.setPos(QtCore.QPointF(*text_block['position']))
            text_item.setRotation(text_block['rotation'])
            text_item.setScale(text_block['scale'])

            self._scene.addItem(text_item)
            self._text_items.append(text_item)  

    def save_state(self):
        transform = self.transform()
        center = self.mapToScene(self.viewport().rect().center())

        text_items_state = []
        for item in self._text_items:
            text_items_state.append({
                'text': item.toHtml(),
                'font_family': item.font_family,
                'font_size': item.font_size,
                'text_color': item.text_color,
                'alignment': item.alignment,
                'line_spacing': item.line_spacing,
                'outline_color': item.outline_color,
                'outline_width': item.outline_width,
                'bold': item.bold,
                'italic': item.italic,
                'underline': item.underline,
                'position': (item.pos().x(), item.pos().y()),
                'rotation': item.rotation(),
                'scale': item.scale(),
                'block': item.text_block
            })

        return {
            'rectangles': [rect.rect().getRect() for rect in self._rectangles],
            'transform': (
                transform.m11(), transform.m12(), transform.m13(),
                transform.m21(), transform.m22(), transform.m23(),
                transform.m31(), transform.m32(), transform.m33()
            ),
            'center': (center.x(), center.y()),
            'scene_rect': (self.sceneRect().x(), self.sceneRect().y(), 
                        self.sceneRect().width(), self.sceneRect().height()),
            'text_items_state': text_items_state
        }

    def create_inpaint_cursor(self, cursor_type, size):
        from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QCursor
        from PySide6.QtCore import Qt

        # Ensure size is at least 1 pixel
        size = max(1, size)
        
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)

        if cursor_type == "brush":
            painter.setBrush(QBrush(QColor(255, 0, 0, 127)))  # Red color with some transparency
            painter.setPen(Qt.PenStyle.NoPen)
        elif cursor_type == "eraser":
            painter.setBrush(QBrush(QColor(0, 0, 0, 0)))  # Fully transparent
            painter.setPen(QColor(0, 0, 0, 127))  # Outline with some transparency
        else:
            painter.setBrush(QBrush(QColor(0, 0, 0, 127)))  # Default to some color if unknown type
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawEllipse(0, 0, (size - 1), (size - 1))
        painter.end()

        return QCursor(pixmap, size // 2, size // 2)
    
    def set_brush_size(self, size):
        self._brush_size = size
        self._brush_cursor = self.create_inpaint_cursor("brush", size)
        if self._current_tool == "brush":
            self.setCursor(self._brush_cursor)

    def set_eraser_size(self, size):
        self._eraser_size = size
        self._eraser_cursor = self.create_inpaint_cursor("eraser", size)
        if self._current_tool == "eraser":
            self.setCursor(self._eraser_cursor)
