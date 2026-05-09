import numpy as np
from typing import List, Dict

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QGraphicsPathItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QBrush, QPen, QPainterPath, QCursor, QPixmap, QImage, QPainter

from app.ui.commands.brush import BrushStrokeCommand, ClearBrushStrokesCommand, \
                            SegmentBoxesCommand, EraseUndoCommand
from app.ui.commands.base import PathCommandBase as pcb
import imkit as imk


class DrawingManager:
    """Manages all drawing-related tools and state."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._scene = viewer._scene

        self.brush_color = QColor(255, 0, 0, 100)
        self.brush_size = 25
        self.eraser_size = 25
        
        self.brush_cursor = self.create_inpaint_cursor('brush', self.brush_size)
        self.eraser_cursor = self.create_inpaint_cursor('eraser', self.eraser_size)

        self.current_path = None
        self.current_path_item = None
        
        self.before_erase_state = []
        self.after_erase_state = []

    def start_stroke(self, scene_pos: QPointF):
        """Starts a new drawing or erasing stroke."""
        self.viewer.drawing_path = QPainterPath() # drawing_path is on viewer in original
        self.viewer.drawing_path.moveTo(scene_pos)
        
        self.current_path = QPainterPath()
        self.current_path.moveTo(scene_pos)

        if self.viewer.current_tool == 'brush':
            pen = QPen(self.brush_color, self.brush_size, 
                       Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self.current_path_item = self._scene.addPath(self.current_path, pen)
            self.current_path_item.setZValue(0.8)  
        
        elif self.viewer.current_tool == 'eraser':
            # Capture the current state before starting erase operation
            self.before_erase_state = []
            try:
                photo_item = getattr(self.viewer, 'photo', None)
                for item in self._scene.items():
                    if (isinstance(item, QGraphicsPathItem) and 
                        item != photo_item and
                        hasattr(item, 'path')):  # Ensure item has path method
                        props = pcb.save_path_properties(item)
                        if props:  # Only add valid properties
                            self.before_erase_state.append(props)
            except Exception as e:
                print(f"Warning: Error capturing before_erase_state: {e}")
                import traceback
                traceback.print_exc()
                self.before_erase_state = []

    def continue_stroke(self, scene_pos: QPointF):
        """Continues an existing drawing or erasing stroke."""
        if not self.current_path:
            return

        self.current_path.lineTo(scene_pos)
        if self.viewer.current_tool == 'brush' and self.current_path_item:
            self.current_path_item.setPath(self.current_path)
        elif self.viewer.current_tool == 'eraser':
            self.erase_at(scene_pos)

    def end_stroke(self):
        """Finalizes the current stroke and creates an undo command."""
        if self.current_path_item:
            if self.viewer.current_tool == 'brush':
                command = BrushStrokeCommand(self.viewer, self.current_path_item)
                self.viewer.command_emitted.emit(command)

        if self.viewer.current_tool == 'eraser':
            # Capture the current state after erase operation
            self.after_erase_state = []
            try:
                photo_item = getattr(self.viewer, 'photo', None)
                for item in self._scene.items():
                    if (isinstance(item, QGraphicsPathItem) and 
                        item != photo_item and
                        hasattr(item, 'path')):  # Ensure item has path method
                        props = pcb.save_path_properties(item)
                        if props:  # Only add valid properties
                            self.after_erase_state.append(props)
            except Exception as e:
                print(f"Warning: Error capturing after_erase_state: {e}")
                import traceback
                traceback.print_exc()
                self.after_erase_state = []
            
            # Only create undo command if we have valid before/after states
            if hasattr(self, 'before_erase_state'):
                # Create copies of the lists before passing them to avoid clearing issues
                before_copy = list(self.before_erase_state)
                after_copy = list(self.after_erase_state)
                command = EraseUndoCommand(self.viewer, before_copy, after_copy)
                self.viewer.command_emitted.emit(command)
                self.before_erase_state.clear()
                self.after_erase_state.clear()
            else:
                print("Warning: No before_erase_state found, skipping undo command creation")
        
        self.current_path = None
        self.current_path_item = None
        self.viewer.drawing_path = None

    def erase_at(self, pos: QPointF):
        erase_path = QPainterPath()
        erase_path.addEllipse(pos, self.eraser_size, self.eraser_size)

        for item in self._scene.items(erase_path):
            if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo:
                self._erase_item_path(item, erase_path, pos)

    def _erase_item_path(self, item, erase_path, pos):
        path = item.path()
        new_path = QPainterPath()
        
        brush_color = QColor(item.brush().color().name(QColor.HexArgb))
        if brush_color == "#80ff0000":  # Generated (filled) segmentation path
            # Map erase shape into item's local coordinates to ensure robust boolean ops
            try:
                local_erase_path = item.mapFromScene(erase_path)
            except Exception:
                # Fallback: translate by item position if mapping isn't available
                local_erase_path = QPainterPath(erase_path)
                local_erase_path.translate(-item.pos().x(), -item.pos().y())

            # Ensure consistent fill rule for robust subtraction of filled polygons
            path.setFillRule(Qt.FillRule.WindingFill)
            local_erase_path.setFillRule(Qt.FillRule.WindingFill)

            result = path.subtracted(local_erase_path)
            if not result.isEmpty():
                new_path = result
        else: # Human-drawn stroke
            element_count = path.elementCount()
            i = 0
            while i < element_count:
                e = path.elementAt(i)
                point = QPointF(e.x, e.y)
                if not erase_path.contains(point):
                    if e.type == QPainterPath.ElementType.MoveToElement: new_path.moveTo(point)
                    elif e.type == QPainterPath.ElementType.LineToElement: new_path.lineTo(point)
                    elif e.type == QPainterPath.ElementType.CurveToElement:
                        if i + 2 < element_count:
                            c1, c2 = path.elementAt(i + 1), path.elementAt(i + 2)
                            c1_p, c2_p = QPointF(c1.x, c1.y), QPointF(c2.x, c2.y)
                            if not (erase_path.contains(c1_p) or erase_path.contains(c2_p)):
                                new_path.cubicTo(point, c1_p, c2_p)
                        i += 2
                else:
                    if (i + 1) < element_count:
                        next_e = path.elementAt(i + 1)
                        next_p = QPointF(next_e.x, next_e.y)
                        if not erase_path.contains(next_p):
                            new_path.moveTo(next_p)
                            if next_e.type == QPainterPath.ElementType.CurveToDataElement:
                                i += 2
                i += 1

        if new_path.isEmpty():
            self._scene.removeItem(item)
        else:
            item.setPath(new_path)

    def set_brush_size(self, size, scaled_size):
        self.brush_size = size
        self.brush_cursor = self.create_inpaint_cursor("brush", scaled_size)

    def set_eraser_size(self, size, scaled_size):
        self.eraser_size = size
        self.eraser_cursor = self.create_inpaint_cursor("eraser", scaled_size)

    def create_inpaint_cursor(self, cursor_type, size):
        size = max(1, size)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        if cursor_type == "brush":
            painter.setBrush(QBrush(QColor(255, 0, 0, 127)))
            painter.setPen(Qt.PenStyle.NoPen)
        elif cursor_type == "eraser":
            painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
            painter.setPen(QColor(0, 0, 0, 127))
        else:
            painter.setBrush(QBrush(QColor(0, 0, 0, 127)))
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, (size - 1), (size - 1))
        painter.end()
        return QCursor(pixmap, size // 2, size // 2)
    
    def save_brush_strokes(self) -> List[Dict]:
        strokes = []
        
        # Also collect any currently visible strokes
        for item in self._scene.items():
            if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo:
                strokes.append({
                    'path': item.path(),
                    'pen': item.pen().color().name(QColor.HexArgb),
                    'brush': item.brush().color().name(QColor.HexArgb),
                    'width': item.pen().width()
                })
        return strokes

    def load_brush_strokes(self, strokes: List[Dict]):
        self.clear_brush_strokes(page_switch=True)
        for stroke in reversed(strokes):
            pen = QPen()
            pen.setColor(QColor(stroke['pen']))
            pen.setWidth(stroke['width'])
            pen.setStyle(Qt.SolidLine)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            brush = QBrush(QColor(stroke['brush']))
            if brush.color() == QColor("#80ff0000"):
                self._scene.addPath(stroke['path'], pen, brush)
            else:
                self._scene.addPath(stroke['path'], pen)
                
    def clear_brush_strokes(self, page_switch=False):
        if page_switch:      
            items_to_remove = [item for item in self._scene.items()
                               if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo]
            for item in items_to_remove:
                self._scene.removeItem(item)
            self._scene.update()
        else:
            command = ClearBrushStrokesCommand(self.viewer)
            self.viewer.command_emitted.emit(command)
            
    def has_drawn_elements(self):
        for item in self._scene.items():
            if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo:
                return True
        return False
        
    def generate_mask_from_strokes(self):
        if not self.viewer.hasPhoto(): 
            return None
        
        # Check if there are any brush strokes to process
        if not self.has_drawn_elements():
            return None

        # Handle webtoon mode vs regular mode for getting dimensions
        is_webtoon_mode = self.viewer.webtoon_mode
        if is_webtoon_mode:
            # In webtoon mode, use visible area dimensions
            visible_image, mappings = self.viewer.get_visible_area_image()
            if visible_image is None:
                return None
            height, width = visible_image.shape[:2]
        else:
            # Regular mode - use photo dimensions
            image_rect = self.viewer.photo.boundingRect()
            width, height = int(image_rect.width()), int(image_rect.height())
        
        # Ensure we have valid dimensions
        if width <= 0 or height <= 0:
            return None
        
        human_qimg = QImage(width, height, QImage.Format_Grayscale8)
        gen_qimg = QImage(width, height, QImage.Format_Grayscale8)
        human_qimg.fill(0)
        gen_qimg.fill(0)

        human_painter, gen_painter = QPainter(human_qimg), QPainter(gen_qimg)
        
        # Get transformation values for debug logging
        visible_scene_top = 0
        visible_scene_left = 0
        
        # Set up coordinate transformation for webtoon mode
        if is_webtoon_mode:
            
            # Don't use viewport bounds - use the actual visible area bounds from the mappings
            visible_image, mappings = self.viewer.get_visible_area_image()
            if mappings:
                # Get the top-left corner of the visible area in scene coordinates
                # Use scene_y_start which is the actual scene coordinate where the visible area starts
                visible_scene_top = mappings[0]['scene_y_start']
                visible_scene_left = 0  # Assuming webtoon width starts at 0
                
                # Transform from scene coordinates to visible area image coordinates
                human_painter.translate(-visible_scene_left, -visible_scene_top)
                gen_painter.translate(-visible_scene_left, -visible_scene_top)
            else:
                # Fallback: no transformation if no mappings
                print(f"[DEBUG] No mappings available, using direct scene coordinates")
        
        human_pen = QPen(QColor(255, 255, 255), self.brush_size)
        gen_pen = QPen(QColor(255, 255, 255), 2, Qt.SolidLine)
        human_painter.setPen(human_pen)
        gen_painter.setPen(gen_pen)
        brush = QBrush(QColor(255, 255, 255))
        human_painter.setBrush(brush)
        gen_painter.setBrush(brush)

        for item in self._scene.items():
            if isinstance(item, QGraphicsPathItem) and item != self.viewer.photo:
                painter = gen_painter if QColor(item.brush().color().name(QColor.HexArgb)) == "#80ff0000" else human_painter
                # Get the path bounding rect to see where the stroke is
                item_pos = item.pos()
                # Draw the path - the painter already has the transformation applied
                # We need to draw at the item position + path coordinates
                painter.save()
                painter.translate(item_pos)
                painter.drawPath(item.path())
                painter.restore()
        
        human_painter.end()
        gen_painter.end()
        
        def qimage_to_np(qimg):
            # Check for valid dimensions
            if qimg.width() <= 0 or qimg.height() <= 0:
                return np.zeros((max(1, qimg.height()), max(1, qimg.width())), dtype=np.uint8)
            
            ptr = qimg.constBits()
            arr = np.array(ptr).reshape(qimg.height(), qimg.bytesPerLine())
            return arr[:, :qimg.width()]
            
        human_mask = qimage_to_np(human_qimg)
        gen_mask = qimage_to_np(gen_qimg)

        # Dilate using backend (ksize approximated by kernel size)
        kernel = np.ones((5,5), np.uint8)
        human_mask = imk.dilate(human_mask, kernel, iterations=2)
        gen_mask = imk.dilate(gen_mask, kernel, iterations=3)

        # Combine masks (bitwise_or equivalent)
        final_mask = np.where((human_mask > 0) | (gen_mask > 0), 255, 0).astype(np.uint8)
        return final_mask
    
    def draw_segmentation_lines(self, bboxes):
        stroke = self.make_segmentation_stroke_data(bboxes)
        if stroke is None:
            return

        # Wrap in one GraphicsPathItem & emit
        fill_color = QtGui.QColor(255, 0, 0, 128)  # Semi-transparent red
        outline_color = QtGui.QColor(255, 0, 0)    # Solid red
        item = QtWidgets.QGraphicsPathItem(stroke['path'])
        item.setPen(QtGui.QPen(outline_color, 2, QtCore.Qt.SolidLine))
        item.setBrush(QtGui.QBrush(fill_color))

        self.viewer.command_emitted.emit(SegmentBoxesCommand(self.viewer, [item]))
        
        # Ensure the rectangles are visible
        self.viewer._scene.update()

    def make_segmentation_stroke_data(self, bboxes):
        if not bboxes:
            return None

        # 1) Compute tight ROI so mask stays small
        xs = [x for x1, _, x2, _ in bboxes for x in (x1, x2)]
        ys = [y for _, y1, _, y2 in bboxes for y in (y1, y2)]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        w, h = max_x - min_x + 1, max_y - min_y + 1

        # 2) Down-sample factor to cap mask size
        long_edge = 2048
        ds = max(1.0, max(w, h) / long_edge)
        mw, mh = int(w / ds) + 2, int(h / ds) + 2

        # 3) Paint the true bboxes
        mask = np.zeros((mh, mw), np.uint8)
        for x1, y1, x2, y2 in bboxes:
            x1i = int((x1 - min_x) / ds)
            y1i = int((y1 - min_y) / ds)
            x2i = int((x2 - min_x) / ds)
            y2i = int((y2 - min_y) / ds)
            mask = imk.rectangle(mask, (x1i, y1i), (x2i, y2i), 255, -1)

        # 4) Morphological closing to bridge small gaps
        ksize = 15
        kernel = imk.get_structuring_element(imk.MORPH_RECT, (ksize, ksize))
        mask_closed = imk.morphology_ex(mask, imk.MORPH_CLOSE, kernel)

        # 5) Build merged contour path
        contours, _ = imk.find_contours(mask_closed)
        if not contours:
            return None

        path = QtGui.QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        for cnt in contours:
            pts = cnt.squeeze(1)
            if pts.ndim != 2 or pts.shape[0] < 3:
                continue
            x0, y0 = pts[0]
            path.moveTo(x0 * ds + min_x, y0 * ds + min_y)
            for x, y in pts[1:]:
                path.lineTo(x * ds + min_x, y * ds + min_y)
            path.closeSubpath()

        if path.isEmpty():
            return None

        return {
            'path': path,
            'pen': QColor(255, 0, 0).name(QColor.HexArgb),
            'brush': QColor(255, 0, 0, 128).name(QColor.HexArgb),
            'width': 2,
        }

    # def draw_segmentation_lines(self, bboxes, layers: int = 1, scale_factor: float = 1.0):
    #     if not self.viewer.hasPhoto() or not bboxes: return
        
    #     all_points = np.array(bboxes).reshape(-1, 2)
    #     centroid = np.mean(all_points, axis=0)

    #     scaled_segments = []
    #     for x1, y1, x2, y2 in bboxes:
    #         p1 = (np.array([x1, y1]) - centroid) * scale_factor + centroid
    #         p2 = (np.array([x2, y2]) - centroid) * scale_factor + centroid
    #         scaled_segments.append((*p1, *p2))
            
    #     fill_color = QColor(255, 0, 0, 128)
    #     outline_color = QColor(255, 0, 0)
    #     pen = QPen(outline_color, 2, Qt.SolidLine)
    #     brush = QBrush(fill_color)

    #     items = []
    #     for _ in range(layers):
    #         for x1, y1, x2, y2 in scaled_segments:
    #             path = QPainterPath()
    #             path.addRect(QtCore.QRectF(x1, y1, x2 - x1, y2 - y1))
    #             path_item = QGraphicsPathItem(path)
    #             path_item.setPen(pen)
    #             path_item.setBrush(brush)
    #             items.append(path_item)
        
    #     if items:
    #         command = SegmentBoxesCommand(self.viewer, items)
    #         self.viewer.command_emitted.emit(command)
