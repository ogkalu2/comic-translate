from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem, QStyle
from PySide6.QtGui import QPen, QFont, QCursor, QColor, \
     QTextCharFormat, QTextBlockFormat, QTextCursor, QFontMetrics, QPainter
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
import math

class TextBlockItem(QGraphicsTextItem):
    textChanged = Signal(str)
    itemSelected = Signal(object)
    itemDeselected = Signal()
    
    def __init__(self, 
             text = "", 
             parent_item = None, 
             text_block = None, 
             font_family = "", 
             font_size = 20, 
             render_color = QColor(0, 0, 0), 
             alignment = Qt.AlignmentFlag.AlignCenter, 
             line_spacing = 1.2, 
             outline_color = QColor(255, 255, 255), 
             outline_width = 1,
             bold=False, 
             italic=False, 
             underline=False):

        super().__init__(text)
        self.parent_item = parent_item
        if text_block:
            self.setPos(text_block.xyxy[0], text_block.xyxy[1]) 
        self.text_color = render_color
        self.outline = True if outline_color else False
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.font_family = font_family
        self.font_size = font_size
        self.alignment = alignment
        self.line_spacing = line_spacing
        self.text_block = text_block

        self.handle_size = 30
        self.selected = False
        self.resizing = False
        self.resize_handle = None
        self._resize_start = None
        self.editing_mode = False

        # Rotation properties
        self.rot_handle = None
        self.rotating = False
        self.last_rotation_angle = 0
        self.rotation_smoothing = 1.0  # rotation sensitivity
        self.center_scene_pos = None  

        if text:
            self.set_text(text)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.document().contentsChanged.connect(self._on_text_changed)
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def set_text(self, text):
        if self.is_html(text):
            self.setHtml(text)
            x, y, w, h = self.text_block.xywh
            self.setTextWidth(w)
            self.set_outline(self.outline_color, self.outline_width)

        else:
            self.setPlainText(text)
            self.apply_all_attributes()

    def is_html(self, text):
        import re
        # Simple check for HTML tags
        return bool(re.search(r'<[^>]+>', text))

    def set_font(self, font_family, font_size):
        if not self.textCursor().hasSelection():
            self.font_family = font_family
            self.font_size = font_size

        font = QFont(font_family, font_size)
        self.update_text_format('font', font)

    def set_font_size(self, font_size):
        if not self.textCursor().hasSelection():
            self.font_size = font_size
        self.update_text_format('size', font_size)

    def update_text_width(self):
        fm = QFontMetrics(self.font())
        max_width = max(fm.horizontalAdvance(line) for line in self.toPlainText().split('\n'))
        self.setTextWidth(max_width)

    def set_alignment(self, alignment):
        if not self.textCursor().hasSelection():
            self.alignment = alignment
        self.update_alignment(alignment)

    def update_alignment(self, alignment):
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()
        block_format = cursor.blockFormat()
        block_format.setAlignment(alignment)

        if has_selection:
            cursor.beginEditBlock()
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeBlockFormat(block_format)
            cursor.endEditBlock()
        else:
            doc = self.document()
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.mergeBlockFormat(block_format)

        self.update()

    def update_text_format(self, attribute, value):
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()

        format_operations = {
            'color': lambda cf, v: cf.setForeground(v),
            'font': lambda cf, v: cf.setFont(v),
            'size': lambda cf, v: cf.setFontPointSize(v),
            'bold': lambda cf, v: cf.setFontWeight(QFont.Bold if v else QFont.Normal),
            'italic': lambda cf, v: cf.setFontItalic(v),
            'underline': lambda cf, v: cf.setFontUnderline(v),
            'outline': lambda cf, v: cf.setTextOutline(QPen(v[0], v[1]) if v[0] else Qt.NoPen)
        }

        if attribute not in format_operations:
            print(f"Unsupported attribute: {attribute}")
            return

        char_format = QTextCharFormat()
        format_operations[attribute](char_format, value)

        if not has_selection:
            cursor.select(QTextCursor.SelectionType.Document)    
  
        cursor.mergeCharFormat(char_format)

        # Update the document's default format
        doc_format = self.document().defaultTextOption()
        if attribute == 'color':
            self.setDefaultTextColor(value)
        elif attribute == 'font':
            self.document().setDefaultFont(value)
        elif attribute == 'size':
            font = self.document().defaultFont()
            font.setPointSize(value)
            self.document().setDefaultFont(font)
        
        # Clear the selection by moving the cursor to the end of the document
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.End)

        self.setTextCursor(cursor)
        self.document().setDefaultTextOption(doc_format)
        self.update()

    def set_line_spacing(self, spacing):
        self.line_spacing = spacing
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = QTextBlockFormat()
        spacing = spacing * 100
        spacing = float(spacing)
        block_format.setLineHeight(spacing, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cursor.mergeBlockFormat(block_format)

    def set_color(self, color):
        if not self.textCursor().hasSelection():
            self.text_color = color
        self.update_text_format('color', color)

    def set_outline(self, outline_color, outline_width):
        if not self.textCursor().hasSelection():
            self.outline_color = outline_color
            self.outline = True if outline_color else False
            self.outline_width = outline_width
        self.update_text_format('outline', (outline_color, outline_width))

    def set_bold(self, state):
        if not self.textCursor().hasSelection():
            self.bold = state
        self.update_text_format('bold', state)

    def set_italic(self, state):
        if not self.textCursor().hasSelection():
            self.italic = state
        self.update_text_format('italic', state)

    def set_underline(self, state):
        if not self.textCursor().hasSelection():
            self.underline = state
        self.update_text_format('underline', state)

    def apply_all_attributes(self):
        self.set_font(self.font_family, self.font_size)
        self.set_color(self.text_color)
        self.set_outline(self.outline_color, self.outline_width)
        self.set_bold(self.bold)
        self.set_italic(self.italic)
        self.set_underline(self.underline)
        self.set_line_spacing(self.line_spacing)
        self.update_text_width()
        self.set_alignment(self.alignment)

    def mouseDoubleClickEvent(self, event):
        if not self.editing_mode:
            self.enter_editing_mode()
        super().mouseDoubleClickEvent(event)

    def enter_editing_mode(self):
        self.editing_mode = True
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.setFocus()

    def exit_editing_mode(self):
        self.editing_mode = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clearFocus()

    def _on_text_changed(self):
        new_text = self.toPlainText()
        self.textChanged.emit(new_text)

    def mousePressEvent(self, event):
        if not self.editing_mode:
            scene_pos = event.scenePos()
            local_pos = self.mapFromScene(scene_pos)
            self.selected = self.boundingRect().contains(local_pos)
            
            if self.selected:
                self.itemSelected.emit(self)  
            
            if event.button() == Qt.LeftButton:
                self.resize_handle = self.get_handle_at_position(local_pos, self.boundingRect())
                if self.resize_handle:
                    self.resizing = True
                    self._resize_start = scene_pos
                else:
                    self.setCursor(QCursor(Qt.ClosedHandCursor))

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.editing_mode:
            if event.button() == Qt.LeftButton:
                self.resizing = False
                self.rotating = False
                self.resize_handle = None
                self._resize_start = None
                self.center_scene_pos = None  # Clear the stored center position
                self.update_cursor(event.pos())
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not self.editing_mode:
            scene_pos = event.scenePos()
            local_pos = self.mapFromScene(scene_pos)
                
            if self.resizing and self.resize_handle:
                self.resize_item(local_pos)
            else:
                self.update_cursor(local_pos)
                if self.parent_item:
                    local_last_scene = self.mapFromScene(event.lastScenePos())
                    self.move_item(local_pos, local_last_scene)
                else:
                    super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def hoverMoveEvent(self, event):
        if self.selected:
            self.update_cursor(event.pos())
            super().hoverMoveEvent(event)
    
    def handleDeselection(self):
        if self.selected:
            self.setSelected(False)
            self.selected = False
            self.itemDeselected.emit()
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if self.editing_mode:
                self.exit_editing_mode()
            self.update()

    def focusOutEvent(self, event):
        # Only exit editing mode if we're not in a text selection
        if not self.textCursor().hasSelection():
            self.handleDeselection()
        super().focusOutEvent(event)

    def init_rotation(self, scene_pos, local_pos):
        self.rotating = True
        center = self.boundingRect().center()
        self.center_scene_pos = self.mapToScene(center)
        self.last_rotation_angle = math.degrees(math.atan2(
            scene_pos.y() - self.center_scene_pos.y(),
            scene_pos.x() - self.center_scene_pos.x()
        ))

    def move_item(self, local_pos: QPointF, last_scene_pos: QPointF):
        delta = self.mapToParent(local_pos) - self.mapToParent(last_scene_pos)
        new_pos = self.pos() + delta
        
        # Calculate the bounding rect of the rotated rectangle in scene coordinates
        scene_rect = self.mapToScene(self.boundingRect())
        bounding_rect = scene_rect.boundingRect()
        
        parent_rect = self.parent_item.boundingRect()
        
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
        x, y, w, h = self.text_block.xywh
        x1 = new_pos.x()
        y1 = new_pos.y()
        self.text_block.xyxy[:] = [x1, y1, x1+w, y1+h]

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

        # Update the text_block's angle parameter
        if self.text_block:
            self.text_block.angle = new_rotation  
        self.last_rotation_angle = current_angle
    
    def update_cursor(self, pos):
        if not self.editing_mode:
            cursor = self.get_cursor_for_position(pos)
            self.setCursor(QCursor(cursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))

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
    
    def resize_item(self, pos):
        if not self._resize_start:
            return

        # Convert positions to scene coordinates
        scene_pos = self.mapToScene(pos)
        scene_start = self._resize_start

        # Calculate delta in scene coordinates
        scene_delta = scene_pos - scene_start

        # Get current rotation in radians
        angle_rad = math.radians(-self.rotation())  # Negative because we want to counter-rotate

        # Rotate delta back to item's original coordinate system
        rotated_delta_x = scene_delta.x() * math.cos(angle_rad) - scene_delta.y() * math.sin(angle_rad)
        rotated_delta_y = scene_delta.x() * math.sin(angle_rad) + scene_delta.y() * math.cos(angle_rad)
        rotated_delta = QPointF(rotated_delta_x, rotated_delta_y)

        # Get the current rect in item coordinates
        rect = self.boundingRect()
        new_rect = QRectF(rect)
        original_height = rect.height()

        # Apply the changes based on which handle is being dragged
        if self.resize_handle in ['left', 'top_left', 'bottom_left']:
            new_rect.setLeft(rect.left() + rotated_delta.x())
        if self.resize_handle in ['right', 'top_right', 'bottom_right']:
            new_rect.setRight(rect.right() + rotated_delta.x())
        if self.resize_handle in ['top', 'top_left', 'top_right']:
            new_rect.setTop(rect.top() + rotated_delta.y())
        if self.resize_handle in ['bottom', 'bottom_left', 'bottom_right']:
            new_rect.setBottom(rect.bottom() + rotated_delta.y())

        # Ensure minimum size
        min_size = 10
        if new_rect.width() < min_size:
            if 'left' in self.resize_handle:
                new_rect.setLeft(new_rect.right() - min_size)
            else:
                new_rect.setRight(new_rect.left() + min_size)
        if new_rect.height() < min_size:
            if 'top' in self.resize_handle:
                new_rect.setTop(new_rect.bottom() - min_size)
            else:
                new_rect.setBottom(new_rect.top() + min_size)

        # Calculate the change in position in scene coordinates
        old_pos = self.mapToScene(rect.topLeft())
        new_pos = self.mapToScene(new_rect.topLeft())
        pos_delta = new_pos - old_pos
        act_pos = self.pos() + pos_delta

        # Convert the new rectangle to scene coordinates to check bounds
        scene_rect = self.mapRectToScene(new_rect)
        parent_rect = self.parent_item.boundingRect()
        
        # Ensure the rectangle stays within parent bounds
        if (scene_rect.left() >= 0 and 
            scene_rect.right() <= parent_rect.right() and
            scene_rect.top() >= 0 and 
            scene_rect.bottom() <= parent_rect.bottom()):

            # Update position
            self.setPos(act_pos)

            # Update size and font
            self.setTextWidth(new_rect.width())
            height_ratio = new_rect.height() / original_height
            new_font_size = self.font_size * height_ratio
            self.set_font_size(new_font_size)

            # Update the resize start position
            self._resize_start = scene_pos
            self.update()

            self.text_block.xyxy[:] = [
                self.pos().x(),
                self.pos().y(),
                self.pos().x() + new_rect.width(),
                self.pos().y() + self.boundingRect().height()
            ]
            self.text_block.tr_origin_point = (self.transformOriginPoint().x(), self.transformOriginPoint().y())

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        rect = self.boundingRect()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self.selected:
            # Draw resize handles
            painter.setPen(QPen(Qt.blue, 1))
            painter.setBrush(Qt.white)

            handle_size = self.handle_size
            # Draw corner and edge handles for resizing
            handles = {
                'top_left': QRectF(rect.left() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size),
                'top_right': QRectF(rect.right() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size),
                'bottom_left': QRectF(rect.left() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size),
                'bottom_right': QRectF(rect.right() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size),
            }

            for handle_rect in handles.values():
                painter.drawRect(handle_rect)

        painter.restore()
        option.state = QStyle.State_None





